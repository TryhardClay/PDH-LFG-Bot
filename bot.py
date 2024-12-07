import discord
import re
import aiohttp
import asyncio
import json

TOKEN = 'YOUR_BOT_TOKEN'
WEBHOOK_URLS = {}  # Start with an empty dictionary

# Load webhook URLs from storage (if available)
try:
    with open('webhooks.json', 'r') as f:
        WEBHOOK_URLS = json.load(f)
except FileNotFoundError:
    pass  # Ignore if the file doesn't exist

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Enable guilds intent
client = discord.Client(intents=intents)

# ... (send_webhook_message function remains the same)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_guild_join(guild):
    # Create a webhook in a specific channel (e.g., the first text channel)
    channel = guild.text_channels[0]  # You might want to refine this logic
    webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")

    # Store the webhook URL
    WEBHOOK_URLS[f'{guild.id}_{channel.id}'] = webhook.url

    # Save webhook URLs to storage
    with open('webhooks.json', 'w') as f:
        json.dump(WEBHOOK_URLS, f)

    print(f"Joined server: {guild.name}, created webhook in {channel.name}")

# ... (on_message event remains the same)

client.run(TOKEN)
