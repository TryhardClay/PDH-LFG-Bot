# commands/admin.py

import discord
from discord.ext import commands
from services.user_service import ban_user, unban_user, is_user_banned, is_user_trusted
from services.guild_service import ban_server, unban_server, is_server_banned

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Custom permission check for trusted admins (including the bot owner)
    def is_trusted_admin():
        def predicate(ctx):
            return is_user_trusted(ctx.author.id)  # Check if the user is in the trusted_admins.json list
        return commands.check(predicate)

    @commands.command(name="banuser", help="(restricted) Ban a user by User ID # from posting in bot-controlled channels and using commands.")
    @commands.check(is_trusted_admin())  # Only bot owner or trusted admins can use this
    async def ban_user_command(self, ctx, user: discord.User):
        if is_user_banned(user.id):
            await ctx.send(f"{user.mention} is already banned.")
        else:
            ban_user(user.id)
            await ctx.send(f"{user.mention} has been banned.")

    @commands.command(name="unbanuser", help="(restricted) Unban a previously banned user.")
    @commands.check(is_trusted_admin())  # Only bot owner or trusted admins can use this
    async def unban_user_command(self, ctx, user: discord.User):
        if is_user_banned(user.id):
            unban_user(user.id)
            await ctx.send(f"{user.mention} has been unbanned.")
        else:
            await ctx.send(f"{user.mention} is not banned.")

    @commands.command(name="banserver", help="(restricted) Ban a server by Server ID # from accessing the bot.")
    @commands.check(is_trusted_admin())  # Only bot owner or trusted admins can use this
    async def ban_server_command(self, ctx, guild_id: int):
        if is_server_banned(guild_id):
            await ctx.send(f"Server {guild_id} is already banned.")
        else:
            ban_server(guild_id)
            await ctx.send(f"Server {guild_id} has been banned.")

    @commands.command(name="unbanserver", help="(restricted) Unban a previously banned server.")
    @commands.check(is_trusted_admin())  # Only bot owner or trusted admins can use this
    async def unban_server_command(self, ctx, guild_id: int):
        if is_server_banned(guild_id):
            unban_server(guild_id)
            await ctx.send(f"Server {guild_id} has been unbanned.")
        else:
            await ctx.send(f"Server {guild_id} is not banned.")

    @commands.command(name="listbans", help="(restricted) Display a list of currently banned users along with their details.")
    @commands.check(is_trusted_admin())  # Only bot owner or trusted admins can use this
    async def list_bans(self, ctx):
        banned_users = is_user_banned()  # You will need a function to list all banned users.
        await ctx.send(f"Banned users: {banned_users}")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
