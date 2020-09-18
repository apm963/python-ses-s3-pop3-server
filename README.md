# Python POP3 server for AWS SES + S3

Purpose: todo

> Important: This does not yet support TLS or proper authentication and should not be used in production. PRs for these are welcome.

Based on [pypopper](https://code.activestate.com/recipes/534131-pypopper-python-pop3-server/).

## Usage

Basic usage:

```sh
python pypopper-s3.py 110 mybucket myobjectprefix
```

Within docker (development):

```sh
docker run -it --rm -v /path/on/host/python-ses-s3-pop3-server:/app -p 110:110 python:3-alpine sh
> python /app/pypopper-s3.py 0.0.0.0:110 mybucket myobjectprefix
```

You will need a `boto.cfg` to exist at `/etc/boto.cfg` or `~/boto.cfg` for AWS credentials.

## Deploy

```sh
docker run -d --name  --restart=always -p 110:110 python-ses-s3-pop3-server:latest mybucket myobjectprefix
```

Or alternately run as service using the included `docker-compose.yml` as a template.
