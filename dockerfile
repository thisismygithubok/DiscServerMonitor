FROM alpine:3.24

WORKDIR /src

RUN apk add --no-cache python3 tzdata su-exec

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# pip is only needed at build time; removing it drops its vendored urllib3/msgpack CVEs
RUN pip3 install discord.py prettytable "setuptools>=78.1.1" && pip3 uninstall -y pip

# Copied after the installs so code changes don't invalidate the package layers
COPY src/ .
COPY src/entrypoint.sh /entrypoint.sh

# Non-Root Docker: uid/gid 10001 so it can't match a real host user (uid 1000 is usually the host owner,
# whose files would then be readable through the /host and /host_proc mounts)
RUN addgroup -S -g 10001 nonroot && \
    adduser -S -D -H -h /src -s /sbin/nologin -G nonroot -u 10001 nonroot && \
    chown -R nonroot:nonroot /src /entrypoint.sh && \
    chmod -R 755 /src /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "bot.py"]