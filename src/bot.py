import os
import discord
import logging
from discord import app_commands
from discord.ext import commands

# Suppress the PyNaCl/davey warnings since voice functionality isn't needed.
discord.VoiceClient.warn_nacl = False
discord.VoiceClient.warn_dave = False

# discord.py's root handler colours output when the stream supports it.
discord.utils.setup_logging(level=logging.INFO, root=True)
logger = logging.getLogger(__name__)

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix=lambda bot, message: [], intents=intents, command_tree_cls=app_commands.CommandTree)

if not DISCORD_BOT_TOKEN:
    logger.error("DISCORD_BOT_TOKEN is not set in the environment variables")
    raise ValueError("DISCORD_BOT_TOKEN is required to run the bot")

if not DISCORD_GUILD_ID:
    logger.error("DISCORD_GUILD_ID is not set in the environment variables")
    raise ValueError("DISCORD_GUILD_ID is required to run the bot")

async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            logger.debug(f'Loaded {filename} cog successfully')

# setup_hook runs once before connecting; on_ready fires again on every reconnect.
@bot.event
async def setup_hook():
    try:
        await load_cogs()
        logger.info("Cogs loaded successfully")

        # Commands are guild-scoped via @app_commands.guilds in each cog
        synced_commands = await bot.tree.sync(guild=discord.Object(id=DISCORD_GUILD_ID)) # type: ignore
        logger.info(f'Synced {len(synced_commands)} commands')

    except Exception as e:
        logger.error(f'Error syncing commands: {e}')

@bot.event
async def on_ready():
    logger.info(f'Bot is ready and logged in as {bot.user}')

logger.info("Starting Discord bot...")
bot.run(f'{DISCORD_BOT_TOKEN}', log_handler=None)