import discord
import aiohttp
import asyncio
import json
import os
import logging
from discord.ext import commands
from discord.ext.commands import has_permissions

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

# --- Global variables ---
WEBHOOK_URLS = {}  # Dictionary to store webhook URLs
CHANNEL_FILTERS = {}  # Dictionary to store channel filters

# --- Helper functions ---
async def send_webhook_message(webhook_url, content=None, embeds=None, username=None, avatar_url=None):
    async with aiohttp.ClientSession() as session:
        data = {}
        if content:
            data['content'] = content
        if embeds:
            data['embeds'] = embeds
        if username:
            data['username'] = username
        if avatar_url:
            data['avatar_url'] = avatar_url
        try:
            async with session.post(webhook_url, json=data) as response:
                if response.status == 204:
                    logging.info("Message sent successfully.")
                elif response.status == 429:
                    logging.warning("Rate limited!")
                    # TODO: Implement more sophisticated rate limit handling
                else:
                    logging.error(f"Failed to send message. Status code: {response.status}")
        except aiohttp.ClientError as e:
            logging.error(f"Error sending webhook message: {e}")

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = commands.Bot(command_prefix='/', intents=intents)

# --- Slash commands ---
@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    logging.info(f"Received /setchannel command in channel {channel.name}")
    await interaction.response.defer(ephemeral=True)
    try:
        # Convert filter to lowercase for consistency
        filter = filter.lower()
        logging.info(f"Filter set to: {filter}")

        # Check if the filter is valid
        if filter not in ("casual", "cpdh"):
            await interaction.followup.send("Invalid filter. Please specify either 'casual' or 'cpdh'.")
            return

        logging.info(f"Creating webhook in channel {channel.name}")
        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
        logging.info(f"Webhook created successfully: {webhook.url}")

        # Store webhook data in webhooks.json (only store the webhook URL)
        with open('webhooks.json', 'r+') as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
            except json.JSONDecodeError:
                data = []
            data.append({
                "webhook_url": webhook.url  # Store only the webhook URL
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()

        await interaction.followup.send(
            f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.")
    except discord.Forbidden:
        logging.error("Permission denied while creating webhook.")
        await interaction.followup.send("I don't have permission to create webhooks in that channel.")
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        await interaction.followup.send("An error occurred while setting the channel.")


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
            connections = "\n".join([
                f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} (filter: {CHANNEL_FILTERS.get(channel, 'none')})"
                for channel in WEBHOOK_URLS
            ])
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)


@client.tree.command(name="configreset", description="Reset the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def configreset(interaction: discord.Interaction):
    try:
        # Reset webhooks.json to an empty dictionary
        global WEBHOOK_URLS, CHANNEL_FILTERS
        WEBHOOK_URLS = {}
        CHANNEL_FILTERS = {}
        with open('webhooks.json', 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)

        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Bot configuration reset.")

    except Exception as e:
        logging.error(f"Error resetting configuration: {e}")
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("An error occurred while resetting the configuration.")


@client.tree.command(name="updateconfig", description="Update the bot's configuration (re-fetches webhooks).")
@has_permissions(manage_channels=True)
async def updateconfig(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Acknowledge the interaction first
    try:
        global WEBHOOK_URLS, CHANNEL_FILTERS
        with open('webhooks.json', 'r') as f:
            try:
                WEBHOOK_URLS = json.load(f)  # Load only WEBHOOK_URLS from the file
            except json.JSONDecodeError:
                await interaction.followup.send("Error: `webhooks.json` is empty or corrupted.")
                return

        await interaction.followup.send("Bot configuration updated.")

    except Exception as e:
        logging.error(f"Error updating configuration: {e}")
        await interaction.followup.send("An error occurred while updating the configuration.")

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
        embed.add_field(name="/configreset",
                        value="Reset the bot's configuration (for debugging/development).", inline=False)
        embed.add_field(name="/updateconfig",  # Updated command name
                        value="Update the bot's configuration.", inline=False)
        embed.add_field(name="/about", value="Show this information.", inline=False)  # Removed /biglfg

        await interaction.followup.send(embed=embed)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.followup.send("An error occurred while processing the command.")

# --- Events ---
@client.event
async def on_ready():
    global WEBHOOK_URLS, CHANNEL_FILTERS
    logging.info(f'Logged in as {client.user}')
    try:
        with open('webhooks.json', 'r') as f:
            WEBHOOK_URLS = json.load(f)
    except FileNotFoundError:
        logging.warning("webhooks.json not found. Starting with empty configuration.")
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding webhooks.json: {e}")
    await client.tree.sync()

    # Start the BigLFG update task
    # asyncio.create_task(update_big_lfg())  # Removed for now

# ... (rest of the events) ...

# --- BigLFG feature --- (Removed for now)

# --- Main bot logic ---
client.run(TOKEN)
