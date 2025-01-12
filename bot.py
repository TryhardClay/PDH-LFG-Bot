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
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Load channel filters from persistent storage
def load_channel_filters():
    try:
        with open(CHANNEL_FILTERS_PATH, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()

# Define intents (includes messages intent)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = commands.Bot(command_prefix='/', intents=intents)

# Store sent messages for reaction tracking
sent_messages = {}

# -------------------------------------------------------------------------
# Webhook Functions
# -------------------------------------------------------------------------

async def send_webhook_message(webhook_url, content=None, embeds=None, username=None, avatar_url=None):
    async with aiohttp.ClientSession() as session:
        data = {"content": content, "embeds": embeds or [], "username": username, "avatar_url": avatar_url}
        try:
            async with session.post(webhook_url, json=data) as response:
                if response.status != 204:
                    logging.error(f"Failed to send message. Status code: {response.status}")
                    logging.error(await response.text())
        except aiohttp.ClientError as e:
            logging.error(f"aiohttp.ClientError: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

# -------------------------------------------------------------------------
# Event Handlers
# -------------------------------------------------------------------------

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    await client.tree.sync()

@client.event
async def on_raw_reaction_add(payload):
    for channel_id, msg in sent_messages.items():
        if payload.message_id == msg.id:
            if str(payload.emoji) == "👍":
                guild = client.get_guild(payload.guild_id)
                user = guild.get_member(payload.user_id)
                if user:
                    await handle_reaction_update(msg, user.display_name)

# -------------------------------------------------------------------------
# Reaction and Embed Handling
# -------------------------------------------------------------------------

async def handle_reaction_update(message, player_name):
    if "players" not in message.embeds[0].fields:
        players = []
    else:
        players = message.embeds[0].fields[0].value.split("\n")

    if player_name not in players:
        players.append(player_name)

    if len(players) >= 4:
        embed = discord.Embed(title="Your game is ready!", color=discord.Color.blue())
        embed.add_field(name="Players", value="\n".join(players))
    else:
        embed = discord.Embed(title="Looking for more players...", color=discord.Color.green())
        embed.add_field(name="Players", value="\n".join(players))
        embed.set_footer(text=f"React with 👍 to join! ({4 - len(players)} more needed)")

    await message.edit(embed=embed)

# -------------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------------

@client.tree.command(name="biglfg", description="Create a cross-server LFG request.")
async def biglfg(interaction: discord.Interaction):
    await interaction.response.defer()

    source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
    source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

    embed = discord.Embed(title="Looking for more players...", color=discord.Color.green())
    embed.set_footer(text="React with 👍 to join! (4 players needed)")

    for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
        destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')
        if source_channel_id != destination_channel_id and (
                source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none'):
            try:
                message = await send_webhook_message(
                    webhook_data['url'],
                    embeds=[embed.to_dict()],
                    username=f"{interaction.user.name} from {interaction.guild.name}",
                    avatar_url=interaction.user.avatar.url if interaction.user.avatar else None
                )

                sent_messages[destination_channel_id] = message
                await message.add_reaction("👍")
            except Exception as e:
                logging.error(f"Error sending LFG request to {destination_channel_id}: {e}")

# -------------------------------------------------------------------------
# Save Functions
# -------------------------------------------------------------------------

def save_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data: {e}")

def save_channel_filters():
    try:
        with open(CHANNEL_FILTERS_PATH, 'w') as f:
            json.dump(CHANNEL_FILTERS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving channel filters: {e}")

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
