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

# ... (logging setup, TOKEN remain the same) ...

# Persistent storage path
PERSISTENT_DATA_PATH = '/var/data/webhooks.json'

# Load webhook data from persistent storage with validation
def load_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'r') as f:
            data = json.load(f)
            # Basic validation (you can add more checks as needed)
            if isinstance(data, dict):
                return data
            else:
                logging.error(f"Invalid data format in {PERSISTENT_DATA_PATH}")
                return {}
    except FileNotFoundError:
        return {}  # Initialize if the file doesn't exist
    except json.decoder.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {PERSISTENT_DATA_PATH}: {e}")
        return {}

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = {}  # Dictionary to store channel filters

# ... (intents, client remain the same) ...

# -------------------------------------------------------------------------
# Webhook Functions
# -------------------------------------------------------------------------

# ... (send_webhook_message remains the same) ...

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

@client.event
async def on_guild_join(guild):
    # ... (welcome message logic) ...

    # Manage the role when joining a server
    await manage_role(guild)

@client.event
async def on_message(message):
    # ... (on_message logic remains the same) ...

@client.event
async def on_guild_remove(guild):
    pass  # Role management is handled elsewhere

# -------------------------------------------------------------------------
# Role Management
# -------------------------------------------------------------------------

async def manage_role(guild):
    try:
        role = discord.utils.get(guild.roles, name="PDH LFG Bot")
        if not role:
            role = await guild.create_role(name="PDH LFG Bot", mentionable=True)
            logging.info(f"Created role {role.name} in server {guild.name}")
        if role not in guild.me.roles:
            await guild.me.add_roles(role)
            logging.info(f"Added role {role.name} to the bot in server {guild.name}")
    except discord.Forbidden:
        logging.warning(f"Missing permissions to manage roles in server {guild.name}")
    except discord.HTTPException as e:
        logging.error(f"Error managing role in server {guild.name}: {e}")

# -------------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------------

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    try:
        # ... (filter validation) ...

        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
        WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = {
            'url': webhook.url,
            'id': webhook.id
        }
        CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter

        # Save webhook data to persistent storage
        save_webhook_data() 

        # ... (response message) ...

    except discord.Forbidden:
        # ... (error handling) ...

# ... (other commands) ...

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def save_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data to {PERSISTENT_DATA_PATH}: {e}")

# -------------------------------------------------------------------------
# Message Relay Loop
# -------------------------------------------------------------------------

async def message_relay_loop():
    while True:
        try:
            # ... (your existing message relay logic)

        except discord.Forbidden as e:
            if "Missing Permissions" in str(e):
                # Assuming you can get the guild object from the message or context
                await manage_role(guild)  # Trigger role management
            else:
                # Handle other Forbidden errors
                ... 
        except Exception as e:
            logging.error(f"Error in message relay loop: {e}")

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
