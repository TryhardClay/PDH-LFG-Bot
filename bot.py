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

# Persistent storage path (using your SSD mount path)
PERSISTENT_DATA_PATH = '/var/data/webhooks.json'

# Load webhook data from persistent storage with validation
def load_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'r') as f:
            data = json.load(f)
            # More robust validation
            if isinstance(data, dict) and all(isinstance(key, str) and isinstance(value, dict) 
                                             and "url" in value and isinstance(value["url"], str) 
                                             and "id" in value and isinstance(value["id"], int) 
                                             and "filter" in value and isinstance(value["filter"], str) 
                                             for key, value in data.items()):
                return data
            else:
                logging.error(f"Invalid data format in {PERSISTENT_DATA_PATH}")
                return {}
    except FileNotFoundError:
        return {}  # Initialize if the file doesn't exist
    except json.decoder.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {PERSISTENT_DATA_PATH}: {e}")
        return {}

WEBHOOK_URLS = load_webhook_data()

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

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
                    # TODO: Implement more sophisticated rate limit handling
                else:
                    logging.error(f"Failed to send message. Status code: {response.status}")
        except aiohttp.ClientError as e:
            logging.error(f"Error sending webhook message: {e}")

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
        source_filter = WEBHOOK_URLS[source_channel_id]['filter'] # Get filter directly from WEBHOOK_URLS

        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            if source_channel_id != destination_channel_id:
                destination_filter = webhook_data['filter'] # Get filter directly from WEBHOOK_URLS

                if source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none':
                    await send_webhook_message(
                        webhook_data['url'],
                        content=content,
                        embeds=embeds,
                        username=f"{message.author.name} from {message.guild.name}",
                        avatar_url=message.author.avatar.url if message.author.avatar else None
                    )

    for reaction in message.reactions:
        try:
            await reaction.message.add_reaction(reaction.emoji)
        except discord.HTTPException as e:
            logging.error(f"Error adding reaction: {e}")

@client.event
async def on_guild_remove(guild):
    pass  # Role management is handled elsewhere

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

# ... (Assuming the /setchannel command is already defined above) ...

@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        channel_id = f'{interaction.guild.id}_{channel.id}'
        if channel_id in WEBHOOK_URLS:
            webhook_url = WEBHOOK_URLS[channel_id]['url']
            webhook_id = WEBHOOK_URLS[channel_id]['id']

            # Delete the webhook
            async with aiohttp.ClientSession() as session:
                async with session.delete(f"{webhook_url}/{webhook_id}") as resp:
                    if resp.status == 204: 
                        logging.info(f"Webhook deleted: {webhook_url}")
                    else:
                        logging.error(f"Failed to delete webhook: {webhook_url}")

            del WEBHOOK_URLS[channel_id]
            save_webhook_data()

            await interaction.response.send_message(
                f"Channel {channel.mention} disconnected from cross-server communication.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Channel {channel.mention} is not connected to cross-server communication.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error disconnecting channel: {e}")
        await interaction.response.send_message("An error occurred while disconnecting the channel.", ephemeral=True)

@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    try:
        if WEBHOOK_URLS:
            connections = "\n".join(
                [f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} (filter: {WEBHOOK_URLS[channel]['filter']})"
                 for channel in WEBHOOK_URLS])
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)

@client.tree.command(name="resetconfig", description="Reload the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def resetconfig(interaction: discord.Interaction):
    try:
        # Reload webhooks.json
        global WEBHOOK_URLS
        WEBHOOK_URLS = load_webhook_data()  # Use the load_webhook_data function

        if interaction.response.is_done():
            await interaction.followup.send("Bot configuration reloaded.", ephemeral=True)
        else:
            await interaction.response.send_message("Bot configuration reloaded.", ephemeral=True)

    except Exception as e:
        logging.error(f"Error reloading configuration: {e}")
        if interaction.response.is_done():
            await interaction.followup.send("An error occurred while reloading the configuration.", ephemeral=True)
        else:
            await interaction.response.send_message("An error occurred while reloading the configuration.",
                                                    ephemeral=True)

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
        embed.add_field(name="/resetconfig",
                        value="Reload the bot's configuration (for debugging/development).", inline=False)
        embed.add_field(name="/about", value="Show this information.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def save_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data to {PERSISTENT_DATA_PATH}: {e}")

# -------------------------------------------------------------------------
# Message Relay Loop
# -------------------------------------------------------------------------

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

# -------------------------------------------------------------------------
# Run the Bot
# -------------------------------------------------------------------------

client.run(TOKEN)
