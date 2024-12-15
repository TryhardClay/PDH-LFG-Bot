import discord
import aiohttp
import asyncio
import json
import os
import logging
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions

# -------------------------------------------------------------------------
# Configuration and Setup
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
            data = json.load(f)
        if isinstance(data, dict):
            return data
        else:
            logging.warning(f"Invalid data format in {CHANNEL_FILTERS_PATH}. Starting with empty channel filters.")
            return {}
    except FileNotFoundError:
        logging.warning(f"{CHANNEL_FILTERS_PATH} not found. Starting with empty channel filters.")
        return {}
    except Exception as e:
        logging.error(f"Error loading channel filters from {CHANNEL_FILTERS_PATH}: {e}")
        return {}

# -------------------------------------------------------------------------
# Global Variables
# -------------------------------------------------------------------------

WEBHOOK_URLS = load_webhook_data()
CHANNEL_FILTERS = load_channel_filters()

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def save_webhook_data():
    try:
        with open(PERSISTENT_DATA_PATH, 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving webhook data to {PERSISTENT_DATA_PATH}: {e}")

def save_channel_filters():
    try:
        with open(CHANNEL_FILTERS_PATH, 'w') as f:
            json.dump(CHANNEL_FILTERS, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving channel filters to {CHANNEL_FILTERS_PATH}: {e}")

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
                    retry_after = float(response.headers.get("Retry-After", 1))
                    logging.warning(f"Retrying in {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    return await send_webhook_message(webhook_url, content, embeds, username, avatar_url, view)
                else:
                    logging.error(f"Failed to send message. Status code: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logging.error(f"Error sending webhook message: {e}")
            return None

# -------------------------------------------------------------------------
# Event Handlers
# -------------------------------------------------------------------------

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    await client.tree.sync()
    # Start the message relay loop
    global message_relay_task
    if message_relay_task is None or message_relay_task.done():
        message_relay_task = asyncio.create_task(message_relay_loop())

@client.event
async def on_guild_join(guild):
    # Send the welcome message
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            try:
                await channel.send("Hello! I'm your cross-server communication bot. \n"
                                   "An admin needs to use the `/setchannel` command to \n"
                                   "choose a channel for relaying messages. \n"
                                   "Be sure to select an appropriate filter; either 'cpdh' or 'casual'.")
                break
            except discord.Forbidden:
                pass

@client.event
async def on_message(message):
    if message.author == client.user or message.webhook_id:
        return

    content = message.content
    embeds = [embed.to_dict() for embed in message.embeds]
    if message.attachments:
        content += "\n" + "\n".join([attachment.url for attachment in message.attachments])

    source_channel_id = f'{message.guild.id}_{message.channel.id}'

    if source_channel_id in WEBHOOK_URLS:
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            if source_channel_id != destination_channel_id:
                destination_filter = CHANNEL_FILTERS.get(destination_channel_id, 'none')

                if (source_filter == destination_filter or
                        source_filter == 'none' or
                        destination_filter == 'none'):
                    try:
                        await send_webhook_message(
                            webhook_data['url'],
                            content=content,
                            embeds=embeds,
                            username=f"{message.author.name} from {message.guild.name}",
                            avatar_url=message.author.avatar.url if message.author.avatar else None
                        )

                        logging.info(f"Attempted to relay message to {destination_channel_id}")

                    except Exception as e:
                        logging.error(f"Error relaying message: {e}")

@client.event
async def on_guild_remove(guild):
    # Clean up webhooks or data related to the removed guild (if needed)
    pass

# -------------------------------------------------------------------------
# Event Handlers for Buttons
# -------------------------------------------------------------------------

@client.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data['custom_id'] == "join_button":
            # Handle join logic here
            embed = interaction.message.embeds[0]
            embed.add_field(name="Players:", value=interaction.user.name, inline=False)
            await interaction.response.edit_message(embed=embed)
            await interaction.response.send_message("You joined the game!", ephemeral=True)
        elif interaction.data['custom_id'] == "leave_button":
            # Handle leave logic here
            embed = interaction.message.embeds[0]
            # Assuming the player's name is in a field named "Players:"
            for i, field in enumerate(embed.fields):
                if field.name == "Players:":
                    embed.remove_field(i)
                    break  # Remove only the first occurrence
            await interaction.response.edit_message(embed=embed)
            await interaction.response.send_message("You left the game!", ephemeral=True)

# -------------------------------------------------------------------------
# Bot Commands
# -------------------------------------------------------------------------

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    try:
        # Convert filter to lowercase for consistency
        filter = filter.lower()

        # Check if the filter is valid
        if filter not in ("casual", "cpdh"):
            await interaction.response.send_message("Invalid filter. Please specify either 'casual' or 'cpdh'.",
                                                    ephemeral=True)
            return

        # Create the webhook without the state parameter
        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")

        # Get the webhook with its state using the ID
        webhook_with_state = discord.Webhook.partial(webhook.id, webhook.url, session=client._session)

        WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = {
            'url': webhook_with_state.url,  # Use webhook_with_state here
            'id': webhook_with_state.id
        }
        CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter

        # Save webhook data and channel filters to persistent storage
        save_webhook_data()
        save_channel_filters()

        await interaction.response.send_message(
            f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to create webhooks in that channel.",
                                                ephemeral=True)

@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        channel_id = f'{interaction.guild.id}_{channel.id}'
        if channel_id in WEBHOOK_URLS:
            del WEBHOOK_URLS[channel_id]

            # Save webhook data to persistent storage
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
                [f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} (filter: {CHANNEL_FILTERS.get(channel, 'none')})"
                 for channel in WEBHOOK_URLS])
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)

@client.tree.command(name="updateconfig", description="Update the bot's configuration and resync commands.")
@has_permissions(administrator=True)
async def updateconfig(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Respond later for longer operations
    try:
        # Reload webhooks.json and channel_filters.json
        global WEBHOOK_URLS, CHANNEL_FILTERS
        WEBHOOK_URLS = load_webhook_data()
        CHANNEL_FILTERS = load_channel_filters()

        # Resync commands
        guild = interaction.guild
        client.tree.copy_global_to(guild=guild)
        await client.tree.sync(guild=guild)

        await interaction.followup.send("Bot configuration updated and commands resynced.", ephemeral=True)

    except Exception as e:
        logging.error(f"Error updating configuration: {e}")
        await interaction.followup.send("An error occurred while updating the configuration.", ephemeral=True)

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
        embed.add_field(name="/updateconfig",
                        value="Update the bot's configuration and resync commands.", inline=False)
        embed.add_field(name="/about", value="Show this information.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

# -------------------------------------------------------------------------
# BigLFG Commands
# -------------------------------------------------------------------------

@client.tree.command(name="biglfg")
async def biglfg(interaction: discord.Interaction):
    """
    Create a BigLFG game in all connected channels.
    """
    try:
        # ... (BigLFG command logic) ...

    except Exception as e:
        # ... (error handling) ...

# -------------------------------------------------------------------------
# Message Relay Loop
# -------------------------------------------------------------------------

@tasks.loop(seconds=1)
async def message_relay_loop():
    while True:
        try:
            # ... (your existing message relay logic)

        except discord.Forbidden as e:
            if "Missing Permissions" in str(e):
                # Assuming you can get the guild object from the message or context
                await manage_role(guild)
            else:
                pass  # Handle other Forbidden errors
        except Exception as e:
            logging.error(f"Error in message relay loop: {e}")

# -------------------------------------------------------------------------
# Main Bot Logic
# -------------------------------------------------------------------------

async def main():
    async with aiohttp.ClientSession() as session:
        client._session = session
        await client.start(TOKEN)  # Use client.start instead of client.run

if __name__ == "__main__":
    asyncio.run(main())
