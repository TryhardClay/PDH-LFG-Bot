# commands/admin.py

import discord
from discord.ext import commands

@client.tree.command(name="banuser", description="Ban a user from posting in bot-controlled channels and using commands.")
async def ban_user_command(interaction: discord.Interaction, user: discord.User, reason: str):
    """
    Ban a user by User ID from posting in bot-controlled channels.
    """
    # Logic for banning user
    await interaction.response.send_message(f"User {user.name} has been banned for: {reason}")

@client.tree.command(name="unbanuser", description="Unban a previously banned user.")
async def unban_user_command(interaction: discord.Interaction, user: discord.User):
    """
    Unban a user who was previously banned.
    """
    # Logic for unbanning user
    await interaction.response.send_message(f"User {user.name} has been unbanned.")

@client.tree.command(name="setchannel", description="Set a channel for cross-server communication. (admin)")
@commands.has_permissions(administrator=True)
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    """
    Set the channel for cross-server communication with a specific filter.
    """
    # Logic for setting channel
    await interaction.response.send_message(f"Channel {channel.mention} set for cross-server communication with filter {filter}.")

@client.tree.command(name="disconnect", description="Remove a channel from cross-server communication. (admin)")
@commands.has_permissions(administrator=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    Remove the channel from cross-server communication.
    """
    # Logic for disconnecting channel
    await interaction.response.send_message(f"Channel {channel.mention} has been disconnected from cross-server communication.")

@client.tree.command(name="listadmins", description="List all current bot super admins. (admin)")
@commands.has_permissions(administrator=True)
async def list_admins(interaction: discord.Interaction):
    """
    List all the super admins of the bot.
    """
    # Logic for listing admins
    await interaction.response.send_message("List of all admins: ...")

@client.tree.command(name="updateconfig", description="Reload the bot's configuration and resync commands. (admin)")
@commands.has_permissions(administrator=True)
async def update_config(interaction: discord.Interaction):
    """
    Reload the bot's configuration and resync commands with Discord.
    """
    # Logic for reloading configuration
    await interaction.response.send_message("Configuration reloaded and commands resynced.")

@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
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

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
