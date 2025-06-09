# DiscServerMonitor
A docker-based discord bot to help monitor the host system.

<a href="https://hub.docker.com/r/thisismynameok/disc-server-monitor"><img alt="Docker Image Size (tag)" src="https://img.shields.io/docker/image-size/thisismynameok/disc-server-monitor/latest?style=for-the-badge">
<img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/thisismynameok/disc-server-monitor?style=for-the-badge"></a>
<img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/m/thisismygithubok/DiscServerMonitor?color=brightgreen&style=for-the-badge">
<img alt="GitHub" src="https://img.shields.io/github/license/thisismygithubok/DiscServerMonitor?style=for-the-badge"></p>

## Slash Command ##
This bot is currently, a singular slash commands to use:
- /view-stats

## Docker Run ##
```
docker run -e DISCORD_GUILD_ID=<your_guild_id> -e DISCORD_BOT_TOKEN=<your_bot_token> -e TZ=<your_tz> -v /proc:/host_proc:ro thisismynameok/disc-server-monitor:latest
```

## Docker Compose ##
You can find an example in [docker-compose-example.yml](https://github.com/thisismygithubok/DiscServerMonitor/blob/main/docker-compose-example.yml)

## Environment Variables ##
- REQUIRED
    - DISCORD_GUILD_ID
        - This is your discord server ID
    - DISCORD_BOT_TOKEN
        - This is your discord bot token
        - If you need information on how to create a discord bot, please see the section below on [setting up a discord bot](#setting-up-a-discord-bot)

- OPTIONAL
    - TZ
        - This is optional, but you can specify this for the container/logging output timezone
        - Must use IANA standard timezones

```
environment:
    DISCORD_BOT_TOKEN: ${DISCORD_BOT_TOKEN}
    DISCORD_GUILD_ID: ${DISCORD_GUILD_ID}
    TZ: ${TZ}
```

## Volumes ##
You need to mount the host's /proc as a volume to the container to be able to see system stats. 
If you'd like to see usage stats on other drives than the boot drive, you'll need to mount them as well.
```
volumes:
    - /proc:/host_proc:ro
```

## Setting Up a Discord Bot ##
1. Navigate to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
    - Name it whatever you'd like the app to be named, in this case I've used "DiscServerMonitor"
3. On the "General Information" page, give it a name and description.
4. On the "Installation" page, change the install link to "None"
5. On the "Bot" page, disable "Public Bot", and enable "Message Content Intent"  
    - On this same page, make sure to copy your TOKEN as you'll need to pass this to the container
6. On the "OAuth2" page, in the OAuth2 URL Generator section, choose "bot".
    - In the "Bot Permissions" section below this, in text permissions, choose "Send Messages" and "Manage Messages".
    - Copy the generated URL at the bottom and paste it into your browser. This will open the add bot to discord screen IN DISCORD. Select the server you want to add the bot to, and viola!