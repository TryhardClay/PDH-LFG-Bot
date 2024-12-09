# bot.py
import discord
import aiohttp
import asyncio
import json
import os
import logging
from discord.ext import commands

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

# Initialize global variables
WEBHOOK_URLS = {}  # Dictionary to store webhook URLs
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

# Import modules
import commands  # Import your commands module
import events  # Import your events module
import biglfg  # Import your biglfg module

# Load extensions (if using cogs)
# client.load_extension("commands")
# client.load_extension("events")
# client.load_extension("biglfg")

client.run(TOKEN)
