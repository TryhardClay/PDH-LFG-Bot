import discord
import re
import aiohttp
import asyncio
import json
import os
from discord.ext import commands
from discord.ext.commands import has_permissions

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

WEBHOOK_URLS = {}  # Initialize as an empty dictionary

# Ensure webhooks.json exists and is valid JSON
try:
    with open('webhooks.json', 'r') as f:
        WEBHOOK_URLS = json.load(f)
except FileNotFoundError:
    with open('webhooks.json', 'w') as f:
        json.dump({}, f)  # Create an empty JSON object if the file doesn't exist
except json.decoder.JSONDecodeError as e:
    print(f"Error decoding JSON from webhooks.json: {e}")
    with open('webhooks.json', 'w') as f:
        json.dump({}, f)  # Overwrite with an empty JSON object if there's an error

# Define intents (only the necessary ones)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Required for on_guild_join

# Use commands.Bot instead of Client
client = commands.Bot(command_prefix='/', intents=intents)

async def send_webhook_message(webhook_url, content, username=None, avatar_url=None):
    async with aiohttp.ClientSession() as session:
        data = {
            'content': content
        }
        if username:
            data['username'] = username
        if avatar_url:
            data['avatar_url'] = avatar_url
        async with session.post(webhook_url, json=data) as response:
            if response.status == 204:
                print("Message sent successfully.")
            elif response.status == 429:
                print("Rate limited! Implement backoff strategy here.")
                # TODO: Implement exponential backoff
            else:
                print(f"Failed to send message. Status code: {response.status}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    await client.tree.sync()

    # Manual trigger for send_webhook_message (for testing)
    if WEBHOOK_URLS:  # Only execute if WEBHOOK_URLS is not empty
        first_webhook = WEBHOOK_URLS[list(WEBHOOK_URLS.keys())[0]]
        await send_webhook_message(first_webhook, "Test message from the bot!")

@client.event
async def on_guild_join(guild):
    # ... (your on_guild_join logic)

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    # ... (your setchannel logic)

@client.event
async def on_message(message):
    # ... (your on_message logic)

client.run(TOKEN)
