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

    @commands.command(name="setchannel", help="(admin) Set a channel for cross-server communication.")
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, channel: discord.TextChannel, filter: str):
        # Logic for setting the channel
        pass

    @commands.command(name="disconnect", help="(admin) Remove a channel from cross-server communication.")
    @commands.has_permissions(administrator=True)
    async def disconnect(self, ctx, channel: discord.TextChannel):
        # Logic for disconnecting the channel
        pass

    @commands.command(name="listadmins", help="(admin) Display a list of current bot super admins.")
    @commands.has_permissions(administrator=True)
    async def list_admins(self, ctx):
        # Logic for listing admins
        pass

    @commands.command(name="updateconfig", help="(admin) Reload the bot's configuration and resync commands.")
    @commands.has_permissions(administrator=True)
    async def update_config(self, ctx):
        # Logic to update configuration
        pass

    @commands.command(name="about", help="Display information about the bot and its commands.")
    async def about(self, ctx):
        """
        Display details about the bot, its available commands, and the rules for use.
        """
        try:
            embed = discord.Embed(
                title="PDH LFG Bot - Information & Commands",
                description=(
                    "This bot allows players to connect and coordinate games across different servers "
                    "through shared announcements, player listings, and automated room creation. "
                    "Below are the commands and features available.\n\n"
                    "**Note:** Restricted commands require admin privileges or special access."
                ),
                color=discord.Color.blue()
            )

            # 📜 Rules Section
            embed.add_field(
                name="📜 Rules:",
                value=(
                    "1️⃣ **Respect Others** - Treat all players with kindness and fairness.\n"
                    "2️⃣ **No Harassment** - Any form of harassment, hate speech, or discrimination will result in bans.\n"
                    "3️⃣ **Follow Server Guidelines** - Abide by each server's unique rules while using this bot.\n"
                    "4️⃣ **No Spamming** - Avoid excessive message spam, command misuse, or abuse of LFG features.\n"
                    "5️⃣ **No Poaching Users** - This bot is designed to bridge the gap between servers and not as a tool to grow your empire.\n"
                    "6️⃣ **Report Issues** - If you encounter issues, inform the server admin; or reach out to **Clay** (User ID: 582548598584115211) on Discord or email: **gaming4tryhards@gmail.com**\n\n"
                    "**🚨 Compliance Failure:** Breaking these rules may result in a user ID ban."
                ),
                inline=False
            )

            # 🌎 Public Commands
            embed.add_field(
                name="🌎 Public Commands:",
                value=(
                    "**/biglfg** - Create a cross-server LFG request and automatically manage player listings.\n"
                    "**/gamerequest** - Generate a personal TableStream game link.\n"
                    "**/addspelltable** - Add your own custom SpellTable link to an LFG chat.\n"
                    "**/about** - Display details about the bot, commands, and usage."
                ),
                inline=False
            )

            # 🔐 Admin Commands
            embed.add_field(
                name="🔐 Admin Commands (Server Admins Only):",
                value=(
                    "**/setchannel (admin)** - Set a channel for cross-server communication.\n"
                    "**/disconnect (admin)** - Remove a channel from cross-server communication.\n"
                    "**/listadmins (admin)** - Display a list of current bot super admins."
                ),
                inline=False
            )

            # 🚨 Restricted Commands (Super Admins Only)
            embed.add_field(
                name="🚨 Restricted Commands (Super Admins Only):",
                value=(
                    "**/banuser (restricted)** - Ban a user by User ID # from posting in bot-controlled channels and using commands.\n"
                    "**/unbanuser (restricted)** - Unban a previously banned user.\n"
                    "**/banserver (restricted)** - Ban a server by Server ID # from accessing the bot.\n"
                    "**/unbanserver (restricted)** - Unban a previously banned server.\n"
                    "**/listbans (restricted)** - Display a list of currently banned users along with their details.\n"
                ),
                inline=False
            )

            await ctx.send(embed=embed)
        except Exception as e:
            logging.error(f"Error in /about command: {e}")
            await ctx.send("An error occurred while processing the command.")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
