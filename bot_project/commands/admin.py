import discord
from discord.ext import commands
from services.user_service import ban_user, unban_user, is_user_banned
from services.guild_service import ban_server, unban_server, is_server_banned

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="banuser", help="(restricted) Ban a user from bot-controlled channels.")
    async def ban_user_command(self, ctx, user: discord.User):
        if is_user_banned(user.id):
            await ctx.send(f"{user.mention} is already banned.")
        else:
            ban_user(user.id)
            await ctx.send(f"{user.mention} has been banned.")

    @commands.command(name="unbanuser", help="(restricted) Unban a user.")
    async def unban_user_command(self, ctx, user: discord.User):
        if is_user_banned(user.id):
            unban_user(user.id)
            await ctx.send(f"{user.mention} has been unbanned.")
        else:
            await ctx.send(f"{user.mention} is not banned.")

    @commands.command(name="banserver", help="(restricted) Ban a server from bot access.")
    async def ban_server_command(self, ctx, guild_id: int):
        if is_server_banned(guild_id):
            await ctx.send(f"Server {guild_id} is already banned.")
        else:
            ban_server(guild_id)
            await ctx.send(f"Server {guild_id} has been banned.")

    @commands.command(name="unbanserver", help="(restricted) Unban a server.")
    async def unban_server_command(self, ctx, guild_id: int):
        if is_server_banned(guild_id):
            unban_server(guild_id)
            await ctx.send(f"Server {guild_id} has been unbanned.")
        else:
            await ctx.send(f"Server {guild_id} is not banned.")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
