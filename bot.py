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

# Persistent storage paths
PERSISTENT_DATA_PATH = '/var/data/webhooks.json'
CHANNEL_FILTERS_PATH = '/var/data/channel_filters.json'

# Load webhook data from persistent storage with validation
def load_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'r') as f:
            data = json.load(f)
            # Basic validation (you can add more checks as needed)
            if isinstance(data, dict):
                return data
            else:
                logging.warning(f"Invalid data format in {PERSISTENT_DATA_PATH}. Starting with empty webhook data.")
                return {}
    except FileNotFoundError:
        logging.warning(f"{PERSISTENT_DATA_PATH} not found. Starting with empty webhook data.")
        return {}
    except Exception as e:
        logging.error(f"Error loading webhook data from {PERSISTENT_DATA_PATH}: {e}")
        return {}

# Load channel filters from persistent storage
def load_channel_filters():
    try:
        with open(CHANNEL_FILTERS_PATH, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            else:
                logging.warning(f"Invalid data format in {CHANNEL_FILTERS_PATH}. Starting with empty channel filters.")
                return {}
    except FileNotFoundError:
        logging.warning(f"{CHANNEL_FILTERS_PATH} not found. Starting with empty channel filters.")
        return {}
    except Exception as e:
        logging.error(f"Error loading channel filters from {CHANNEL_FILTERS_PATH}: {e}")
        return {}

# -------------------------------------------------------------------------
# Global Variables
# -------------------------------------------------------------------------

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()
# Dictionary to store BigLFG games and their associated data
big_lfg_games = {}

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def save_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data to {PERSISTENT_DATA_PATH}: {e}")

def save_channel_filters():
    try:
        with open(CHANNEL_FILTERS_PATH, 'w') as f:
            json.dump(CHANNEL_FILTERS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving channel filters to {CHANNEL_FILTERS_PATH}: {e}")

# -------------------------------------------------------------------------
# Bot Commands
# -------------------------------------------------------------------------

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    try:
        # ... (setchannel command logic) ...
    except discord.Forbidden:
        # ... (error handling) ...

@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        # ... (disconnect command logic) ...
    except Exception as e:
        # ... (error handling) ...

@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    try:
        # ... (listconnections command logic) ...
    except Exception as e:
        # ... (error handling) ...

@client.tree.command(name="resetconfig", description="Reload the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def resetconfig(interaction: discord.Interaction):
    try:
        # ... (resetconfig command logic) ...
    except Exception as e:
        # ... (error handling) ...

@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    try:
        # ... (about command logic) ...
    except Exception as e:
        # ... (error handling) ...

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

    # Manage the role when joining a server
    await manage_role(guild)

@client.event
async def on_message(message):
    if message.author == client.user or message.webhook_id:
        return

    content = message.content
    embeds = [embed.to_dict() for embed in message.embeds]
    if message.attachments:
        content += "\n" + "\n".join([attachment.url for attachment in message.attachments])

    source_channel_id = f'{message.guild.id}_{message.channel.id}'

    if source_channel_id in WEBHOOK_URLS:
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            if source_channel_id != destination_channel_id:
                destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')

                if (source_filter == destination_filter or
                    source_filter == 'none' or
                    destination_filter == 'none'):
                    try:
                        await send_webhook_message(
                            webhook_data['url'],
                            content=content,
                            embeds=embeds,
                            username=f"{message.author.name} from {message.guild.name}",
                            avatar_url=message.author.avatar.url if message.author.avatar else None
                        )

                        logging.info(f"Attempted to relay message to {destination_channel_id}")

                    except Exception as e:
                        logging.error(f"Error relaying message: {e}")

@client.event
async def on_guild_remove(guild):
    pass  # Role management is handled elsewhere

# -------------------------------------------------------------------------
# Event Handlers for Buttons
# -------------------------------------------------------------------------

@client.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data['custom_id'] == "join_button":
            # Handle join logic here
            await interaction.response.send_message("You joined the game!", ephemeral=True)
        elif interaction.data['custom_id'] == "leave_button":
            # Handle leave logic here
            await interaction.response.send_message("You left the game!", ephemeral=True)

# --- ADDED REACTION HANDLING LOGIC START ---
@client.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
        return

    # Check if the reaction is on one of the sent embeds
    if payload.message_id in sent_message_ids:
        # Add the reaction to all other copies of the embed
        for message_id in sent_message_ids:
            if message_id != payload.message_id:
                channel = client.get_channel(payload.channel_id)
                message = await channel.fetch_message(message_id)
                await message.add_reaction(payload.emoji)

@client.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == client.user.id:  # Ignore bot's own reactions
        return

    # Check if the reaction removal is on one of the sent embeds
    if payload.message_id in sent_message_ids:
        # Remove the reaction from all other copies of the embed
        for message_id in sent_message_ids:
            if message_id != payload.message_id:
                channel = client.get_channel(payload.channel_id)
                message = await channel.fetch_message(message_id)
                await message.remove_reaction(payload.emoji, client.user)  # Remove bot's reaction
# --- ADDED REACTION HANDLING LOGIC END ---

# -------------------------------------------------------------------------
# Persistent Storage Functions
# -------------------------------------------------------------------------

def save_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data to {PERSISTENT_DATA_PATH}: {e}")

def save_channel_filters():
    try:
        with open(CHANNEL_FILTERS_PATH, 'w') as f:
            json.dump(CHANNEL_FILTERS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving channel filters to {CHANNEL_FILTERS_PATH}: {e}")

# -------------------------------------------------------------------------
# Message Relay Loop
# -------------------------------------------------------------------------

@tasks.loop(seconds=1)
async def message_relay_loop():
    while True:
        try:
            await asyncio.sleep(1)  # Check for new messages every second
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

# Start the message relay loop after the bot is ready
@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    await client.tree.sync()
    message_relay_loop.start()  # Start the loop here

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
