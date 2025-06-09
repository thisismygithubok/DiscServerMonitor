import os
import discord
import logging
from discord import app_commands
from discord.ext import commands

# Suppress the PyNaCl warning since voice functionality isn't needed.
discord.VoiceClient.warn_nacl = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)
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
            logger.info(f'Loaded {filename} cog successfully')

@bot.event
async def on_ready():
    logger.info(f'Bot is ready and logged in as {bot.user}')
    try:        
        await load_cogs()
        logger.info("Cogs loaded successfully")

        # Add command syncing
        guild = discord.Object(id=DISCORD_GUILD_ID) # type: ignore
        bot.tree.copy_global_to(guild=guild)
        synced_commands = await bot.tree.sync(guild=guild)
        logger.info(f'Synced {len(synced_commands)} commands')

    except Exception as e:
        logger.error(f'Error syncing commands: {e}')

logger.info("Starting Discord bot...")
bot.run(f'{DISCORD_BOT_TOKEN}')