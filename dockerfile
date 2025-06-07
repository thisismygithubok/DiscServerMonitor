FROM alpine:3

WORKDIR /src
RUN mkdir /config

COPY src/ .
COPY src/entrypoint.sh /entrypoint.sh

RUN apk update && apk upgrade
RUN apk add docker-cli python3 py3-pip tzdata gosu

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip3 install discord.py prettytable setuptools>=78.1.1

# Non-Root Docker
RUN addgroup -S -g 988 docker && \
    adduser -S -D -H -h /src -s /sbin/nologin -G docker -u 1000 nonroot && \
    adduser nonroot docker && \
    mkdir -p /config && \
    chown nonroot:docker /config && \
    chmod 2775 /config && \
    chown -R nonroot:docker /src /entrypoint.sh && \
    chmod -R 755 /src /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "bot.py"]