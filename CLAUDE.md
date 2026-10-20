# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Discord bot (discord.py, slash commands only, single guild) that runs in a container and reports host system stats (memory, CPU, uptime, disk usage) by reading `/proc` and running `df -h`. There is no local dev environment beyond the image. Sibling project: DiscContainerController (same bot skeleton).

## Commands

There is no test suite, linter, or CI. Everything is built and run via Docker.

```sh
# Build locally (native arch)
docker build -t dsm-test .

# Run the bot locally (needs a real token/guild; see "Testing" below)
docker run --rm -e DISCORD_BOT_TOKEN=... -e DISCORD_GUILD_ID=... \
  -v /proc:/host_proc:ro dsm-test

# Check startup without connecting to a live session: a dummy token fails at login
docker run --rm -e DISCORD_BOT_TOKEN=invalid -e DISCORD_GUILD_ID=1 dsm-test

# Publish (always multi-arch; prod host is amd64, dev machine may be arm64)
docker buildx build --builder multi-builder --platform linux/amd64,linux/arm64 \
  -t thisismynameok/disc-server-monitor:latest --push .

# Vulnerability scan
docker scout cves --only-severity critical,high --format only-packages <image>
```

Docker Hub image name is `thisismynameok/disc-server-monitor` (hyphenated).

## Architecture

- `src/bot.py`: the entry point. Validates `DISCORD_BOT_TOKEN`/`DISCORD_GUILD_ID`, then in `setup_hook` (runs once) loads every `cogs/*.py` as an extension and syncs commands to the guild. `command_prefix` returns `[]` so text messages are ignored.
- `src/cogs/`: one cog per slash command (`/ping`, `/view-stats`). Each command is guild-scoped with `@app_commands.guilds(...)`; there is intentionally no `copy_global_to`. Cog filenames contain hyphens, so they are only loadable as extensions, not importable normally.
- `/view-stats`: memory from `/proc/meminfo`, CPU % from two `/proc/stat` samples 1s apart, uptime from `/proc/uptime`, disk usage from `df -h` (filters `/proc`, `/sys`, `/dev` mounts). Output is two PrettyTable embeds, ephemeral, auto-deleted after 30s.
- No permissions model: anyone in the guild can run every command.

## Container/image details that matter

- `src/entrypoint.sh` runs as root: applies `TZ`, then `exec su-exec nonroot`.
- The image has no docker CLI and no docker group; this bot never talks to the docker socket.
- The `/proc:/host_proc:ro` mount in the README is currently not read by the code (it reads the container's `/proc`, which shows host-wide memory/CPU/uptime anyway unless lxcfs is in use). Pending fix.
- `df -h` only sees the container's mounts; host drives must be bind-mounted to show up.
- pip is uninstalled from the runtime venv after install (removes vendored-library CVEs), so nothing can be pip-installed at runtime.
- `discord.py` is unpinned.

## Logging

`discord.utils.setup_logging(root=True)` gives colored output, and `bot.run(..., log_handler=None)` prevents discord.py from adding a second handler. Don't call `logging.basicConfig` at import time in any module; it duplicates every line. `VoiceClient.warn_nacl`/`warn_dave` are disabled because voice isn't used.

## Testing against Discord

Slash commands can't be invoked by the bot itself; a human has to run them in Discord. Running a second instance with the **same token** as a deployed bot makes both receive every command, and whichever responds first wins. Stop the deployed instance first, or use a separate bot application.
