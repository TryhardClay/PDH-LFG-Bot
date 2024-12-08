import discord
import re
import aiohttp
import asyncio
import json
import os
import logging
from discord.ext import commands
from discord.ext.commands import has_permissions

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

WEBHOOK_URLS = {}  # Initialize as an empty dictionary

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
intents.members = True  # For potential future use with member-related events

client = commands.Bot(command_prefix='/', intents=intents)

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

@client.event
async def on_guild_join(guild):
    # ... (your on_guild_join logic)

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    # ... (your setchannel logic)

@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    # ... (your disconnect logic)

@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    # ... (your listconnections logic)

@client.event
async def on_message(message):
    if message.author == client.user:
        return  # Ignore messages from the bot itself

    content = message.content
    embeds = [embed.to_dict() for embed in message.embeds]
    if message.attachments:
        content += "\n" + "\n".join([attachment.url for attachment in message.attachments])

    # Correctly construct the source_channel_id
    source_channel_id = f'{message.guild.id}_{message.channel.id}'

    if source_channel_id in WEBHOOK_URLS:
        for destination_channel_id, webhook_url in WEBHOOK_URLS.items():
            if source_channel_id != destination_channel_id:
                await send_webhook_message(
                    webhook_url,
                    content=content,
                    embeds=embeds,
                    username=f"{message.author.name} from {message.guild.name}",
                    avatar_url=message.author.avatar.url if message.author.avatar else None
                )

        # ... (your reaction relaying logic)

client.run(TOKEN)
