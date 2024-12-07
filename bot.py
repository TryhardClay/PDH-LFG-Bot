import discord
import re
import aiohttp
import asyncio
import json
import os

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

WEBHOOK_URLS = {}  # Start with an empty dictionary

# Load webhook URLs from storage (if available)
try:
    with open('webhooks.json', 'r') as f:
        WEBHOOK_URLS = json.load(f)
except FileNotFoundError:
    pass  # Ignore if the file doesn't exist

# Define intents with privileged intents enabled
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # Enable members intent

client = discord.Client(intents=intents)

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

@client.event
async def on_guild_join(guild):
    # Create a webhook in a specific channel (e.g., the first text channel)
    channel = guild.text_channels[0]  # You might want to refine this logic
    webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")

    # Store the webhook URL
    WEBHOOK_URLS[f'{guild.id}_{channel.id}'] = webhook.url

    # Save webhook URLs to storage
    with open('webhooks.json', 'w') as f:
        json.dump(WEBHOOK_URLS, f, indent=4)  # Added indent for better readability

    print(f"Joined server: {guild.name}, created webhook in {channel.name}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return  # Ignore messages from the bot itself

    # Extract content (including links and attachments)
    content = message.content
    if message.attachments:
        content += "\n" + "\n".join([attachment.url for attachment in message.attachments])

    # Determine source and destination
    source_channel = f'{message.guild.id}_{message.channel.id}'
    for destination_channel, webhook_url in WEBHOOK_URLS.items():
        if source_channel != destination_channel:  # Don't send to the same channel
            await send_webhook_message(
                webhook_url,
                content,
                username=f"{message.author.name} from {message.guild.name}",
                avatar_url=message.author.avatar.url if message.author.avatar else None
            )

client.run(TOKEN)
