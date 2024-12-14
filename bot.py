import discord
import aiohttp
import asyncio
import json
import os
import logging
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions

# -------------------------------------------------------------------------
# Setup and Configuration
# -------------------------------------------------------------------------

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

# Persistent storage path
PERSISTENT_DATA_PATH = '/var/data/webhooks.json'

# Load webhook data from persistent storage
try:
    with open(PERSISTENT_DATA_PATH, 'r') as f:
        WEBHOOK_URLS = json.load(f)
except FileNotFoundError:
    WEBHOOK_URLS = {}  # Initialize if the file doesn't exist
except json.decoder.JSONDecodeError as e:
    logging.error(f"Error decoding JSON from {PERSISTENT_DATA_PATH}: {e}")
    WEBHOOK_URLS = {}

CHANNEL_FILTERS = {}  # Dictionary to store channel filters

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = commands.Bot(command_prefix='/', intents=intents)

# Global variable to keep track of the main message handling task
message_relay_task = None

# -------------------------------------------------------------------------
# Webhook Functions
# -------------------------------------------------------------------------

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

# -------------------------------------------------------------------------
# Event Handlers
# -------------------------------------------------------------------------

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    await client.tree.sync()
    global message_relay_task
    if message_relay_task is None or message_relay_task.done():
        message_relay_task = asyncio.create_task(message_relay_loop())
    if not role_management_task.is_running():
        role_management_task.start()  

@client.event
async def on_guild_join(guild):
    # Send the welcome message to a suitable channel
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            try:
                await channel.send("Hello! I'm your cross-server communication bot. \n"
                                   "An admin needs to use the `/setchannel` command to \n"
                                   "choose a channel for relaying messages. \n"
                                   "Be sure to select an appropriate filter; either 'cpdh' or 'casual'.")
                break  # Stop after sending the message once
            except discord.Forbidden:
                pass  # Continue to the next channel if sending fails

@client.event
async def on_message(message):
    # ... (on_message logic remains the same) ...

@client.event
async def on_guild_remove(guild):
    # This is now handled by the role_management_task
    pass

# -------------------------------------------------------------------------
# Tasks
# -------------------------------------------------------------------------

@tasks.loop(seconds=60)  # Check every 60 seconds
async def role_management_task():
    try:
        for guild in client.guilds:
            try:
                # ... (role management logic remains the same) ...
            except discord.Forbidden:
                logging.warning(f"Missing permissions to manage roles in server {guild.name}")
            except discord.HTTPException as e:
                logging.error(f"Error managing role in server {guild.name}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in role_management_task: {e}")

# -------------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------------

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    # ... (setchannel logic with webhook ID storage remains the same) ...

@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    # ... (disconnect logic remains the same) ...

@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    # ... (listconnections logic remains the same) ...

@client.tree.command(name="resetconfig", description="Reload the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def resetconfig(interaction: discord.Interaction):
    # ... (resetconfig logic remains the same) ...

@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    # ... (about logic remains the same) ...

# -------------------------------------------------------------------------
# Message Relay Loop
# -------------------------------------------------------------------------

async def message_relay_loop():
    while True:
        try:
            # ... (message relay logic remains the same) ...
        except Exception as e:
            logging.error(f"Error in message relay loop: {e}")

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
