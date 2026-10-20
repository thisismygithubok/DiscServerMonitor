# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Discord bot (discord.py, slash commands only, single guild) that runs in a container and reports host system stats (memory, CPU, uptime, disk usage) by reading `/proc` and running `df -h`. There is no local dev environment beyond the image. Sibling project: DiscContainerController (same bot skeleton).

## Commands

There is no test suite, linter, or CI. Everything is built and run via Docker.

```sh
# Build locally (native arch)
docker build -t dsm-test .

# Self-check for the mount table parser (the only test)
docker run --rm --entrypoint python3 -e DISCORD_GUILD_ID=1 dsm-test cogs/view-stats.py

# Run the bot locally (needs a real token/guild; see "Testing" below)
docker run --rm -e DISCORD_BOT_TOKEN=... -e DISCORD_GUILD_ID=... \
  -v /proc:/host_proc:ro -v /:/host:ro,rslave dsm-test

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
- `/view-stats`: memory from `meminfo`, CPU % from two `stat` samples 1s apart, uptime from `uptime`, all read under `PROC_ROOT` (`/host_proc` if mounted, else the container's `/proc`). Disk usage: `parse_mounts` reads the host's mount table (`/host_proc/1/mounts`), drops pseudo filesystems (`PSEUDO_FS_TYPES`), runtime paths (`SKIPPED_MOUNT_PREFIXES`) and repeat mounts of the same device, then `os.statvfs` measures each under `/host` (in a thread, since a dead network mount can block). Without both mounts it uses the container's `/proc/self/mounts`. A failed memory/CPU/uptime read is logged and shows "Unavailable". Output is two PrettyTable embeds, ephemeral, auto-deleted after 30s.
- No permissions model: anyone in the guild can run every command.

## Container/image details that matter

- `src/entrypoint.sh` runs as root: applies `TZ`, then `exec su-exec nonroot`.
- The image has no docker CLI and no docker group; this bot never talks to the docker socket.
- Stats are read from the `/proc:/host_proc:ro` mount. Without it the container's `/proc` is used, which still shows host-wide memory/CPU/uptime unless lxcfs is in use.
- Host drives are visible through the `/:/host:ro,rslave` mount (read-only; `rslave` makes drives mounted after container start show up, but Docker refuses it where host `/` isn't a shared mount, e.g. Docker Desktop, so test there with `/:/host:ro`). The bot runs as uid 1000, so it can only read world-readable host files.
- pip is uninstalled from the runtime venv after install (removes vendored-library CVEs), so nothing can be pip-installed at runtime.
- `discord.py` is unpinned.

## Logging

`discord.utils.setup_logging(root=True)` gives colored output, and `bot.run(..., log_handler=None)` prevents discord.py from adding a second handler. Don't call `logging.basicConfig` at import time in any module; it duplicates every line. `VoiceClient.warn_nacl`/`warn_dave` are disabled because voice isn't used.

## Testing against Discord

Slash commands can't be invoked by the bot itself; a human has to run them in Discord. Running a second instance with the **same token** as a deployed bot makes both receive every command, and whichever responds first wins. Stop the deployed instance first, or use a separate bot application.
