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
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"{CHANNEL_FILTERS_PATH} not found. Starting with empty channel filters.")
        return {}
    except Exception as e:
        logging.error(f"Error loading channel filters from {CHANNEL_FILTERS_PATH}: {e}")
        return {}

# -------------------------------------------------------------------------
# Global Variables
# -------------------------------------------------------------------------

# Load webhook URLs and channel filters
WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()

# Initialize the bot with the appropriate intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.members = True        # Enable member intent
client = commands.Bot(command_prefix="!", intents=intents)

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

async def send_webhook_message(webhook_url, content=None, embeds=None, username=None, avatar_url=None, view=None):
    async with aiohttp.ClientSession() as session:
        data = {}
        if content:
            data['content'] = content
        if embeds:
            data['embeds'] = embeds
        if username:
            data['username'] = username
        if avatar_url:
            data['avatar_url'] = avatar_url
        try:
            async with session.post(webhook_url, json=data) as response:
                if response.status == 204:
                    logging.info("Message sent successfully.")
                elif response.status == 429:
                    logging.warning("Rate limited!")
                    # Implement rate limit handling
                    retry_after = float(response.headers.get("Retry-After", 1))
                    logging.warning(f"Retrying in {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    return await send_webhook_message(webhook_url, content, embeds, username, avatar_url, view)  # Retry
                else:
                    logging.error(f"Failed to send message. Status code: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logging.error(f"Error sending webhook message: {e}")
            return None

# -------------------------------------------------------------------------
# Bot Initialization 
# -------------------------------------------------------------------------

# Initialize the bot with the appropriate intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.members = True        # Enable member intent
client = commands.Bot(command_prefix="!", intents=intents) 

# -------------------------------------------------------------------------
# Event Handlers
# -------------------------------------------------------------------------

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    await client.tree.sync()
    message_relay_loop.start()  # Start the loop here

@client.event
async def on_guild_join(guild):
    # This event is called when the bot joins a guild (server).
    # You can use this to send a welcome message or set up initial configurations.
    logging.info(f"Joined guild: {guild.name}")

@client.event
async def on_guild_remove(guild):
    # This event is called when the bot leaves a guild (server).
    # You can use this to clean up any resources or data related to that guild.
    logging.info(f"Left guild: {guild.name}")
    # Remove webhooks associated with the guild
    to_remove = [guild_id for guild_id in WEBHOOK_URLS.keys() if guild_id.startswith(str(guild.id))]
    for guild_id in to_remove:
        del WEBHOOK_URLS[guild_id]
    save_webhook_data()


# -------------------------------------------------------------------------
# Event Handlers for Buttons
# -------------------------------------------------------------------------

@client.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        # Check if the interaction is from a button click
        if interaction.component.custom_id == "join_button":
            # Handle the "Join" button click
            await interaction.response.send_message("You clicked the Join button!", ephemeral=True)
        elif interaction.component.custom_id == "leave_button":
            # Handle the "Leave" button click
            await interaction.response.send_message("You clicked the Leave button!", ephemeral=True)
    await client.process_application_commands(interaction)

# -------------------------------------------------------------------------
# Role Management
# -------------------------------------------------------------------------

async def manage_role(guild):
    """
    Manages the bot's role in the given guild to ensure it has the necessary permissions.
    """
    logging.info(f"Managing role in guild: {guild.name}")
    bot_member = guild.get_member(client.user.id)
    if not bot_member:
        logging.error(f"Unable to find bot member in guild: {guild.name}")
        return

    # Check for existing "BigLFG" role
    role_name = "BigLFG"
    role = discord.utils.get(guild.roles, name=role_name)

    if not role:
        # Create the role if it doesn't exist
        try:
            permissions = discord.Permissions(permissions=268435456)  # Adjust permissions as needed
            role = await guild.create_role(name=role_name, permissions=permissions)
            logging.info(f"Created role '{role_name}' in guild: {guild.name}")
        except discord.Forbidden:
            logging.error(f"Missing permissions to create role in guild: {guild.name}")
            return

    # Assign the role to the bot
    try:
        await bot_member.add_roles(role)
        logging.info(f"Added role '{role_name}' to bot in guild: {guild.name}")
    except discord.Forbidden:
        logging.error(f"Missing permissions to add role to bot in guild: {guild.name}")

# -------------------------------------------------------------------------
# Bot Commands
# -------------------------------------------------------------------------

@client.tree.command(name="biglfg")
async def biglfg(interaction: discord.Interaction):
    """
    Create a BigLFG game in all connected channels.
    """
    try:
        await interaction.response.defer()  # Acknowledge the interaction

        # Get game info from user (using channel name for now)
        game = interaction.channel.name  

        # Create the embed
        embed = discord.Embed(
            title="BigLFG",
            description=f"**Game:** {game}",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Click the button to join!")

        # Create buttons
        join_button = discord.ui.Button(label="Join", style=discord.ButtonStyle.green, custom_id="join_button")
        leave_button = discord.ui.Button(label="Leave", style=discord.ButtonStyle.red, custom_id="leave_button")

        # Create a view to hold the buttons
        view = discord.ui.View()
        view.add_item(join_button)
        view.add_item(leave_button)

        # Send the embed to all connected channels
        for channel_id, webhook_data in WEBHOOK_URLS.items():
            try:
                channel = client.get_channel(int(channel_id.split('_')[1]))
                webhook = discord.Webhook.from_url(webhook_data['url'], session=client._session)
                message = await webhook.send(
                    embeds=[embed.to_dict()],
                    username=f"{interaction.user.name} from {interaction.guild.name}",
                    avatar_url=interaction.user.avatar.url if interaction.user.avatar else None,
                    view=view
                )
                # Store the message ID for later updates or deletion if necessary
                WEBHOOK_URLS[channel_id]['last_message_id'] = message.id
                save_webhook_data()

            except discord.HTTPException as e:
                logging.error(f"Failed to send message to channel {channel_id}: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")

        await interaction.followup.send("BigLFG message sent to all connected channels!", ephemeral=True)

    except Exception as e:
        logging.error(f"An error occurred in biglfg command: {e}")
        await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)


@client.tree.command(name="connect")
@has_permissions(manage_channels=True)
async def connect(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    Connects a channel to the BigLFG system.
    """
    try:
        await interaction.response.defer()
        webhook = await channel.create_webhook(name="BigLFG Webhook")
        WEBHOOK_URLS[f"{interaction.guild.id}_{channel.id}"] = {
            "url": webhook.url,
            "last_message_id": None
        }
        save_webhook_data()
        await interaction.followup.send(f"Channel {channel.mention} connected to BigLFG!", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to create webhooks in that channel.", ephemeral=True)
    except Exception as e:
        logging.error(f"An error occurred in connect command: {e}")
        await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)


@client.tree.command(name="disconnect")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    Disconnects a channel from the BigLFG system.
    """
    try:
        await interaction.response.defer()
        channel_id = f"{interaction.guild.id}_{channel.id}"
        if channel_id in WEBHOOK_URLS:
            # Optionally delete the webhook here 
            # webhook = discord.Webhook.from_url(WEBHOOK_URLS[channel_id]["url"], session=client._session)
            # await webhook.delete()  
            del WEBHOOK_URLS[channel_id]
            save_webhook_data()
            await interaction.followup.send(f"Channel {channel.mention} disconnected from BigLFG!", ephemeral=True)
        else:
            await interaction.followup.send("That channel is not connected to BigLFG.", ephemeral=True)
    except Exception as e:
        logging.error(f"An error occurred in disconnect command: {e}")
        await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)

@client.tree.command(name="show_connections")
@has_permissions(manage_channels=True)
async def show_connections(interaction: discord.Interaction):
    """
    Shows the channels connected to the BigLFG system in this server.
    """
    try:
        await interaction.response.defer()
        connected_channels = []
        for channel_id in WEBHOOK_URLS.keys():
            guild_id, channel_id = channel_id.split('_')
            if int(guild_id) == interaction.guild.id:
                channel = client.get_channel(int(channel_id))
                if channel:
                    connected_channels.append(channel.mention)
        if connected_channels:
            await interaction.followup.send(f"Connected channels: {', '.join(connected_channels)}", ephemeral=True)
        else:
            await interaction.followup.send("No channels are connected to BigLFG in this server.", ephemeral=True)
    except Exception as e:
        logging.error(f"An error occurred in show_connections command: {e}")
        await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)

# -------------------------------------------------------------------------
# Event Handlers for Buttons
# -------------------------------------------------------------------------

@client.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        # Check if the interaction is from a button click
        if interaction.component.custom_id == "join_button":
            # Handle the "Join" button click
            await interaction.response.send_message("You clicked the Join button!", ephemeral=True)
        elif interaction.component.custom_id == "leave_button":
            # Handle the "Leave" button click
            await interaction.response.send_message("You clicked the Leave button!", ephemeral=True)
    await client.process_application_commands(interaction)


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
                pass
        except Exception as e:
            logging.error(f"Error in message relay loop: {e}")


# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
