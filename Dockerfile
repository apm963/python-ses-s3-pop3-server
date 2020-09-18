FROM python:3-alpine
LABEL maintainer="adam@mazzy.xyz"

RUN mkdir -p /usr/src/package/ && cd /usr/src/package/

COPY ["pypopper-s3.py", "requirements.txt", "/usr/src/package/"]

WORKDIR /usr/src/package
RUN pip3 install -r requirements.txt

EXPOSE 110
ENTRYPOINT ["python", "pypopper-s3.py", "0.0.0.0:110"]