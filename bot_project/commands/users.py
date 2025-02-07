import discord
from discord.ext import commands
from services.user_service import is_user_banned, is_user_trusted

class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="checkban", help="Check if a user is banned.")
    async def check_ban(self, ctx, user: discord.User):
        if is_user_banned(user.id):
            await ctx.send(f"{user.mention} is currently banned.")
        else:
            await ctx.send(f"{user.mention} is not banned.")

    @commands.command(name="checktrusted", help="Check if a user is a trusted admin.")
    async def check_trusted(self, ctx, user: discord.User):
        if is_user_trusted(user.id):
            await ctx.send(f"{user.mention} is a trusted admin.")
        else:
            await ctx.send(f"{user.mention} is not a trusted admin.")

async def setup(bot):
    await bot.add_cog(UserCommands(bot))
