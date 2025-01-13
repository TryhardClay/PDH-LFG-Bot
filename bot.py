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
CHANNEL_FILTERS_PATH = '/var/data/channel_filters.json'  # New file for channel filters

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
active_embeds = {}  # {embed_id: {"players": [], "task": asyncio.Task, "messages": {channel_id: discord.WebhookMessage}}}
MESSAGE_QUEUE = []  # Initialize the global message queue

# Define intents (includes messages intent)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True

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
            data["content"] = content
        if embeds:
            data["embeds"] = embeds
        if username:
            data["username"] = username
        if avatar_url:
            data["avatar_url"] = avatar_url

        try:
            async with session.post(webhook_url, json=data) as response:
                if response.status != 204:
                    logging.error(f"Failed to send message. Status code: {response.status}")
                    logging.error(await response.text())

        except aiohttp.ClientError as e:
            logging.error(f"aiohttp.ClientError: {e}")
        except discord.HTTPException as e:
            logging.error(f"discord.HTTPException: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

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
async def on_reaction_add(reaction, user):
    """Handle player reactions to active LFG embeds."""
    if user.bot:
        return

    for embed_id, data in active_embeds.items():
        if reaction.message.id in [msg.id for msg in data["messages"].values()]:
            if str(reaction.emoji) == "👍":
                if user.name not in data["players"]:
                    data["players"].append(user.name)
                    await update_embeds(embed_id)
                    if len(data["players"]) == 4:
                        await lfg_complete(embed_id)
            elif str(reaction.emoji) == "👎":
                if user.name in data["players"]:
                    data["players"].remove(user.name)
                    await update_embeds(embed_id)
            break

# -------------------------------------------------------------------------
# Commands and Helpers
# -------------------------------------------------------------------------

@client.tree.command(name="biglfg", description="Create a cross-server LFG request.")
async def biglfg(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        initiating_player = interaction.user.name

        embed = discord.Embed(title="Looking for more players...", color=discord.Color.yellow())
        embed.set_footer(text="React with 👍 to join! React with 👎 to leave. (3 players needed)")
        embed.add_field(name="Players:", value=f"1. {initiating_player}", inline=False)

        sent_messages = {}

        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            try:
                message = await send_webhook_message(
                    webhook_data['url'],
                    embeds=[embed.to_dict()],
                    username=interaction.user.name,
                    avatar_url=interaction.user.avatar.url if interaction.user.avatar else None,
                )
                if message:
                    sent_messages[destination_channel_id] = message
            except Exception as e:
                logging.error(f"Error sending LFG request: {e}")

        if sent_messages:
            embed_id = list(sent_messages.values())[0].id
            active_embeds[embed_id] = {
                "players": [initiating_player],
                "messages": sent_messages,
                "task": asyncio.create_task(lfg_timeout(embed_id)),
            }
            await interaction.followup.send("LFG request sent across channels.", ephemeral=True)
        else:
            await interaction.followup.send("Failed to send LFG request to any channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /biglfg command: {e}")

async def update_embeds(embed_id):
    data = active_embeds[embed_id]
    players = data["players"]

    for channel_id, message in data["messages"].items():
        try:
            if len(players) < 4:
                embed = discord.Embed(
                    title="Looking for more players...",
                    color=discord.Color.yellow(),
                    description=f"React with 👍 to join! React with 👎 to leave. ({4 - len(players)} players needed)"
                )
            else:
                embed = discord.Embed(title="Your game is ready!", color=discord.Color.green())

            embed.add_field(
                name="Players:",
                value="\n".join([f"{i + 1}. {name}" for i, name in enumerate(players)]),
                inline=False,
            )
            await message.edit(embed=embed)
        except Exception as e:
            logging.error(f"Error updating embed: {e}")

async def lfg_complete(embed_id):
    data = active_embeds.pop(embed_id)
    for message in data["messages"].values():
        try:
            embed = discord.Embed(title="Your game is ready!", color=discord.Color.green())
            embed.add_field(
                name="Players:",
                value="\n".join([f"{i + 1}. {name}" for i, name in enumerate(data["players"])]),
                inline=False,
            )
            await message.edit(embed=embed)
        except Exception as e:
            logging.error(f"Error completing LFG request: {e}")

async def lfg_timeout(embed_id):
    await asyncio.sleep(15 * 60)
    if embed_id in active_embeds:
        data = active_embeds.pop(embed_id)
        for message in data["messages"].values():
            try:
                embed = discord.Embed(title="This request has timed out.", color=discord.Color.red())
                await message.edit(embed=embed)
            except Exception as e:
                logging.error(f"Error timing out LFG request: {e}")

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
