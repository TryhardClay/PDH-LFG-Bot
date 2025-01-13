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
active_embeds = {
    "embed_id": {
        "players": ["Player1"],
        "task": None,  # This will be replaced with an asyncio.Task object
        "messages": {},  # Initialize as an empty dictionary to be populated later
    }
}

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
            logging.error(f"Unexpected error occurred: {e}")

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
async def on_reaction_add(reaction, user):
    """Handle player reactions to active LFG embeds."""
    if user.bot:
        return  # Ignore bot reactions

    # Iterate through all active embeds to find the matching one
    for embed_id, data in active_embeds.items():
        # Check if the reaction message matches one of the tracked messages
        if reaction.message.id in [msg.id for msg in data["messages"].values()]:
            if str(reaction.emoji) == "👍":
                # Add the user to the player list if not already in it
                if user.name not in data["players"]:
                    data["players"].append(user.name)
                    await update_embeds(embed_id)  # Update all embeds for this LFG request

                    # Check if the maximum player limit is reached
                    if len(data["players"]) == 4:
                        await lfg_complete(embed_id)

            elif str(reaction.emoji) == "👎":
                # Remove the user from the player list if present
                if user.name in data["players"]:
                    data["players"].remove(user.name)
                    await update_embeds(embed_id)  # Update all embeds for this LFG request

            break  # Stop checking other embeds once a match is found

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

        source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')
        initiating_player = interaction.user.name

        embed = discord.Embed(title="Looking for more players...", color=discord.Color.yellow())
        embed.set_footer(text="React with 👍 to join! React with 👎 to leave. (3 players needed)")
        embed.add_field(name="Players:", value=f"1. {initiating_player}", inline=False)

        sent_messages = {}

        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')

            if source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none':
                try:
                    message = await send_webhook_message(
                        webhook_data['url'],
                        embeds=[embed.to_dict()],
                        username=f"{interaction.user.name} from {interaction.guild.name}",
                        avatar_url=interaction.user.avatar.url if interaction.user.avatar else None
                    )
                    if message:
                        sent_messages[destination_channel_id] = message
                except Exception as e:
                    logging.error(f"Error sending LFG request to {destination_channel_id}: {e}")

        if sent_messages:
            embed_id = list(sent_messages.values())[0].id
            active_embeds[embed_id] = {
                "players": [initiating_player],
                "channels": list(sent_messages.keys()),
                "messages": sent_messages,
                "task": asyncio.create_task(lfg_timeout(embed_id)),
            }

            await interaction.followup.send("LFG request sent across channels.", ephemeral=True)
        else:
            await interaction.followup.send("Failed to send LFG request to any channels.", ephemeral=True)

    except Exception as e:
        logging.error(f"Error in /biglfg command: {e}")
        await interaction.followup.send("An error occurred while processing the LFG request.", ephemeral=True)

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
    """Update all related embeds with the current player list."""
    data = active_embeds[embed_id]
    players = data["players"]

    # Iterate through all messages for this embed ID
    for channel_id, message in data["messages"].items():
        try:
            # Create an updated embed with the current player list
            if len(players) < 4:
                embed = discord.Embed(
                    title="Looking for more players...",
                    color=discord.Color.yellow(),
                    description=f"React with 👍 to join! React with 👎 to leave. ({4 - len(players)} players needed)",
                )
            else:
                embed = discord.Embed(title="Your game is ready!", color=discord.Color.green())

            # Add the player list to the embed
            embed.add_field(
                name="Players:",
                value="\n".join([f"{i + 1}. {name}" for i, name in enumerate(players)]),
                inline=False,
            )

            # Update the embed in the current channel
            await message.edit(embed=embed)
        except Exception as e:
            logging.error(f"Error updating embed in channel {channel_id}: {e}")

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
        for channel_id, message in data["messages"].items():
            try:
                embed = discord.Embed(title="This request has timed out.", color=discord.Color.red())
                await message.edit(embed=embed)
            except Exception as e:
                logging.error(f"Error updating embed on timeout in channel {channel_id}: {e}")

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
