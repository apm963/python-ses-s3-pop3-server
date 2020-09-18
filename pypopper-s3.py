"""pypopper: a file-based pop3 server

Usage:
    python pypopper.py <port> <bucket> [<object_prefix>]
"""
import logging
import os
import socket
import sys
import traceback

from boto3 import client, resource

logging.basicConfig(format="%(name)s %(levelname)s - %(message)s")
log = logging.getLogger("pypopper")
log.setLevel(logging.DEBUG) # logging.INFO

s3conn = client('s3')  # again assumes boto.cfg setup, assume AWS S3
s3 = resource('s3')

class ChatterboxConnection(object):
    END = "\r\n"
    def __init__(self, conn):
        self.conn = conn
    def __getattr__(self, name):
        return getattr(self.conn, name)
    def sendall(self, data, END=END):
        if len(data) < 50:
            # TODO: Obfuscate password when that command is used
            log.debug("send: %r", data)
        else:
            log.debug("send: %r...", data[:50])
        data += END
        self.conn.sendall(data.encode())
    def recvall(self, END=END):
        data = []
        while True:
            chunkRaw = self.conn.recv(4096)
            chunk = chunkRaw.decode("utf-8")
            if END in chunk:
                data.append(chunk[:chunk.index(END)])
                break
            data.append(chunk)
            if len(data) > 1:
                pair = data[-2] + data[-1]
                if END in pair:
                    data[-2] = pair[:pair.index(END)]
                    data.pop()
                    break
        log.debug("recv: %r", "".join(data))
        return "".join(data)


class Message(object):
    def __init__(self, bucket, object_name):
        obj = s3.Object(bucket, object_name)
        msg = obj.get()['Body']
        try:
            self.data = data = msg.read()
            self.size = len(data)
            self.top, bot = data.decode("utf-8").split("\r\n\r\n", 1)
            self.bot = bot.split("\r\n")
        finally:
            msg.close()


def handleUser(data, msgDict, msgList):
    cmd, username = data.split()
    # TODO: Implement login
    return "+OK user accepted"

def handlePass(data, msgDict, msgList):
    cmd, passPlaintext = data.split()
    # TODO: Implement login
    return "+OK pass accepted"

def handleStat(data, msgDict, msgList):
    totalSize = 0
    for msgItem in msgDict.values():
        totalSize += msgItem.size
    return "+OK %i %i" % (len(msgDict), totalSize)

def handleList(data, msgDict, msgList):
    cmd, num = data.split()
    
    # Without specific message number arg
    if num == "":
        text = ""
        i = 0
        totalSize = 0
        for key in msgDict.keys():
            i += 1
            msgSize = msgDict[key].size
            totalSize += msgSize
            text += "%i %s\r\n" % (i, msgSize)
        
        return "+OK %i messages (%i octets)\r\n%s." % (len(msgDict), totalSize, text)
    
    # With specific message number arg
    numInt = int(num);
    
    if numInt > len(msgList):
        return "-ERR no such message, only %i messages in maildrop" % len(msgList)
    
    currMsg = msgList[numInt - 1]
    
    return "+OK %i %i" % (numInt, currMsg.size)

def handleTop(data, msgDict, msgList):
    cmd, num, lines = data.split()
    numInt = int(num);
    # assert numInt == 1, "unknown message number: %i" % num
    if numInt > len(msgList):
        return "-ERR no such message"
    
    currMsg = msgList[numInt - 1]
    
    lines = int(lines)
    text = currMsg.top + "\r\n\r\n" + "\r\n".join(currMsg.bot[:lines])
    return "+OK top of message follows\r\n%s\r\n." % text

def handleRetr(data, msgDict, msgList):
    cmd, num = data.split()
    numInt = int(num);
    if numInt > len(msgList):
        return "-ERR no such message"
    
    currMsg = msgList[numInt - 1]
    
    log.info("message sent")
    return "+OK %i octets\r\n%s\r\n." % (currMsg.size, currMsg.data)

def handleDele(data, msgDict, msgList):
    cmd, num = data.split()
    numInt = int(num);
    if numInt > len(msgList):
        return "-ERR message %i already deleted" % numInt
    
    currMsg = msgList[numInt - 1]
    
    # TODO: Support deleting
    
    log.info("message %i deleted" % numInt)
    return "+OK message %i deleted" % numInt

def handleNoop(data, msgDict, msgList):
    return "+OK"

def handleCapa(data, msgDict, msgList):
    return "-ERR"

def handleUidl(data, msgDict, msgList):
    text = ""
    i = 0
    for key in msgDict.keys():
        i += 1
        text += "%i %s\r\n" % (i, key)
    # log.debug(text);
    return "+OK\r\n%s." % text

def handleQuit(data, msgDict, msgList):
    return "+OK pypopper POP3 server signing off"

dispatch = dict(
    USER=handleUser,
    PASS=handlePass,
    STAT=handleStat,
    LIST=handleList,
    TOP=handleTop,
    RETR=handleRetr,
    DELE=handleDele,
    NOOP=handleNoop,
    CAPA=handleCapa,
    UIDL=handleUidl,
    QUIT=handleQuit,
)

def serve(host, port, bucket, object_prefix = ""):
    # TODO: assert bucket exists
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    try:
        if host:
            hostname = host
        else:
            hostname = "localhost"
        log.info("pypopper POP3 serving bucket '%s' (prefix '%s') on %s:%s", bucket, object_prefix, hostname, port)
        msgDict = {}
        while True:
            sock.listen(1)
            conn, addr = sock.accept()
            log.debug('Connected by %s', addr)
            try:
                for key in s3conn.list_objects(Bucket=bucket, Prefix=object_prefix)['Contents']:
                    # print(key['Key'])
                    cleanedObjectName = key['Key'][len(object_prefix):].lstrip('/')
                    if cleanedObjectName == "AMAZON_SES_SETUP_NOTIFICATION":
                        continue
                    msg = Message(bucket, key['Key'])
                    debugObjectName = "%s_debug_3" % cleanedObjectName # This is for manually incrementing messages so clients don't cache results
                    msgDict[debugObjectName] = msg
                msgList = list(msgDict.values())
                conn = ChatterboxConnection(conn)
                conn.sendall("+OK pypopper file-based pop3 server ready")
                while True:
                    data = conn.recvall()
                    command = data.split(None, 1)[0]
                    try:
                        cmd = dispatch[command]
                    except KeyError:
                        conn.sendall("-ERR unknown command")
                        log.debug('Unknown command received [%s]', command)
                    else:
                        conn.sendall(cmd(data, msgDict, msgList))
                        if cmd is handleQuit:
                            break
            finally:
                conn.close()
    except (SystemExit, KeyboardInterrupt):
        log.info("pypopper stopped")
    except Exception as ex:
        log.critical("fatal error", exc_info=ex)
    finally:
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("USAGE: [<host>:]<port> <bucket> [<object_prefix>]")
    else:
        _, port, bucket, object_prefix = sys.argv
        if ":" in port:
            host = port[:port.index(":")]
            port = port[port.index(":") + 1:]
        else:
            host = ""
        try:
            port = int(port)
        except Exception:
            print("Unknown port:", port)
        else:
            if True: # TODO: Verify bucket exists
                serve(host, port, bucket, object_prefix)
            else:
                print("Bucket not found:", bucket)
