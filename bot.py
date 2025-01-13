import discord
import aiohttp
import asyncio
import json
import os
import logging
import uuid
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.ui import Button, View
from cachetools import TTLCache

# -------------------------------------------------------------------------
# Setup and Configuration
# -------------------------------------------------------------------------

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a dictionary with a 24-hour expiration (in seconds)
relayed_messages = TTLCache(maxsize=10000, ttl=24 * 60 * 60)  # Max size and TTL

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
active_embeds = {}

# Define intents (includes messages intent)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True

client = commands.Bot(command_prefix='/', intents=intents)

# Global variable to keep track of the main message handling task
message_relay_task = None

# PROGRAMMING NOTES
# The cross server messaging feature is ALWAYS handled via webhooks for ease of programming and code simplicity.
# - See: "Webhook Functions" and "Message Relay Loop"
# The BIGLFG embed functionality is ALWAYS handled via dynamic gateway processes to ensure preferred performance.
# - See: "/biglfg Command" and "Dynamic Updates for Embeds"

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

async def relay_message(source_message, destination_channel):
    """
    Relay a message from one server/channel to another and store its UUID.
    """
    try:
        unique_id = str(uuid.uuid4())  # Generate a unique UUID for the message
        relayed_message = await destination_channel.send(content=source_message.content)

        # Ensure both the original and relayed messages are tracked
        relayed_messages[unique_id] = {
            "original_message_id": source_message.id,
            "relayed_message_ids": [relayed_message.id],  # Start tracking with the first relayed message
        }

        logging.info(f"Message relayed from {source_message.channel.name} to {destination_channel.name}.")
        logging.info(f"Stored UUID {unique_id} for original message {source_message.id}.")

        return unique_id
    except discord.Forbidden:
        logging.error(f"Missing permissions to send a message in {destination_channel.name}.")
    except discord.HTTPException as e:
        logging.error(f"Failed to relay message to {destination_channel.name}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in relay_message: {e}")

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
    if message.author == client.user:
        return

    if message.webhook_id and message.author.id != client.user.id:
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
                        message = await send_webhook_message(
                            webhook_data['url'],
                            content=content,
                            embeds=embeds,
                            username=f"{message.author.name} from {message.guild.name}",
                            avatar_url=message.author.avatar.url if message.author.avatar else None
                        )
                        
                        # This is the fix for the 'NoneType' object error
                        if message is not None:     
                            for reaction in message.reactions:
                                try:
                                    await reaction.message.add_reaction(reaction.emoji)
                                except discord.HTTPException as e:
                                    logging.error(f"Error adding reaction: {e}")

                    except Exception as e:
                        logging.error(f"Error relaying message: {e}")

@client.event
async def on_message_edit(before, after):
    """Handle editing of an original message and propagate changes to relayed messages."""
    found_uuid = None

    # Find the UUID associated with the edited message
    for unique_id, data in relayed_messages.items():
        if data["original_message_id"] == before.id:
            found_uuid = unique_id
            break

    if not found_uuid:
        logging.warning(f"Original message {before.id} not found in relayed_messages. Cannot propagate edits.")
        return

    # Propagate edits to relayed messages
    try:
        data = relayed_messages[found_uuid]
        for relayed_id in data["relayed_message_ids"]:
            for channel in client.get_all_channels():
                if isinstance(channel, discord.TextChannel):
                    try:
                        relayed_message = await channel.fetch_message(relayed_id)
                        await relayed_message.edit(content=after.content)
                        logging.info(f"Edited relayed message {relayed_id} in {channel.name}.")
                    except discord.NotFound:
                        logging.warning(f"Message {relayed_id} not found in channel {channel.name}. Skipping.")
                    except discord.Forbidden:
                        logging.error(f"Missing permissions to edit message {relayed_id} in {channel.name}.")
                    except Exception as e:
                        logging.error(f"Error editing relayed message {relayed_id} in {channel.name}: {e}")
    except KeyError:
        logging.error(f"UUID {found_uuid} unexpectedly missing from relayed_messages.")
    except Exception as e:
        logging.error(f"Unexpected error in on_message_edit: {e}")

@client.event
async def on_message_delete(message):
    """Handle deletion of an original message and propagate deletions to relayed messages."""
    found_uuid = None

    # Locate the UUID associated with the deleted message
    for unique_id, data in relayed_messages.items():
        if data["original_message_id"] == message.id:
            found_uuid = unique_id
            break

    if not found_uuid:
        logging.warning(f"Original message {message.id} not found in relayed_messages. Cannot propagate deletions.")
        return

    # Propagate deletions to relayed messages
    try:
        data = relayed_messages[found_uuid]
        for relayed_id in data["relayed_message_ids"]:
            for channel in client.get_all_channels():
                if isinstance(channel, discord.TextChannel):
                    try:
                        relayed_message = await channel.fetch_message(relayed_id)
                        await relayed_message.delete()
                        logging.info(f"Deleted relayed message {relayed_id} in {channel.name}.")
                    except discord.NotFound:
                        logging.warning(f"Message {relayed_id} not found in channel {channel.name}. Skipping.")
                    except discord.Forbidden:
                        logging.error(f"Missing permissions to delete message {relayed_id} in {channel.name}.")
                    except Exception as e:
                        logging.error(f"Error deleting relayed message {relayed_id} in {channel.name}: {e}")

        # Remove the UUID entry from relayed_messages
        del relayed_messages[found_uuid]
        logging.info(f"Removed UUID {found_uuid} from relayed_messages after deletion.")
    except KeyError:
        logging.error(f"UUID {found_uuid} unexpectedly missing from relayed_messages.")
    except Exception as e:
        logging.error(f"Unexpected error in on_message_delete: {e}")

@client.event
async def on_reaction_add(reaction, user):
    """Handle player reactions to active LFG embeds."""
    if user.bot:
        return  # Ignore bot reactions

    # Fetch the message to ensure we are working with the latest data
    try:
        message = reaction.message
        if message.id not in active_embeds:
            logging.info(f"Reaction ignored: Message ID {message.id} not in active embeds.")
            return

        embed_data = active_embeds[message.id]

        # Handle 👍 reaction
        if str(reaction.emoji) == "👍":
            if user.name not in embed_data["players"]:
                embed_data["players"].append(user.name)
                logging.info(f"Added {user.name} to the player list for embed {message.id}.")
                await update_embeds(message.id)

                # If the player limit is reached, complete the LFG request
                if len(embed_data["players"]) == 4:
                    await lfg_complete(message.id)

        # Handle 👎 reaction
        elif str(reaction.emoji) == "👎":
            if user.name in embed_data["players"]:
                embed_data["players"].remove(user.name)
                logging.info(f"Removed {user.name} from the player list for embed {message.id}.")
                await update_embeds(message.id)

    except Exception as e:
        logging.error(f"Error in on_reaction_add: {e}")

@client.event
async def on_guild_remove(guild):
    pass  # Role management is handled elsewhere

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
        f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.", ephemeral=True)


@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
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
    try:
        if WEBHOOK_URLS:
            connections = "\n".join(
                [f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} "
                 f"(filter: {CHANNEL_FILTERS.get(channel, 'none')})"
                 for channel in WEBHOOK_URLS])
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)


@client.tree.command(name="updateconfig", description="Reload the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def updateconfig(interaction: discord.Interaction):
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
        embed.add_field(name="/updateconfig", value="Reload the bot's configuration and sync updates.", inline=False)
        embed.add_field(name="/biglfg", value="Create a cross-server LFG request.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

@client.tree.command(name="biglfg", description="Create a cross-server LFG request.")
async def biglfg(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        # Generate a unique UUID for this LFG instance
        lfg_uuid = str(uuid.uuid4())

        source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')
        initiating_player = interaction.user

        # Create the embed
        embed = discord.Embed(
            title="Looking for more players...",
            color=discord.Color.yellow()
        )
        embed.set_footer(text="REACT BELOW (3 players needed)")
        embed.add_field(
            name="Players:",
            value=f"1. {initiating_player.name}",
            inline=False
        )

        # Define the buttons
        view = discord.ui.View(timeout=15 * 60)  # 15-minute timeout

        async def join_button_callback(button_interaction: discord.Interaction):
            if lfg_uuid not in active_embeds:
                await button_interaction.response.send_message("This LFG request is no longer active.", ephemeral=True)
                return

            user_id = button_interaction.user.id
            display_name = button_interaction.user.name

            if user_id not in active_embeds[lfg_uuid]["players"]:
                active_embeds[lfg_uuid]["players"][user_id] = display_name
                await update_embeds(lfg_uuid)

            await button_interaction.response.defer()

        async def leave_button_callback(button_interaction: discord.Interaction):
            if lfg_uuid not in active_embeds:
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

        # Distribute the embed to all channels
        sent_messages = {}

        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')

            if source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none':
                channel = client.get_channel(int(destination_channel_id.split('_')[1]))
                if channel:
                    sent_message = await channel.send(embed=embed, view=view)
                    sent_messages[destination_channel_id] = sent_message

        # Store active embed data
        if sent_messages:
            active_embeds[lfg_uuid] = {
                "players": {initiating_player.id: initiating_player.name},
                "messages": sent_messages,
                "task": asyncio.create_task(lfg_timeout(lfg_uuid)),
            }

            await interaction.followup.send("LFG request sent across channels.", ephemeral=True)
        else:
            await interaction.followup.send("Failed to send LFG request to any channels.", ephemeral=True)

    except Exception as e:
        logging.error(f"Error in /biglfg command: {e}")
        try:
            await interaction.followup.send("An error occurred while processing the LFG request.", ephemeral=True)
        except discord.HTTPException as e:
            logging.error(f"Error sending error message: {e}")

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def save_webhook_data():
    """Save the current webhook data to persistent storage."""
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data to {PERSISTENT_DATA_PATH}: {e}")


def save_channel_filters():
    """Save the current channel filters to persistent storage."""
    try:
        with open(CHANNEL_FILTERS_PATH, 'w') as f:
            json.dump(CHANNEL_FILTERS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving channel filters to {CHANNEL_FILTERS_PATH}: {e}")

async def update_embeds(embed_id):
    data = active_embeds[embed_id]
    players = data["players"]  # Should always be a dictionary

    # Prepare the player list display or default to "Empty"
    if not players:
        player_list = "Empty"
    else:
        player_list = "\n".join([f"{i + 1}. {name}" for i, name in enumerate(players.values())])

    for channel_id, message in data["messages"].items():
        try:
            embed = discord.Embed(
                title="Looking for more players...",
                color=discord.Color.yellow() if len(players) < 4 else discord.Color.green(),
                description=f"REACT BELOW ({4 - len(players)} players needed)" if len(players) < 4 else "Your game is ready!",
            )
            embed.add_field(name="Players:", value=player_list, inline=False)
            await message.edit(embed=embed)
        except Exception as e:
            logging.error(f"Error updating embed in channel {channel_id}: {e}")

async def join_button_callback(button_interaction: discord.Interaction):
    embed_id = button_interaction.message.id
    if embed_id in active_embeds:
        data = active_embeds[embed_id]
        players = data["players"]  # Should always be a dictionary
        user_id = button_interaction.user.id

        if user_id not in players:
            players[user_id] = button_interaction.user.name
            logging.info(f"Added {button_interaction.user.name} to the player list for embed {embed_id}.")
            await update_embeds(embed_id)
            await button_interaction.response.send_message("You've joined the game!", ephemeral=True)
        else:
            await button_interaction.response.send_message("You're already in the player list.", ephemeral=True)
    else:
        await button_interaction.response.send_message("This game is no longer active.", ephemeral=True)


async def leave_button_callback(button_interaction: discord.Interaction):
    embed_id = button_interaction.message.id
    if embed_id in active_embeds:
        data = active_embeds[embed_id]
        players = data["players"]  # Should always be a dictionary
        user_id = button_interaction.user.id

        if user_id in players:
            del players[user_id]
            logging.info(f"Removed {button_interaction.user.name} from the player list for embed {embed_id}.")
            await update_embeds(embed_id)
            await button_interaction.response.send_message("You've left the game.", ephemeral=True)
        else:
            await button_interaction.response.send_message("You are not in the player list.", ephemeral=True)
    else:
        await button_interaction.response.send_message("This game is no longer active.", ephemeral=True)

async def lfg_complete(embed_id):
    """Mark the LFG request as complete."""
    data = active_embeds.pop(embed_id)
    for channel_id, message in data["messages"].items():
        try:
            embed = discord.Embed(title="Your game is ready!", color=discord.Color.green())
            embed.add_field(
                name="Players:",
                value="\n".join([f"{i + 1}. {name}" for i, name in enumerate(data["players"])]),
                inline=False,
            )
            await message.edit(embed=embed)
        except Exception as e:
            logging.error(f"Error completing LFG request in channel {channel_id}: {e}")


async def lfg_timeout(embed_id):
    """Handle timeout for an LFG embed."""
    await asyncio.sleep(15 * 60)  # Wait 15 minutes
    if embed_id in active_embeds:
        data = active_embeds.pop(embed_id)
        for message in data["messages"].values():
            try:
                embed = discord.Embed(title="This request has timed out.", color=discord.Color.red())
                await message.edit(embed=embed, view=None)
            except Exception as e:
                logging.error(f"Error updating embed on timeout: {e}")

# -------------------------------------------------------------------------
# Message Relay Loop
# -------------------------------------------------------------------------

async def message_relay_loop():
    """Main loop for relaying messages between connected channels."""
    while True:
        await asyncio.sleep(1)  # Check for new messages every second

        # Add your logic for relaying messages if necessary
        # For example, managing a message queue or processing incoming data

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
