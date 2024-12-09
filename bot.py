import discord
import re
import aiohttp
import asyncio
import json
import os
import logging
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

WEBHOOK_URLS = {}  # Initialize as an empty dictionary
CHANNEL_FILTERS = {}  # Dictionary to store channel filters

# Ensure webhooks.json exists and is valid JSON
try:
    with open('webhooks.json', 'r') as f:
        WEBHOOK_URLS = json.load(f)
except FileNotFoundError:
    with open('webhooks.json', 'w') as f:
        json.dump({}, f)
except json.decoder.JSONDecodeError as e:
    logging.error(f"Error decoding JSON from webhooks.json: {e}")
    with open('webhooks.json', 'w') as f:
        json.dump({}, f)

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = commands.Bot(command_prefix='/', intents=intents)

# Global variable to keep track of the main message handling task
message_relay_task = None

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

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    await client.tree.sync()
    global message_relay_task
    # Start the message relay task in the background
    if not message_relay_task:
        message_relay_task = asyncio.create_task(message_relay_loop())

    # Load the lfg extension
    try:
        await client.load_extension("lfg")
        logging.info("LFG extension loaded.")
    except Exception as e:
        logging.error(f"Failed to load LFG extension: {e}")

@client.event
async def on_guild_join(guild):
    try:
        bot_role = await guild.create_role(name=client.user.name, mentionable=True)
        logging.info(f"Created role {bot_role.name} in server {guild.name}")
        try:
            await guild.me.add_roles(bot_role)
            logging.info(f"Added role {bot_role.name} to the bot in server {guild.name}")
        except discord.Forbidden:
            logging.warning(f"Missing permissions to add role to the bot in server {guild.name}")
    except discord.Forbidden:
        logging.warning(f"Missing permissions to create role in server {guild.name}")

    for channel in guild.text_channels:
        try:
            await channel.send("Hello! I'm your cross-server communication bot. "
                               "An admin needs to use the `/setchannel` command to "
                               "choose a channel for relaying messages.")
            break
        except discord.Forbidden:
            continue

# ... (rest of your commands and events)

async def message_relay_loop():
    while True:
        try:
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in message relay loop: {e}")

@client.event
async def on_message(message):
    # ... (your on_message logic)

@client.event
async def on_guild_remove(guild):
    # ... (your on_guild_remove logic)

@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    # ... (your about logic)

client.run(TOKEN)
