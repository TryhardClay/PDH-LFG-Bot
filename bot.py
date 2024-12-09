import discord
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

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    try:
        # Convert filter to lowercase for consistency
        filter = filter.lower()

        # Check if the filter is valid
        if filter not in ("casual", "cpdh"):
            await interaction.response.send_message("Invalid filter. Please specify either 'casual' or 'cpdh'.", ephemeral=True)
            return

        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
        WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = webhook.url
        CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter
        with open('webhooks.json', 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
        await interaction.response.send_message(f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to create webhooks in that channel.", ephemeral=True)

@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        channel_id = f'{interaction.guild.id}_{channel.id}'
        if channel_id in WEBHOOK_URLS:
            del WEBHOOK_URLS[channel_id]
            with open('webhooks.json', 'w') as f:
                json.dump(WEBHOOK_URLS, f, indent=4)
            await interaction.response.send_message(f"Channel {channel.mention} disconnected from cross-server communication.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Channel {channel.mention} is not connected to cross-server communication.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error disconnecting channel: {e}")
        await interaction.response.send_message("An error occurred while disconnecting the channel.", ephemeral=True)

@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    try:
        if WEBHOOK_URLS:
            connections = "\n".join([f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} (filter: {CHANNEL_FILTERS.get(channel, 'none')})" for channel in WEBHOOK_URLS])
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
        global WEBHOOK_URLS, CHANNEL_FILTERS
        with open('webhooks.json', 'r') as f:
            WEBHOOK_URLS = json.load(f)

        if interaction.response.is_done():
            await interaction.followup.send("Bot configuration reloaded.", ephemeral=True)
        else:
            await interaction.response.send_message("Bot configuration reloaded.", ephemeral=True)

    except Exception as e:
        logging.error(f"Error reloading configuration: {e}")
        if interaction.response.is_done():
            await interaction.followup.send("An error occurred while reloading the configuration.", ephemeral=True)
        else:
            await interaction.response.send_message("An error occurred while reloading the configuration.", ephemeral=True)

async def message_relay_loop():
    while True:
        try:
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in message relay loop: {e}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return  # Ignore messages from the bot itself

    # Only ignore webhook messages that are NOT from the bot itself
    if message.webhook_id and message.author.id != client.user.id:
        return

    content = message.content
    embeds = [embed.to_dict() for embed in message.embeds]
    if message.attachments:
        content += "\n" + "\n".join([attachment.url for attachment in message.attachments])

    source_channel_id = f'{message.guild.id}_{message.channel.id}'

    if source_channel_id in WEBHOOK_URLS:
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

        for destination_channel_id, webhook_url in WEBHOOK_URLS.items():
            if source_channel_id != destination_channel_id:
                destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')

                if source_filter == destination_filter or source_filter == 'none' or destination_filter == 'none':
                    await send_webhook_message(
                        webhook_url,
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
    try:
        role_name = client.user.name
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            await role.delete()
            logging.info(f"Deleted role {role_name} from server {guild.name}")
    except discord.Forbidden:
        logging.warning(f"Missing permissions to delete role in server {guild.name}")
    except discord.HTTPException as e:
        logging.error(f"Error deleting role in server {guild.name}: {e}")

@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    try:
        embed = discord.Embed(title="Cross-Server Communication Bot", description="This bot allows you to connect channels in different servers to relay messages and facilitate communication.", color=discord.Color.blue())
        embed.add_field(name="/setchannel", value="Set a channel for cross-server communication and assign a filter ('casual' or 'cpdh').", inline=False)
        embed.add_field(name="/disconnect", value="Disconnect a channel from cross-server communication.", inline=False)
        embed.add_field(name="/listconnections", value="List all connected channels and their filters.", inline=False)
        embed.add_field(name="/resetconfig", value="Reload the bot's configuration (for debugging/development).", inline=False)
        embed.add_field(name="/about", value="Show this information.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

client.run(TOKEN)
