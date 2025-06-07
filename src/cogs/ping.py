import os
import discord
import logging
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=DISCORD_GUILD_ID)) # type: ignore
    @app_commands.command(name='ping', description='Ping the bot to check if it is online')

    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'{interaction.user.mention} Pong!', ephemeral=True, delete_after=30)

async def setup(bot):
  await bot.add_cog(Ping(bot))