FROM ubuntu:latest

# No USER directive — runs as root

ENV DB_PASSWORD=supersecret123
ENV API_KEY=myapikey

RUN apt-get update && apt-get install -y openssh-server sudo

EXPOSE 22
EXPOSE 8080

ADD http://example.com/setup.sh /tmp/setup.sh
RUN chmod +x /tmp/setup.sh && sudo /tmp/setup.sh

COPY . /app
WORKDIR /app
RUN pip install flask==0.12.2

CMD ["python", "app.py"]
