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
    # Sync slash commands (global sync)
    await client.tree.sync()

@client.event
async def on_guild_join(guild):
    # Create a role for the bot
    try:
        bot_role = await guild.create_role(name=client.user.name, mentionable=True)
        print(f"Created role {bot_role.name} in server {guild.name}")

        # Add the role to the bot itself
        try:
            await guild.me.add_roles(bot_role)
            print(f"Added role {bot_role.name} to the bot in server {guild.name}")
        except discord.Forbidden:
            print(f"Missing permissions to add role to the bot in server {guild.name}")

    except discord.Forbidden:
        print(f"Missing permissions to create role in server {guild.name}")

    # (Optional) Welcome message
    for channel in guild.text_channels:
        try:
            await channel.send("Hello! I'm your cross-server communication bot. "
                               "An admin needs to use the `/setchannel` command to "
                               "choose a channel for relaying messages.")
            break
        except discord.Forbidden:
            continue

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
        WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = webhook.url
        with open('webhooks.json', 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
        await interaction.response.send_message(f"Cross-server communication channel set to {channel.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to create webhooks in that channel.", ephemeral=True)

@client.event
async def on_message(message):
    if message.author == client.user:
        return  # Ignore messages from the bot itself

    content = message.content
    if message.attachments:
        content += "\n" + "\n".join([attachment.url for attachment in message.attachments])

    source_channel = f'{message.guild.id}_{message.channel.id}'
    for destination_channel, webhook_url in WEBHOOK_URLS.items():
        if source_channel != destination_channel:
            await send_webhook_message(
                webhook_url,
                content,
                username=f"{message.author.name} from {message.guild.name}",
                avatar_url=message.author.avatar.url if message.author.avatar else None
            )

client.run(TOKEN)
