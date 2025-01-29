import asyncio
import discord
import aiohttp
import json
import os
import logging
import uuid
import time
import requests
import re
from enum import Enum
from discord.ext import commands
from discord.ext.commands import has_permissions
from discord.ui import Button, View
from cachetools import TTLCache
from datetime import datetime, timedelta
from aiohttp_retry import RetryClient, ExponentialRetry

# -------------------------------------------------------------------------
# Setup and Configuration
# -------------------------------------------------------------------------

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a dictionary with a 24-hour expiration (in seconds)
relayed_text_messages = TTLCache(maxsize=10000, ttl=24 * 60 * 60)  # Max size, TTL, and 24-hour expiration

# Set up global rate limit handling
RATE_LIMIT_DELAY = 0.5  # Default delay between API calls to prevent spamming

message_map = {}

# BigLFG Embed Tracking
active_embeds = {}  # Independently managed

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

# Persistent storage paths
PERSISTENT_DATA_PATH = '/var/data/webhooks.json'
CHANNEL_FILTERS_PATH = '/var/data/channel_filters.json'

# Add the IMAGE_URL variable here
IMAGE_URL = "https://raw.githubusercontent.com/TryhardClay/PDH-LFG-Bot/main/PDHBot.jpg"

# Define RateLimiter Class
class RateLimiter:
    def __init__(self, max_requests: int, period: float):
        """
        Initialize a rate limiter.
        :param max_requests: Maximum number of requests allowed.
        :param period: Time period (in seconds) for the rate limit.
        """
        self.max_requests = max_requests
        self.period = period
        self.requests = asyncio.Queue()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = datetime.now()
            while not self.requests.empty():
                if (now - self.requests.queue[0]).total_seconds() > self.period:
                    await self.requests.get()
                else:
                    break

            if self.requests.qsize() >= self.max_requests:
                wait_time = self.period - (now - self.requests.queue[0]).total_seconds()
                logging.warning(f"Rate limit reached. Pausing for {wait_time:.2f} seconds.")
                await asyncio.sleep(wait_time)

            await self.requests.put(now)

# Define PauseManager Class
class PauseManager:
    def __init__(self, violation_threshold: int, pause_duration: int):
        """
        Initialize the pause manager.
        :param violation_threshold: Number of rate limit violations to trigger a pause.
        :param pause_duration: Duration (in seconds) of the pause.
        """
        self.violation_threshold = violation_threshold
        self.pause_duration = pause_duration
        self.violations = 0
        self.last_violation_time = datetime.now()

    async def handle_violation(self):
        now = datetime.now()
        if (now - self.last_violation_time).total_seconds() > 60:
            self.violations = 0  # Reset violations after 1 minute
        self.violations += 1
        self.last_violation_time = now

        if self.violations >= self.violation_threshold:
            logging.critical(f"Too many rate limit violations! Pausing for {self.pause_duration} seconds.")
            await asyncio.sleep(self.pause_duration)
            self.violations = 0

# Initialize RateLimiter and PauseManager
rate_limiter = RateLimiter(max_requests=50, period=1)  # Adjust to Discord limits
pause_manager = PauseManager(violation_threshold=5, pause_duration=30)

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
        return {}
    except json.decoder.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CHANNEL_FILTERS_PATH}: {e}")
        return {}

class GameFormat(Enum):
    PAUPER_EDH = "Pauper EDH"

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()

# Define intents (includes messages intent)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True

client = commands.Bot(command_prefix='/', intents=intents)

# -------------------------------------------------------------------------
# Webhook Functions
# -------------------------------------------------------------------------

async def send_webhook_message(webhook_url, content=None, embeds=None, username=None, avatar_url=None):
    """
    Send a message using a webhook to a specific channel.
    Handles content, embeds, username attribution, and avatar.
    """
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
                if response.status == 204:
                    logging.info(f"Message sent successfully to webhook at {webhook_url}.")
                    return None  # No content to parse
                elif response.status >= 200 and response.status < 300:
                    logging.info(f"Message sent to webhook at {webhook_url} with response: {response.status}")
                    return await response.json()  # Parse response only for non-204 success codes
                else:
                    logging.error(f"Failed to send message. Status code: {response.status}")
                    logging.error(await response.text())
        except aiohttp.ClientError as e:
            logging.error(f"aiohttp.ClientError: {e}")
        except discord.HTTPException as e:
            logging.error(f"discord.HTTPException: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

    return None

def save_webhook_data():
    """
    Save the current webhook data to persistent storage.
    """
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data to {PERSISTENT_DATA_PATH}: {e}")

def save_channel_filters():
    """
    Save the current channel filters to persistent storage.
    """
    try:
        with open(CHANNEL_FILTERS_PATH, 'w') as f:
            json.dump(CHANNEL_FILTERS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving channel filters to {CHANNEL_FILTERS_PATH}: {e}")

# -------------------------------------------------------------------------
# Gateway Functions (Text Messages and BigLFG Embeds)
# -------------------------------------------------------------------------

class TableStreamGameTypes(Enum):
    MTGCommander = "MTGCommander"

def table_stream_game_type(format: str) -> TableStreamGameTypes:
    # Always map Pauper EDH to MTGCommander
    if format == "PAUPER_EDH":
        return TableStreamGameTypes.MTGCommander
    raise ValueError(f"Unsupported game format: {format}")

def sanitize_room_name(requester_name: str) -> str:
    """
    Generate a valid room name by sanitizing the requester's name.
    Ensures the name meets TableStream's requirements.
    """
    base_room_name = f"{requester_name}'s Pauper EDH Room"
    # Remove problematic characters and trim to 100 characters
    sanitized_name = re.sub(r"[^a-zA-Z0-9\s]", "", base_room_name).strip()[:100]
    if len(sanitized_name) > 100:
        sanitized_name = sanitized_name[:100]
    return sanitized_name

# Text Message Relay
async def relay_text_message(source_message, destination_channel):
    """
    Relay a text message across servers using the Gateway API.
    """
    try:
        formatted_content = (
            f"{source_message.author.name} (from {source_message.guild.name}) said:\n"
            f"{source_message.content}"
        )

        relayed_message = await destination_channel.send(content=formatted_content)

        original_id = str(source_message.id)
        relay_channel_id = str(destination_channel.id)
        relay_message_id = str(relayed_message.id)

        # Update the message_map
        if original_id not in message_map:
            message_map[original_id] = {
                "original_channel_id": str(source_message.channel.id),
                "relayed_messages": []
            }
        message_map[original_id]["relayed_messages"].append({
            "channel_id": relay_channel_id,
            "message_id": relay_message_id
        })

        logging.info(f"Updated message_map: {json.dumps(message_map, indent=4)}")
        return relayed_message
    except Exception as e:
        logging.error(f"Error relaying message to channel {destination_channel.id}: {e}")
        return None

# Text Message Edit Propagation
async def propagate_text_edit(before, after):
    """
    Handle and propagate edits to text messages across servers.
    """
    try:
        logging.info(f"Processing edit for message ID: {before.id}")
        
        # Find the original message in message_map
        for original_id, data in message_map.items():
            if str(before.id) == original_id:
                # Edit all relayed messages
                for relayed in data["relayed_messages"]:
                    try:
                        channel = client.get_channel(int(relayed["channel_id"]))
                        if not channel:
                            logging.warning(f"Channel {relayed['channel_id']} not accessible. Skipping.")
                            continue

                        message = await channel.fetch_message(int(relayed["message_id"]))
                        await message.edit(content=f"{after.author.name} (from {after.guild.name}) said:\n{after.content}")
                        logging.info(f"Message edit propagated to message ID: {relayed['message_id']} in channel {relayed['channel_id']}")
                    except Exception as e:
                        logging.error(f"Error editing message ID {relayed['message_id']}: {e}")
                return
        
        logging.warning(f"Original message {before.id} not found in message_map. Cannot propagate edits.")
    except Exception as e:
        logging.error(f"Error in propagate_text_edit: {e}")

# Text Message Reaction Propagation
async def propagate_reaction_add(reaction, user):
    """
    Handle and propagate reactions added to text messages across servers.
    """
    try:
        if user.bot:
            return  # Ignore bot reactions

        logging.info(f"Reaction {reaction.emoji} added by {user.name} in channel {reaction.message.channel.id}")

        for original_id, data in message_map.items():
            relayed_messages = data["relayed_messages"]
            if any(str(reaction.message.id) == relayed["message_id"] for relayed in relayed_messages) or str(reaction.message.id) == original_id:
                logging.info(f"Match found for message ID: {reaction.message.id} (Original ID: {original_id})")

                # Propagate the reaction to all associated messages
                for relayed in relayed_messages:
                    if str(reaction.message.id) != relayed["message_id"]:  # Skip the triggering message
                        try:
                            channel = client.get_channel(int(relayed["channel_id"]))
                            if not channel:
                                logging.warning(f"Channel {relayed['channel_id']} not accessible. Skipping.")
                                continue

                            message = await channel.fetch_message(int(relayed["message_id"]))
                            await message.add_reaction(reaction.emoji)
                            logging.info(f"Propagated reaction {reaction.emoji} to message ID: {relayed['message_id']} in channel {relayed['channel_id']}")
                        except Exception as e:
                            logging.error(f"Error propagating reaction to message ID {relayed['message_id']}: {e}")

                # Add reaction to the original message if not already triggered
                if str(reaction.message.id) != original_id:
                    try:
                        original_channel = client.get_channel(int(data["original_channel_id"]))
                        if original_channel:
                            original_message = await original_channel.fetch_message(int(original_id))
                            await original_message.add_reaction(reaction.emoji)
                            logging.info(f"Propagated reaction {reaction.emoji} to original message ID: {original_id}")
                    except discord.NotFound:
                        logging.warning(f"Original message {original_id} not found. Skipping reaction propagation to it.")
                    except Exception as e:
                        logging.error(f"Error propagating reaction to the original message ID {original_id}: {e}")

                return  # Exit after processing the match

        logging.warning(f"Message ID {reaction.message.id} not found in message_map. Cannot propagate reactions.")
    except Exception as e:
        logging.error(f"Error in propagate_reaction_add: {e}")

# BigLFG Embed Propagation
async def relay_lfg_embed(embed, source_filter, initiating_player, destination_channel):
    """
    Relay a BigLFG embed to other connected servers using the Gateway API.
    Manages the embed view and player interactions independently.
    """
    try:
        sent_message = await destination_channel.send(embed=embed, view=create_lfg_view())
        logging.info(f"Relayed BigLFG embed to channel {destination_channel.id}")
        return sent_message
    except Exception as e:
        logging.error(f"Error relaying BigLFG embed to channel {destination_channel.id}: {e}")
        return None

# Helper to Update Embeds
async def update_embeds(lfg_uuid):
    """
    Update all embeds associated with the given LFG UUID.
    """
    try:
        if lfg_uuid not in active_embeds:
            logging.warning(f"LFG UUID {lfg_uuid} not found in active_embeds. Cannot update embeds.")
            return

        data = active_embeds[lfg_uuid]
        players = data["players"]
        is_game_ready = len(players) == 4

        # Generate the Table Stream link only once and reuse it
        if is_game_ready and "game_link" not in data:
            logging.info("Generating Table Stream link for the first time...")
            game_data = {"id": str(uuid.uuid4())}
            game_format = GameFormat.PAUPER_EDH
            player_count = 4

            # Call API only once
            game_link, game_password = await generate_tablestream_link(game_data, game_format, player_count)

            if game_link:
                data["game_link"] = game_link  # Store the generated game link
                data["game_password"] = game_password  # Store the password
            else:
                logging.error("Failed to generate Table Stream link.")
                data["game_link"] = "Error generating game link"
                data["game_password"] = None

        # Update all embeds with the player list, Table Stream link, and other information
        for channel_id, message in data["messages"].items():
            try:
                embed = discord.Embed(
                    title="Your game is ready!" if is_game_ready else "Looking for more players...",
                    color=discord.Color.green() if is_game_ready else discord.Color.yellow(),
                )
                embed.set_author(
                    name="PDH LFG Bot",
                    icon_url=IMAGE_URL,
                    url="https://github.com/TryhardClay/PDH-LFG-Bot"
                )
                if not is_game_ready:
                    embed.set_thumbnail(url=IMAGE_URL)

                # Add the player list
                embed.add_field(
                    name="Players:",
                    value="\n".join([f"{i + 1}. {name}" for i, name in enumerate(players.values())]),
                    inline=False
                )

                if is_game_ready:
                    # Add the Table Stream link to the embed
                    embed.add_field(
                        name="Table Stream Game:",
                        value=f"[Click this link to join your Table Stream game.]({data['game_link']})",
                        inline=False
                    )

                    # Add Spelltable prompt
                    embed.add_field(name="Spelltable:", value="**Or link your own Spelltable link below...**", inline=False)

                    # Remove buttons
                    view = discord.ui.View()
                    await message.edit(view=view)

                    # Cancel the timeout task
                    task = data.pop("task", None)
                    if task and not task.done():
                        task.cancel()
                        logging.info(f"Timeout task canceled for LFG UUID {lfg_uuid} as the game is ready.")

                    # Send DMs to all players with the same game link and password
                    if "dm_sent" not in data or not data["dm_sent"]:  # Ensure DMs are only sent once
                        for user_id in players:
                            try:
                                user = await client.fetch_user(user_id)
                                if user:
                                    # Link to the original message in the server
                                    message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                                    dm_content = (
                                        f"**Your game is ready!**\n\n"
                                        f"**Table Stream Link:** {data['game_link']}\n"
                                        f"**Password:** {data['game_password']}\n\n"
                                        f"You can also view the game request message here: [Click to view the message.]({message_link})"
                                    )
                                    await user.send(dm_content)
                                    logging.info(f"DM sent to {user.name} (ID: {user.id}).")
                            except Exception as e:
                                logging.error(f"Failed to DM player {user_id}: {e}")
                        data["dm_sent"] = True  # Mark DMs as sent

                await message.edit(embed=embed)

            except Exception as e:
                logging.error(f"Error updating embed in channel {channel_id} for LFG UUID {lfg_uuid}: {e}")
    except Exception as e:
        logging.error(f"Error in update_embeds for LFG UUID {lfg_uuid}: {e}")

# Helper to Create BigLFG View
def create_lfg_view():
    """
    Create and return a Discord UI View with JOIN and LEAVE buttons for the BigLFG embed.
    """
    view = discord.ui.View(timeout=15 * 60)  # 15-minute timeout

    async def join_button_callback(button_interaction: discord.Interaction):
        try:
            lfg_uuid = None
            for uuid, data in active_embeds.items():
                if any(message.id == button_interaction.message.id for message in data["messages"].values()):
                    lfg_uuid = uuid
                    break

            if not lfg_uuid or lfg_uuid not in active_embeds:
                await button_interaction.response.send_message("This LFG request is no longer active.", ephemeral=True)
                return

            user_id = button_interaction.user.id
            display_name = button_interaction.user.name

            if user_id not in active_embeds[lfg_uuid]["players"]:
                active_embeds[lfg_uuid]["players"][user_id] = display_name
                await update_embeds(lfg_uuid)

            await button_interaction.response.defer()
        except discord.errors.NotFound:
            logging.error("Interaction not found. This might be caused by a timeout or invalid interaction.")

    async def leave_button_callback(button_interaction: discord.Interaction):
        try:
            lfg_uuid = None
            for uuid, data in active_embeds.items():
                if any(message.id == button_interaction.message.id for message in data["messages"].values()):
                    lfg_uuid = uuid
                    break

            if not lfg_uuid or lfg_uuid not in active_embeds:
                await button_interaction.response.send_message("This LFG request is no longer active.", ephemeral=True)
                return

            user_id = button_interaction.user.id

            if user_id in active_embeds[lfg_uuid]["players"]:
                del active_embeds[lfg_uuid]["players"][user_id]
                await update_embeds(lfg_uuid)

                # Restart timeout if player count falls below four
                if len(active_embeds[lfg_uuid]["players"]) < 4:
                    task = active_embeds[lfg_uuid].get("task")
                    if not task or task.done():
                        active_embeds[lfg_uuid]["task"] = asyncio.create_task(lfg_timeout(lfg_uuid))
                        logging.info(f"Timeout task restarted for LFG UUID {lfg_uuid} as the player count fell below four.")

            await button_interaction.response.defer()
        except discord.errors.NotFound:
            logging.error("Interaction not found. This might be caused by a timeout or invalid interaction.")

    join_button = discord.ui.Button(style=discord.ButtonStyle.success, label="JOIN")
    leave_button = discord.ui.Button(style=discord.ButtonStyle.danger, label="LEAVE")

    join_button.callback = join_button_callback
    leave_button.callback = leave_button_callback

    view.add_item(join_button)
    view.add_item(leave_button)

    return view

# Helper for timeout handling of BigLFG requests
async def lfg_timeout(lfg_uuid):
    """
    Handle timeout for an LFG embed.
    """
    try:
        await asyncio.sleep(15 * 60)  # Wait 15 minutes
        if lfg_uuid in active_embeds:
            data = active_embeds.pop(lfg_uuid)
            for message in data["messages"].values():
                try:
                    embed = discord.Embed(title="This request has timed out.", color=discord.Color.red())
                    await message.edit(embed=embed, view=None)
                except Exception as e:
                    logging.error(f"Error updating embed on timeout for LFG UUID {lfg_uuid}: {e}")
    except Exception as e:
        logging.error(f"Error in lfg_timeout for LFG UUID {lfg_uuid}: {e}")

# Helper to generate TableStream link
async def generate_tablestream_link(game_data: dict, game_format: GameFormat, player_count: int) -> tuple[str | None, str | None]:
    """
    Generate a TableStream link using the provided game data, format, and player count.
    """
    try:
        logging.info(f"Generating TableStream link with game_data: {game_data}, game_format: {game_format}, player_count: {player_count}")

        # API setup
        api_url = "https://api.table-stream.com/create-room"
        token_bearer = os.environ.get("TABLESTREAM_BEARER_TOKEN")
        if not token_bearer:
            logging.error("Bearer token for TableStream API is missing!")
            return None, None

        headers = {
            "Authorization": f"Bearer {token_bearer}",
            "Content-Type": "application/json"
        }

        payload = {
            "roomName": f"{game_data['id']} Pauper EDH Room",
            "gameType": "MTGCommander",
            "maxPlayers": player_count,
            "private": True,
            "initialScheduleTTLInSeconds": 3600  # 1 hour
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status == 201:  # HTTP Created
                    data = await response.json()
                    room_url = data.get("room", {}).get("roomUrl")
                    password = data.get("room", {}).get("password")
                    logging.info(f"Successfully generated TableStream link: {room_url}")
                    return room_url, password
                else:
                    error = await response.json()
                    logging.error(f"Failed to generate TableStream link. Status: {response.status}, Error: {error}")
                    return None, None
    except Exception as e:
        logging.error(f"Error while generating TableStream link: {e}")
        return None, None

# -------------------------------------------------------------------------
# Event Handlers
# -------------------------------------------------------------------------

@client.event
async def on_ready():
    """
    Event triggered when the bot is ready. Reloads configuration files,
    logs guild connections, and initializes the bot state.
    """
    logging.info(f"Bot is ready and logged in as {client.user}")

    # Reload configurations from persistent storage
    global WEBHOOK_URLS, CHANNEL_FILTERS
    WEBHOOK_URLS = load_webhook_data()
    CHANNEL_FILTERS = load_channel_filters()
    logging.info("Configurations reloaded successfully.")

    # Force sync commands with Discord
    try:
        await client.tree.sync()
        logging.info("Commands have been synced successfully.")
    except Exception as e:
        logging.error(f"Error syncing commands: {e}")

    # Log connected guilds for monitoring
    for guild in client.guilds:
        logging.info(f"Connected to server: {guild.name} (ID: {guild.id})")

    logging.info("Bot is ready to receive updates and relay messages.")

@client.event
async def on_message(message):
    """
    Handles new text messages and propagates them across connected channels.
    Ensures attribution to the original author and respects channel filters.
    """
    if message.author == client.user or message.webhook_id:
        return  # Ignore bot messages and webhook messages

    source_channel_id = f'{message.guild.id}_{message.channel.id}'
    if source_channel_id in WEBHOOK_URLS:
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')
        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            if source_channel_id != destination_channel_id:
                destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')
                if source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none':
                    destination_channel = client.get_channel(int(destination_channel_id.split('_')[1]))
                    if destination_channel:
                        await relay_text_message(message, destination_channel)

@client.event
async def on_message_edit(before, after):
    """
    Handles edits to messages and propagates updates across all relayed copies.
    """
    await propagate_text_edit(before, after)

@client.event
async def on_message_delete(message):
    """
    Handles deletions of messages and ensures all related relayed copies are also deleted.
    """
    try:
        for original_id, data in list(message_map.items()):
            if str(message.id) == original_id:
                # Delete all relayed messages
                logging.info(f"Deleting relayed messages for original message ID: {message.id}")
                for relayed in data["relayed_messages"]:
                    try:
                        channel = client.get_channel(int(relayed["channel_id"]))
                        if not channel:
                            logging.warning(f"Channel {relayed['channel_id']} not accessible. Skipping.")
                            continue

                        target_message = await channel.fetch_message(int(relayed["message_id"]))
                        await target_message.delete()
                        logging.info(f"Deleted relayed message ID: {relayed['message_id']} in channel {relayed['channel_id']}")
                    except Exception as e:
                        logging.error(f"Error deleting message ID {relayed['message_id']}: {e}")
                del message_map[original_id]  # Remove from map after deletion
                return
        
        logging.warning(f"Original message {message.id} not found in message_map. Cannot propagate deletion.")
    except Exception as e:
        logging.error(f"Error in on_message_delete: {e}")

@client.event
async def on_reaction_add(reaction, user):
    """
    Handle and propagate reactions across all associated messages.
    """
    if user.bot:
        return  # Ignore bot reactions

    try:
        logging.info(f"Reaction {reaction.emoji} added by {user.name} in channel {reaction.message.channel.id}")

        # Locate the original message ID
        for original_id, data in message_map.items():
            relayed_messages = data["relayed_messages"]
            if any(str(reaction.message.id) == relayed["message_id"] for relayed in relayed_messages) or str(reaction.message.id) == original_id:
                logging.info(f"Match found for message ID: {reaction.message.id} (Original ID: {original_id})")

                # Propagate the reaction to all relayed messages
                for relayed in relayed_messages:
                    if str(reaction.message.id) != relayed["message_id"]:  # Skip the triggering message
                        try:
                            channel = client.get_channel(int(relayed["channel_id"]))
                            if not channel:
                                logging.warning(f"Channel {relayed['channel_id']} not accessible. Skipping.")
                                continue

                            message = await channel.fetch_message(int(relayed["message_id"]))
                            await message.add_reaction(reaction.emoji)
                            logging.info(f"Propagated reaction {reaction.emoji} to message ID: {relayed['message_id']} in channel {relayed['channel_id']}")
                        except Exception as e:
                            logging.error(f"Error propagating reaction to message ID {relayed['message_id']}: {e}")

                # Add reaction to the original message if not already triggered
                if str(reaction.message.id) != original_id:
                    try:
                        original_channel = client.get_channel(int(data["original_channel_id"]))
                        if original_channel:
                            original_message = await original_channel.fetch_message(int(original_id))
                            await original_message.add_reaction(reaction.emoji)
                            logging.info(f"Propagated reaction {reaction.emoji} to original message ID: {original_id}")
                    except discord.NotFound:
                        logging.warning(f"Original message {original_id} not found. Skipping reaction propagation to it.")
                    except Exception as e:
                        logging.error(f"Error propagating reaction to the original message ID {original_id}: {e}")

                return  # Exit after processing the match

        logging.warning(f"Message ID {reaction.message.id} not found in message_map. Cannot propagate reactions.")
    except Exception as e:
        logging.error(f"Error in on_reaction_add: {e}")

@client.event
async def on_reaction_remove(reaction, user):
    """
    Handles removing reactions from a message and propagates the removal to all relayed copies.
    """
    if user.bot:
        return  # Ignore bot reactions

    try:
        logging.info(f"Processing reaction {reaction.emoji} removed by {user.name} from message ID: {reaction.message.id}")

        # Locate the original message ID
        for original_id, data in message_map.items():
            relayed_messages = data["relayed_messages"]
            if any(str(reaction.message.id) == relayed["message_id"] for relayed in relayed_messages) or str(reaction.message.id) == original_id:
                logging.info(f"Match found for message ID: {reaction.message.id} (Original ID: {original_id})")

                # Propagate the reaction removal to all associated messages
                for relayed in relayed_messages:
                    if str(reaction.message.id) != relayed["message_id"]:  # Skip the triggering message
                        try:
                            channel = client.get_channel(int(relayed["channel_id"]))
                            if not channel:
                                logging.warning(f"Channel {relayed['channel_id']} not accessible. Skipping.")
                                continue

                            message = await channel.fetch_message(int(relayed["message_id"]))
                            await message.remove_reaction(reaction.emoji, user)
                            logging.info(f"Propagated reaction removal {reaction.emoji} from message ID: {relayed['message_id']} in channel {relayed['channel_id']}")
                        except Exception as e:
                            logging.error(f"Error propagating reaction removal to message ID {relayed['message_id']}: {e}")

                # Remove reaction from the original message if not already triggered
                if str(reaction.message.id) != original_id:
                    try:
                        original_channel = client.get_channel(int(data["original_channel_id"]))
                        if original_channel:
                            original_message = await original_channel.fetch_message(int(original_id))
                            await original_message.remove_reaction(reaction.emoji, user)
                            logging.info(f"Propagated reaction removal {reaction.emoji} to original message ID: {original_id}")
                    except discord.NotFound:
                        logging.warning(f"Original message {original_id} not found. Skipping reaction removal propagation to it.")
                    except Exception as e:
                        logging.error(f"Error propagating reaction removal to the original message ID {original_id}: {e}")

                return  # Exit after processing the match

        logging.warning(f"Message ID {reaction.message.id} not found in message_map. Cannot propagate reaction removals.")
    except Exception as e:
        logging.error(f"Error in on_reaction_remove: {e}")

@client.event
async def on_guild_remove(guild):
    """
    Handles bot removal from a guild, ensuring any associated data or configurations are cleaned up.
    """
    logging.info(f"Bot removed from server: {guild.name} (ID: {guild.id})")
    # Further cleanup logic (if required) can be added here

# -------------------------------------------------------------------------
# Role Management
# -------------------------------------------------------------------------

async def manage_role(guild):
    """
    Ensure the 'PDH LFG Bot' role exists in the guild and assign it to the bot.
    """
    try:
        # Check if the role exists
        role = discord.utils.get(guild.roles, name="PDH LFG Bot")
        
        # If not, create it
        if not role:
            role = await guild.create_role(name="PDH LFG Bot", mentionable=True)
            logging.info(f"Created role '{role.name}' in server '{guild.name}'")

        # Ensure the bot has the role
        if role not in guild.me.roles:
            await guild.me.add_roles(role)
            logging.info(f"Added role '{role.name}' to the bot in server '{guild.name}'")
    except discord.Forbidden:
        logging.warning(f"Missing permissions to manage roles in server '{guild.name}'")
    except discord.HTTPException as e:
        logging.error(f"Error managing role in server '{guild.name}': {e}")

# -------------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------------

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    """
    Assign a channel for cross-server communication and apply a filter.
    """
    filter = filter.lower()
    if filter not in ("casual", "cpdh"):
        await interaction.response.send_message("Invalid filter. Please specify 'casual' or 'cpdh'.", ephemeral=True)
        return

    webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
    WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = {'url': webhook.url, 'id': webhook.id}
    CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter
    save_webhook_data()
    save_channel_filters()
    await interaction.response.send_message(
        f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.", ephemeral=True
    )


@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    Remove a channel from the cross-server communication network.
    """
    channel_id = f'{interaction.guild.id}_{channel.id}'
    if channel_id in WEBHOOK_URLS:
        del WEBHOOK_URLS[channel_id]
        save_webhook_data()
        await interaction.response.send_message(f"Disconnected {channel.mention} from cross-server communication.",
                                                ephemeral=True)
    else:
        await interaction.response.send_message(f"{channel.mention} is not connected to cross-server communication.",
                                                ephemeral=True)


@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    """
    Display all active channel connections and their filters across servers.
    """
    try:
        if WEBHOOK_URLS:
            connections = "\n".join(
                [f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} "
                 f"(filter: {CHANNEL_FILTERS.get(channel, 'none')})"
                 for channel in WEBHOOK_URLS]
            )
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)

@client.tree.command(name="updateconfig", description="Reload the bot's configuration and resync commands.")
@has_permissions(administrator=True)
async def updateconfig(interaction: discord.Interaction):
    """
    Reload the bot's configuration from persistent storage, resynchronize commands,
    and provide feedback on updates.
    """
    try:
        # Acknowledge the interaction immediately to avoid expiration
        await interaction.response.defer(ephemeral=True)

        # Reload configuration files
        global WEBHOOK_URLS, CHANNEL_FILTERS
        WEBHOOK_URLS = load_webhook_data()
        CHANNEL_FILTERS = load_channel_filters()

        # Resynchronize the command tree
        await client.tree.sync()

        # Send follow-up message indicating success
        await interaction.followup.send(
            "Configuration reloaded successfully and command tree synchronized!",
            ephemeral=True
        )
        logging.info("Configuration reloaded and command tree synchronized successfully.")
    except Exception as e:
        logging.error(f"Error during /updateconfig: {e}")
        await interaction.followup.send(
            f"An error occurred while reloading configuration or syncing commands: {e}",
            ephemeral=True
        )

@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    """
    Display details about the bot, rules, and available commands.
    """
    try:
        embed = discord.Embed(
            title="PDH LFG Bot - Information & Commands",
            description=(
                "**Welcome to the PDH LFG Bot!**\n\n"
                "This bot facilitates cross-server communication and game coordination for Pauper EDH.\n"
                "If you experience issues, inform the server admin, reach out to Clay (User ID: 582548598584115211) on Discord, "
                "or email: gaming4tryhards@gmail.com.\n"
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Rules & Guidelines",
            value=(
                "1. **Be Respectful** - Treat all players with respect. Harassment, hate speech, or discrimination will not be tolerated.\n"
                "2. **No Cheating** - Players must adhere to Pauper EDH deck-building and gameplay rules. Rule violations may result in a ban.\n"
                "3. **Appropriate Content** - No NSFW content, excessive profanity, or disruptive behavior. Violators will be removed.\n"
                "4. **Follow Server Rules** - Each server may have additional rules. Abide by them alongside these rules.\n"
                "**Failure to comply with these rules may result in a user ID ban.**\n"
            ),
            inline=False
        )

        embed.add_field(
            name="Public Commands",
            value=(
                "- **/biglfg** - Create a cross-server LFG request.\n"
                "- **/about** - Show bot information and commands.\n"
                "- **/gamerequest** - Generate a TableStream test game.\n"
            ),
            inline=False
        )

        embed.add_field(
            name="Admin Commands",
            value=(
                "- **/setchannel (admin)** - Set a channel for cross-server communication.\n"
                "- **/disconnect (admin)** - Remove a channel from cross-server communication.\n"
                "- **/listconnections** - List connected channels for cross-server communication.\n"
                "- **/updateconfig (admin)** - Reload bot configuration and resync commands.\n"
                "- **/banuser (restricted)** - Ban a user from using bot services.\n"
                "- **/unbanuser (restricted)** - Unban a previously banned user.\n"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

@client.tree.command(name="gamerequest", description="Generate a test game request to verify TableStream integration.")
async def gamerequest(interaction: discord.Interaction):
    """
    Test command to generate a TableStream game request and display the link and password.
    """
    try:
        await interaction.response.defer(ephemeral=True)

        # Game data
        game_data = {
            "id": str(uuid.uuid4())  # Unique game ID
        }
        game_format = GameFormat.PAUPER_EDH
        player_count = 4

        logging.info(f"Preparing to generate TableStream link with game_data: {game_data}, game_format: {game_format}, player_count: {player_count}")

        # Generate TableStream link
        game_link, game_password = await generate_tablestream_link(game_data, game_format, player_count)

        # Handle the response
        if game_link:
            response_message = (
                f"**Game Request Generated Successfully!**\n\n"
                f"**Link:** {game_link}\n"
                f"**Password:** {game_password if game_password else 'No password required'}"
            )
        else:
            response_message = "Failed to generate the game request. Please check the configuration and try again."

        await interaction.followup.send(response_message, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /gamerequest command: {e}")
        await interaction.followup.send("An error occurred while processing the game request.", ephemeral=True)

@client.tree.command(name="biglfg", description="Create a cross-server LFG request.")
async def biglfg(interaction: discord.Interaction):
    """
    Handles the creation and propagation of BigLFG embeds across connected servers
    with rate-limit handling for multiple destinations.
    """
    try:
        await interaction.response.defer()

        # Generate a unique UUID for this LFG instance
        lfg_uuid = str(uuid.uuid4())

        source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

        # Create the initial embed
        embed = discord.Embed(
            title="Looking for more players...",
            color=discord.Color.yellow(),
            description="React below to join the game!",
        )
        embed.set_author(
            name="PDH LFG Bot",
            icon_url=IMAGE_URL,  # Add the image to the author section
            url="https://github.com/TryhardClay/PDH-LFG-Bot"
        )
        embed.set_thumbnail(url=IMAGE_URL)  # Add the image as a thumbnail
        embed.add_field(name="Players:", value=f"1. {interaction.user.name}", inline=False)

        # Track the BigLFG embed
        sent_messages = {}
        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')
            if source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none':
                destination_channel = client.get_channel(int(destination_channel_id.split('_')[1]))
                if destination_channel:
                    # Introduce a small delay to prevent rate-limiting
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                    sent_message = await destination_channel.send(embed=embed, view=create_lfg_view())
                    if sent_message:
                        sent_messages[destination_channel_id] = sent_message

        if sent_messages:
            active_embeds[lfg_uuid] = {
                "players": {interaction.user.id: interaction.user.name},
                "messages": sent_messages,
                "task": asyncio.create_task(lfg_timeout(lfg_uuid)),
            }
            await interaction.followup.send("BigLFG request sent successfully!", ephemeral=True)
        else:
            await interaction.followup.send("Failed to send BigLFG request to any channels.", ephemeral=True)

    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = int(e.response.headers.get("Retry-After", 1)) / 1000
            logging.warning(f"Rate limit hit during BigLFG command! Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
            await biglfg(interaction)
        else:
            logging.error(f"Discord API error in BigLFG command: {e}")
    except Exception as e:
        logging.error(f"Error in BigLFG command: {e}")
        try:
            await interaction.followup.send("An error occurred while processing the BigLFG request.", ephemeral=True)
        except discord.HTTPException as e:
            logging.error(f"Error sending error message: {e}")

# -------------------------------------------------------------------------
# Message Relay Loop
# -------------------------------------------------------------------------

async def message_relay_loop():
    """
    Main loop for handling message propagation across connected channels.
    Implements rate-limit-aware handling for all queued tasks.
    """
    while True:
        try:
            # Introduce a small delay to prevent excessive API calls
            await asyncio.sleep(RATE_LIMIT_DELAY)
            # Placeholder for additional logic if message queuing or advanced relay is added
        except Exception as e:
            logging.error(f"Error in message relay loop: {e}")

# -------------------------------------------------------------------------
# Start the Bot
# -------------------------------------------------------------------------

async def start_bot():
    """
    Asynchronous function to start the bot with rate-limit handling.
    """
    while True:
        try:
            logging.info("Starting the bot...")
            await client.start(TOKEN)
            break  # Exit the loop if successful
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = int(e.response.headers.get("Retry-After", 1)) / 1000
                logging.critical(f"Rate limit hit during bot start! Retrying after {retry_after} seconds.")
                await asyncio.sleep(retry_after)
            else:
                logging.critical(f"Discord API error while starting the bot: {e}")
                break
        except Exception as e:
            logging.critical(f"Critical error while starting the bot: {e}")
            break


if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except Exception as e:
        logging.critical(f"Unhandled error during bot initialization: {e}")
