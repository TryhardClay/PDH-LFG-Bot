import discord
from discord.ext import commands
from services.user_service import is_user_banned, is_user_trusted

class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # These commands were not part of the legacy list and were removed to keep strict consistency
    # Command to check if user is banned or trusted has been removed.
    # Placeholder for future user management-related commands if needed.

async def setup(bot):
    await bot.add_cog(UserCommands(bot))
