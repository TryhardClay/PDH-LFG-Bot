# commands.py
import discord
from discord.ext import commands
from discord.ext.commands import has_permissions

from bot import WEBHOOK_URLS, CHANNEL_FILTERS, client, logging  # Import necessary variables and client


@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    try:
        # Convert filter to lowercase for consistency
        filter = filter.lower()

        # Check if the filter is valid
        if filter not in ("casual", "cpdh"):
            await interaction.response.send_message("Invalid filter. Please specify either 'casual' or 'cpdh'.",
                                                    ephemeral=True)
            return

        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
        WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = webhook.url
        CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter
        with open('webhooks.json', 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
        await interaction.response.send_message(
            f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to create webhooks in that channel.",
                                                ephemeral=True)


@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        channel_id = f'{interaction.guild.id}_{channel.id}'
        if channel_id in WEBHOOK_URLS:
            del WEBHOOK_URLS[channel_id]
            with open('webhooks.json', 'w') as f:
                json.dump(WEBHOOK_URLS, f, indent=4)
            await interaction.response.send_message(
                f"Channel {channel.mention} disconnected from cross-server communication.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Channel {channel.mention} is not connected to cross-server communication.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error disconnecting channel: {e}")
        await interaction.response.send_message("An error occurred while disconnecting the channel.", ephemeral=True)


@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    try:
        if WEBHOOK_URLS:
            connections = "\n".join(
                [f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} (filter: {CHANNEL_FILTERS.get(channel, 'none')})" for
                 channel in WEBHOOK_URLS])
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)


@client.tree.command(name="configreset", description="Reset the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def configreset(interaction: discord.Interaction):
    # Replace ALLOWED_GUILD_ID with the actual ID of your allowed server
    ALLOWED_GUILD_ID = 123456789012345678  # Example ID, replace with your server's ID

    if interaction.guild.id == ALLOWED_GUILD_ID:
        try:
            # Reload webhooks.json
            global WEBHOOK_URLS, CHANNEL_FILTERS
            with open('webhooks.json', 'r') as f:
                WEBHOOK_URLS = json.load(f)

            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("Bot configuration reset.")  # Updated message

        except Exception as e:
            logging.error(f"Error resetting configuration: {e}")  # Updated log message
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("An error occurred while resetting the configuration.")  # Updated message
    else:
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)


@client.tree.command(name="reloadconfig", description="Reload the bot's configuration.")
@has_permissions(manage_channels=True)  # Or any appropriate permission
async def reloadconfig(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Acknowledge the interaction first
    try:
        global WEBHOOK_URLS, CHANNEL_FILTERS
        with open('webhooks.json', 'r') as f:
            WEBHOOK_URLS = json.load(f)
        await interaction.followup.send("Bot configuration reloaded.")  # Use followup.send
    except Exception as e:
        logging.error(f"Error reloading configuration: {e}")
        await interaction.followup.send("An error occurred while reloading the configuration.")  # Use followup.send


@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Defer the interaction first
    try:
        embed = discord.Embed(title="Cross-Server Communication Bot",
                              description="This bot allows you to connect channels in different servers to relay messages and facilitate communication.",
                              color=discord.Color.blue())
        embed.add_field(name="/setchannel",
                        value="Set a channel for cross-server communication and assign a filter ('casual' or 'cpdh').",
                        inline=False)
        embed.add_field(name="/disconnect", value="Disconnect a channel from cross-server communication.",
                        inline=False)
        embed.add_field(name="/listconnections", value="List all connected channels and their filters.", inline=False)
        embed.add_field(name="/configreset",  # Updated command name
                        value="Reset the bot's configuration (restricted to a specific server).", inline=False)
        embed.add_field(name="/reloadconfig",
                        value="Reload the bot's configuration.", inline=False)
        embed.add_field(name="/biglfg",
                        value="Create a BigLFG prompt with reactions.", inline=False)
        embed.add_field(name="/about", value="Show this information.", inline=False)

        await interaction.followup.send(embed=embed)  # Use followup.send
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.followup.send("An error occurred while processing the command.")
