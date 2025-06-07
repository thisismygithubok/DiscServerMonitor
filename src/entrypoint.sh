#!/bin/sh

if [ -n "$TZ" ]; then
    if [ -f "/usr/share/zoneinfo/$TZ" ]; then
        cp "/usr/share/zoneinfo/$TZ" /etc/localtime
        echo "$TZ" > /etc/timezone
    else
        echo "Warning: Timezone $TZ not found, using default"
    fi
else
    echo "No TZ environment variable set, using default"
fi

exec gosu nonroot "$@"