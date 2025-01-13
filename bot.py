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
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

# Persistent storage paths
PERSISTENT_DATA_PATH = '/var/data/webhooks.json'
CHANNEL_FILTERS_PATH = '/var/data/channel_filters.json'  # New file for channel filters

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

# Load channel filters from persistent storage
def load_channel_filters():
    try:
        with open(CHANNEL_FILTERS_PATH, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            else:
                logging.error(f"Invalid data format in {CHANNEL_FILTERS_PATH}")
                return {}
    except FileNotFoundError:
        return {}  # Initialize if the file doesn't exist
    except json.decoder.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CHANNEL_FILTERS_PATH}: {e}")
        return {}

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()  # Load channel filters

# Active embeds tracking
active_embeds = {}  # {message_id: {"players": [], "task": timeout_task, "channels": [channel_ids]}}

# Define intents (includes messages intent)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True  # Added for caching messages

client = commands.Bot(command_prefix='/', intents=intents)

# Global variable to keep track of the main message handling task
message_relay_task = None
MESSAGE_QUEUE = []  # Initialize the message queue

# -------------------------------------------------------------------------
# Webhook Functions
# -------------------------------------------------------------------------

async def send_webhook_message(webhook_url, content=None, embeds=None, username=None, avatar_url=None):
    """Send a message via a webhook and return the WebhookMessage object."""
    try:
        # Ensure that embeds is always a list (even if empty)
        if embeds is None:
            embeds = []

        # Log the embed contents for debugging
        logging.debug(f"Sending webhook message with embeds: {embeds}")

        webhook = discord.Webhook.from_url(webhook_url, session=aiohttp.ClientSession())
        message = await webhook.send(
            content=content,
            embeds=[discord.Embed.from_dict(embed) for embed in embeds] if embeds else None,
            username=username,
            avatar_url=avatar_url,
            wait=True,  # Wait for the message to be sent and return it
        )
        return message  # Return the WebhookMessage object
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending webhook message: {e}")
        return None

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
    # Check if the message is from the bot itself (to prevent infinite loops)
    if message.author == client.user:
        return

    # If the message was sent by a webhook and isn't our bot, ignore it
    if message.webhook_id and message.author.id != client.user.id:
        return

    # Ensure that content is never None
    content = message.content if message.content is not None else ""

    # Prepare embeds (if any)
    embeds = [embed.to_dict() for embed in message.embeds]

    # Add attachment URLs to content if there are any attachments
    if message.attachments:
        content += "\n" + "\n".join([attachment.url for attachment in message.attachments])

    source_channel_id = f'{message.guild.id}_{message.channel.id}'

    if source_channel_id in WEBHOOK_URLS:
        # Retrieve the filter settings for the source channel
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

        # Loop over the destination channels
        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            if source_channel_id != destination_channel_id:
                destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')

                # Check if the source and destination filters match
                if (source_filter == destination_filter or
                        source_filter == 'none' or
                        destination_filter == 'none'):
                    try:
                        # Log the sending of the webhook message inside the loop
                        logging.debug(f"Sending webhook message to {webhook_data['url']} with content: {content} and embeds: {embeds}")

                        # Send the webhook message
                        await send_webhook_message(
                            webhook_data['url'],
                            content=content,
                            embeds=embeds,
                            username=f"{message.author.name} from {message.guild.name}",
                            avatar_url=message.author.avatar.url if message.author.avatar else None
                        )
                    except Exception as e:
                        logging.error(f"Error relaying message: {e}")

@client.event
async def on_guild_remove(guild):
    pass  # Role management is handled elsewhere

@client.event
async def on_reaction_add(reaction, user):
    """Handle player reactions to active LFG embeds."""
    if user.bot:
        return  # Ignore bot reactions

    # Iterate through active embeds to check if the reaction belongs to one of them
    for embed_id, data in active_embeds.items():
        if reaction.message.id in [msg.id for msg in data["messages"].values()]:
            if str(reaction.emoji) == "👍":
                # Ensure the user isn't already in the player list
                if user.name not in data["players"]:
                    data["players"].append(user.name)  # Add the user to the players list
                    await update_embeds(embed_id)  # Update all related embeds

                    # If the player limit is reached, complete the LFG request
                    if len(data["players"]) == 4:
                        await lfg_complete(embed_id)

            elif str(reaction.emoji) == "👎":
                # Remove the user from the players list if they are in it
                if user.name in data["players"]:
                    data["players"].remove(user.name)
                    await update_embeds(embed_id)  # Update all related embeds

            break  # No need to check further once the embed is identified

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
        filter = filter.lower()

        if filter not in ("casual", "cpdh"):
            await interaction.response.send_message("Invalid filter. Please specify either 'casual' or 'cpdh'.",
                                                    ephemeral=True)
            return

        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
        WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = {
            'url': webhook.url,
            'id': webhook.id
        }
        CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter

        save_webhook_data()
        save_channel_filters()

        await interaction.response.send_message(
            f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to create webhooks in that channel.",
                                                ephemeral=True)

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

async def update_embeds(embed_id):
    """Update all related embeds with the current player list."""
    data = active_embeds[embed_id]
    players = data["players"]

    for channel_id, message in data["messages"].items():
        try:
            if len(players) < 4:
                embed = discord.Embed(
                    title="Looking for more players...",
                    color=discord.Color.yellow(),
                    description=f"React with 👍 to join! React with 👎 to leave. ({4 - len(players)} players needed)",
                )
            else:
                embed = discord.Embed(title="Your game is ready!", color=discord.Color.green())

            embed.add_field(name="Players:", value="\n".join([f"{i + 1}. {name}" for i, name in enumerate(players)]), inline=False)
            await message.edit(embed=embed)
        except Exception as e:
            logging.error(f"Error updating embed in channel {channel_id}: {e}")

async def lfg_complete(embed_id):
    """Complete an LFG request when the player limit is reached."""
    if embed_id in active_embeds:
        data = active_embeds.pop(embed_id)
        for channel_id, message in data["messages"].items():
            try:
                embed = discord.Embed(title="Your game is ready!", color=discord.Color.green())
                embed.add_field(name="Players:", value="\n".join(data["players"]), inline=False)
                await message.edit(embed=embed)
            except Exception as e:
                logging.error(f"Error updating embed on completion in channel {channel_id}: {e}")

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
