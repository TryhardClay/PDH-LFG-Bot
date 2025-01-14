import discord
import aiohttp
import asyncio
import json
import os
import logging
import uuid
from discord.ext import commands
from discord.ext.commands import has_permissions
from discord.ui import Button, View
from cachetools import TTLCache

# -------------------------------------------------------------------------
# Setup and Configuration
# -------------------------------------------------------------------------

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a dictionary with a 24-hour expiration (in seconds)
relayed_text_messages = TTLCache(maxsize=10000, ttl=24 * 60 * 60)  # Max size, TTL, and 24-hour expiration

# BigLFG Embed Tracking
active_embeds = {}  # Independently managed

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

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()

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

# Text Message Relay
async def relay_text_message(source_message, destination_channel):
    """
    Relay a text message across servers using the Gateway API.
    Includes attribution to the original author and origin server.
    """
    try:
        # Format message attribution
        formatted_content = (
            f"{source_message.author.name} (from {source_message.guild.name}) said:\n"
            f"{source_message.content}"
        )

        # Send message to destination channel
        relayed_message = await destination_channel.send(content=formatted_content)

        # Log and track the relayed message
        unique_id = str(uuid.uuid4())
        relayed_text_messages[unique_id] = {
            "original_message": source_message,
            "relayed_message": relayed_message,
        }
        logging.info(f"Relayed text message to channel {destination_channel.id} with unique_id: {unique_id}")

        return unique_id
    except Exception as e:
        logging.error(f"Error relaying text message to channel {destination_channel.id}: {e}")
        return None

# Text Message Edit Propagation
async def propagate_text_edit(before, after):
    """
    Handle and propagate edits to text messages across servers.
    """
    try:
        logging.info(f"Processing edit for message ID: {before.id}")
        for unique_id, data in relayed_text_messages.items():
            if data["original_message"].id == before.id:
                # Apply edit to the relayed message
                relayed_message = data["relayed_message"]
                await relayed_message.edit(content=f"{after.author.name} (from {after.guild.name}) said:\n{after.content}")
                logging.info(f"Message edit propagated: {before.content} -> {after.content}")
                break
        else:
            logging.warning(f"Original message {before.id} not found in relayed_text_messages. Cannot propagate edits.")
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

        for unique_id, data in relayed_text_messages.items():
            if data["original_message"].id == reaction.message.id:
                # Propagate the reaction to all relayed copies
                relayed_message = data["relayed_message"]
                target_message = await relayed_message.channel.fetch_message(relayed_message.id)
                await target_message.add_reaction(reaction.emoji)
                logging.info(f"Propagated reaction {reaction.emoji} to channel {relayed_message.channel.id}")
                break
        else:
            logging.warning(f"Original message {reaction.message.id} not found in relayed_text_messages. Cannot propagate reactions.")
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
        data = active_embeds[lfg_uuid]
        players = data["players"]

        player_list = "\n".join([f"{i + 1}. {name}" for i, name in enumerate(players.values())]) if players else "Empty"

        for message in data["messages"].values():
            embed = discord.Embed(
                title="Looking for more players...",
                color=discord.Color.yellow() if len(players) < 4 else discord.Color.green(),
                description=f"React below ({4 - len(players)} players needed)" if len(players) < 4 else "Your game is ready!",
            )
            embed.add_field(name="Players:", value=player_list, inline=False)
            await message.edit(embed=embed)
    except Exception as e:
        logging.error(f"Error updating embeds for LFG UUID {lfg_uuid}: {e}")

# Helper to Create BigLFG View
def create_lfg_view():
    """
    Create and return a Discord UI View with JOIN and LEAVE buttons for the BigLFG embed.
    """
    view = discord.ui.View(timeout=15 * 60)  # 15-minute timeout

    async def join_button_callback(button_interaction: discord.Interaction):
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

    async def leave_button_callback(button_interaction: discord.Interaction):
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

        await button_interaction.response.defer()

    join_button = discord.ui.Button(style=discord.ButtonStyle.success, label="JOIN")
    leave_button = discord.ui.Button(style=discord.ButtonStyle.danger, label="LEAVE")

    join_button.callback = join_button_callback
    leave_button.callback = leave_button_callback

    view.add_item(join_button)
    view.add_item(leave_button)

    return view

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
        for unique_id, data in list(relayed_text_messages.items()):  # Use list() to avoid iteration issues
            if data["original_message"].id == message.id:
                # Delete all relayed copies
                logging.info(f"Deleting relayed messages for original message ID: {message.id}")
                relayed_message = data["relayed_message"]
                await relayed_message.delete()
                del relayed_text_messages[unique_id]
                logging.info(f"Successfully deleted all related relayed messages for unique_id: {unique_id}")
                break
        else:
            logging.warning(f"Original message {message.id} not found in relayed_text_messages. Cannot propagate deletion.")
    except Exception as e:
        logging.error(f"Error in on_message_delete: {e}")

@client.event
async def on_reaction_add(reaction, user):
    """
    Propagates reactions across all relayed copies of a message to maintain consistency.
    """
    await propagate_reaction_add(reaction, user)

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


@client.tree.command(name="updateconfig", description="Reload the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def updateconfig(interaction: discord.Interaction):
    """
    Reload the bot's configuration from persistent storage without restarting.
    """
    try:
        global WEBHOOK_URLS, CHANNEL_FILTERS
        WEBHOOK_URLS = load_webhook_data()
        CHANNEL_FILTERS = load_channel_filters()
        await interaction.response.send_message("Bot configuration reloaded successfully.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error reloading configuration: {e}")
        await interaction.response.send_message("An error occurred while reloading the configuration.", ephemeral=True)


@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    """
    Display details about the bot and its available commands.
    """
    try:
        embed = discord.Embed(
            title="Cross-Server Communication Bot",
            description="This bot allows you to connect channels in different servers to relay messages and facilitate communication.",
            color=discord.Color.blue()
        )
        embed.add_field(name="/setchannel",
                        value="Set a channel for cross-server communication and assign a filter ('casual' or 'cpdh').",
                        inline=False)
        embed.add_field(name="/disconnect", value="Disconnect a channel from cross-server communication.",
                        inline=False)
        embed.add_field(name="/listconnections", value="List all connected channels and their filters.", inline=False)
        embed.add_field(name="/updateconfig", value="Reload the bot's configuration and sync updates.", inline=False)
        embed.add_field(name="/biglfg", value="Create a cross-server LFG request.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)


@client.tree.command(name="biglfg", description="Create a cross-server LFG request.")
async def biglfg(interaction: discord.Interaction):
    """
    Handles the creation and propagation of BigLFG embeds across connected servers.
    """
    try:
        await interaction.response.defer()

        # Generate a unique UUID for this LFG instance
        lfg_uuid = str(uuid.uuid4())

        source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

        # Create the embed
        embed = discord.Embed(
            title="Looking for more players...",
            color=discord.Color.yellow(),
            description="React below to join the game!",
        )
        embed.add_field(name="Players:", value=f"1. {interaction.user.name}", inline=False)

        # Track the BigLFG embed
        sent_messages = {}
        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')
            if source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none':
                destination_channel = client.get_channel(int(destination_channel_id.split('_')[1]))
                if destination_channel:
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
    This function ensures messages are relayed between servers based on filters and configurations.
    """
    while True:
        await asyncio.sleep(1)  # Poll for new messages every second
        # Placeholder for additional logic if message queuing or advanced relay is added

# -------------------------------------------------------------------------
# Start the Bot
# -------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        logging.info("Starting the bot...")
        client.run(TOKEN)
    except Exception as e:
        logging.critical(f"Critical error while starting the bot: {e}")
