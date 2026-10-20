FROM alpine:3.24

WORKDIR /src

COPY src/ .
COPY src/entrypoint.sh /entrypoint.sh

RUN apk add python3 tzdata su-exec

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# pip is only needed at build time; removing it drops its vendored urllib3/msgpack CVEs
RUN pip3 install discord.py prettytable "setuptools>=78.1.1" && pip3 uninstall -y pip

# Non-Root Docker
RUN addgroup -S -g 1000 nonroot && \
    adduser -S -D -H -h /src -s /sbin/nologin -G nonroot -u 1000 nonroot && \
    chown -R nonroot:nonroot /src /entrypoint.sh && \
    chmod -R 755 /src /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "bot.py"]