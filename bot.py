import discord
import aiohttp
import asyncio
import json
import os
import logging
import uuid
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
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
            if isinstance(data, dict):
                return data
            else:
                logging.error(f"Invalid data format in {PERSISTENT_DATA_PATH}")
                return {}
    except FileNotFoundError:
        return {}
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
        return {}
    except json.decoder.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CHANNEL_FILTERS_PATH}: {e}")
        return {}

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()

# Define intents (includes messages intent)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True
intents.reactions = True

client = commands.Bot(command_prefix='/', intents=intents)

# -------------------------------------------------------------------------
# Webhook Functions
# -------------------------------------------------------------------------

async def send_webhook_message(webhook_url, content=None, embeds=None, username=None, avatar_url=None):
    async with aiohttp.ClientSession() as session:
        data = {"content": content, "embeds": embeds, "username": username, "avatar_url": avatar_url}
        try:
            async with session.post(webhook_url, json=data) as response:
                if response.status in (200, 204):
                    return await response.json() if response.status == 200 else None
                else:
                    logging.error(f"Failed to send message. Status code: {response.status}")
                    logging.error(await response.text())
        except aiohttp.ClientError as e:
            logging.error(f"aiohttp.ClientError: {e}")
        except Exception as e:
            logging.error(f"Unexpected error occurred: {e}")
    return None

async def edit_webhook_message(webhook_id, webhook_token, message_id, embed):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.partial(webhook_id, webhook_token, adapter=discord.AsyncWebhookAdapter(session))
        try:
            await webhook.edit_message(message_id, embed=embed)
        except Exception as e:
            logging.error(f"Error editing webhook message: {e}")

# -------------------------------------------------------------------------
# Event Handlers
# -------------------------------------------------------------------------

@client.event
async def on_ready():
    logging.info(f"Logged in as {client.user}")
    await client.tree.sync()

@client.event
async def on_raw_reaction_add(payload):
    if payload.message_id in sent_messages:  # Check if the reaction is on a tracked message
        lfg_id = next((key for key, data in sent_messages.items() if data['message_id'] == payload.message_id), None)
        if not lfg_id:
            return

        guild = client.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if payload.user_id != client.user.id:
            players[lfg_id].add(payload.user_id)

            if len(players[lfg_id]) == 4:
                embed = discord.Embed(title="Game Ready!", description="All players are set.", color=discord.Color.blue())
                await edit_webhook_message(sent_messages[lfg_id]['webhook_id'], sent_messages[lfg_id]['webhook_token'], payload.message_id, embed)

# -------------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------------

@client.tree.command(name="biglfg", description="Create a cross-server LFG request.")
async def biglfg(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    lfg_id = str(uuid.uuid4())
    embed = discord.Embed(title="Looking for more players...", color=discord.Color.green())
    embed.set_footer(text="React with 👍 to join! (4 players needed)")

    sent_messages[lfg_id] = {}
    players[lfg_id] = set()

    for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
        try:
            message_data = await send_webhook_message(
                webhook_data['url'],
                embeds=[embed.to_dict()],
                username=f"{interaction.user.name} from {interaction.guild.name}",
                avatar_url=interaction.user.avatar.url if interaction.user.avatar else None
            )

            if message_data:
                sent_messages[lfg_id] = {
                    'message_id': message_data['id'],
                    'webhook_id': webhook_data['id'],
                    'webhook_token': webhook_data['token']
                }
        except Exception as e:
            logging.error(f"Error sending LFG message: {e}")

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
