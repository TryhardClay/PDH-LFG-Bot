import discord
import aiohttp
import asyncio
import json
import os
import logging
from discord.ext import commands
from discord.ext.commands import has_permissions
import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')

# --- Global variables ---
WEBHOOK_URLS = {}  # Dictionary to store webhook URLs
CHANNEL_FILTERS = {}  # Dictionary to store channel filters
big_lfg_data = {}  # Dictionary to store BigLFG data

# --- Helper functions ---
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

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = commands.Bot(command_prefix='/', intents=intents)

# --- Slash commands ---
@client.tree.command(name="setchannel", description="Set the channel for cross-server communication.")
@has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    logging.info(f"Received /setchannel command in channel {channel.name}")
    await interaction.response.defer(ephemeral=True)
    try:
        # Convert filter to lowercase for consistency
        filter = filter.lower()
        logging.info(f"Filter set to: {filter}")

        # Check if the filter is valid
        if filter not in ("casual", "cpdh"):
            await interaction.followup.send("Invalid filter. Please specify either 'casual' or 'cpdh'.")
            return

        logging.info(f"Creating webhook in channel {channel.name}")
        webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
        logging.info(f"Webhook created successfully: {webhook.url}")

        # Store webhook data in webhooks.json (only store the webhook URL)
        with open('webhooks.json', 'r+') as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
            except json.JSONDecodeError:
                data = []
            data.append({
                "webhook_url": webhook.url  # Store only the webhook URL
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()

        await interaction.followup.send(
            f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.")
    except discord.Forbidden:
        logging.error("Permission denied while creating webhook.")
        await interaction.followup.send("I don't have permission to create webhooks in that channel.")
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        await interaction.followup.send("An error occurred while setting the channel.")


@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication.")
@has_permissions(manage_channels=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        channel_id = f'{interaction.guild.id}_{channel.id}'
        if channel_id in WEBHOOK_URLS:
            del WEBHOOK_URLS[channel_id]
            with open('webhooks.json', 'w') as f:
                json.dump(WEBHOOK_URLS, f, indent=4)
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
            connections = "\n".join([
                f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} (filter: {CHANNEL_FILTERS.get(channel, 'none')})"
                for channel in WEBHOOK_URLS
            ])
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)


@client.tree.command(name="configreset", description="Reset the bot's configuration (for debugging/development).")
@has_permissions(administrator=True)
async def configreset(interaction: discord.Interaction):
    try:
        # Reset webhooks.json to an empty dictionary
        global WEBHOOK_URLS, CHANNEL_FILTERS
        WEBHOOK_URLS = {}
        CHANNEL_FILTERS = {}
        with open('webhooks.json', 'w') as f:
            json.dump(WEBHOOK_URLS, f, indent=4)

        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Bot configuration reset.")

    except Exception as e:
        logging.error(f"Error resetting configuration: {e}")
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("An error occurred while resetting the configuration.")


@client.tree.command(name="updateconfig", description="Update the bot's configuration (re-fetches webhooks).")
@has_permissions(manage_channels=True)
async def updateconfig(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Acknowledge the interaction first
    try:
        global WEBHOOK_URLS, CHANNEL_FILTERS
        new_webhook_urls = {}
        new_channel_filters = {}

        with open('webhooks.json', 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                await interaction.followup.send("Error: `webhooks.json` is empty or corrupted.")
                return

            # Re-fetch webhooks and populate dictionaries
            for item in data:
                try:
                    channel = client.get_channel(item.get('channel_id'))  # Use .get() with a default value
                    if channel is None:
                        logging.warning(f"Channel not found for ID: {item.get('channel_id')}")
                        continue

                    webhook = await channel.fetch_webhook(int(item['webhook_url'].split('/')[-2]))
                    new_webhook_urls[f"{item['guild_id']}_{item['channel_id']}"] = webhook.url
                    new_channel_filters[f"{item['guild_id']}_{item['channel_id']}"] = item['filter']
                    logging.info(f"Refreshed webhook for channel: {channel.name}")
                except discord.NotFound:
                    logging.warning(f"Webhook not found for channel ID: {item['channel_id']}")
                except Exception as e:
                    logging.error(f"Error refreshing webhook: {e}")

        # Update global dictionaries
        WEBHOOK_URLS = new_webhook_urls
        CHANNEL_FILTERS = new_channel_filters

        await interaction.followup.send("Bot configuration updated.")

    except Exception as e:
        logging.error(f"Error updating configuration: {e}")
        await interaction.followup.send("An error occurred while updating the configuration.")


@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Defer the interaction first
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
        embed.add_field(name="/configreset",  # Updated command name
                        value="Reset the bot's configuration (for debugging/development).", inline=False)
        embed.add_field(name="/updateconfig",
                        value="Update the bot's configuration.", inline=False)
        embed.add_field(name="/biglfg",
                        value="Create a BigLFG prompt with reactions.", inline=False)
        embed.add_field(name="/about", value="Show this information.", inline=False)

        await interaction.followup.send(embed=embed)  # Use followup.send
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.followup.send("An error occurred while processing the command.")

# --- Events ---
@client.event
async def on_ready():
    global WEBHOOK_URLS, CHANNEL_FILTERS
    logging.info(f'Logged in as {client.user}')
    
    try:
        with open('webhooks.json', 'r') as f:
            WEBHOOK_URLS = json.load(f)  # Load only WEBHOOK_URLS from the file
    except FileNotFoundError:
        logging.warning("webhooks.json not found. Starting with empty configuration.")
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding webhooks.json: {e}")
    
    await client.tree.sync()
    asyncio.create_task(update_big_lfg())


@client.event
async def on_guild_join(guild):
    # Check if the bot already has a role in the server
    bot_role = discord.utils.get(guild.roles, name=client.user.name)
    if not bot_role:  # Only create a role if it doesn't exist
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


@client.event
async def on_guild_remove(guild):
    try:
        # Use client.user.name to get the exact role name
        role_name = client.user.name
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            await role.delete()
            logging.info(f"Deleted role {role_name} from server {guild.name}")
    except discord.Forbidden:
        logging.warning(f"Missing permissions to delete role in server {guild.name}")
    except discord.HTTPException as e:
        logging.error(f"Error deleting role in server {guild.name}: {e}")


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
        logging.info(f"Relaying message from channel: {message.channel.name}")  # Log message relaying
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

# --- BigLFG feature ---
@client.tree.command(name="biglfg", description="Create a BigLFG prompt with reactions.")
async def biglfg(interaction: discord.Interaction, prompt: str = "Waiting for 4 more players to join..."):  # Set default prompt
    try:
        embed = discord.Embed(title=prompt, description="React with 👍 to join!")
        message_ids = []

        # Send the embed to connected channels with matching filters
        for channel_id, webhook_url in WEBHOOK_URLS.items():
            channel_filter = CHANNEL_FILTERS.get(channel_id, 'none')
            if channel_filter == interaction.channel.id or channel_filter == 'none':  # Check for matching filter or no filter
                channel = client.get_channel(int(channel_id.split('_')[1]))
                message = await channel.send(embed=embed)
                await message.add_reaction("👍")  # Add thumbs up reaction
                message_ids.append(f"{message.id}_{channel.id}")

        # Store BigLFG data
        big_lfg_data[message.id] = {  # Removed the check for message is not None
            "prompt": prompt,
            "start_time": datetime.datetime.now(),
            "timeout": datetime.timedelta(minutes=15),  # 15-minute timeout
            "max_thumbs_up": 4,
            "thumbs_up_count": 0,
            "message_ids": message_ids
        }

        await interaction.response.defer(ephemeral=True)  # Moved this line back to its original position
        await interaction.followup.send(f"BigLFG prompt created with the following prompt: {prompt}")

    except Exception as e:
        logging.error(f"Error in biglfg command: {e}")
        await interaction.followup.send("An error occurred while creating the BigLFG prompt.")


async def update_big_lfg():
    while True:
        await asyncio.sleep(5)  # Update every 5 seconds
        for lfg_id, lfg_data in big_lfg_data.copy().items():
            elapsed_time = datetime.datetime.now() - lfg_data["start_time"]
            if elapsed_time > lfg_data["timeout"]:
                # Timeout reached, cancel the BigLFG
                embed = discord.Embed(title=lfg_data["prompt"],
                                      description="This request has been cancelled due to inactivity.")
                for message_id in lfg_data["message_ids"]:
                    try:
                        channel = client.get_channel(int(message_id.split('_')[1]))
                        message = await channel.fetch_message(int(message_id.split('_')[0]))
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                    except Exception as e:
                        logging.error(f"Error cancelling BigLFG: {e}")
                del big_lfg_data[lfg_id]  # Remove from data
                continue

            # Update thumbs up count and update prompt
            for message_id in lfg_data["message_ids"]:
                try:
                    channel = client.get_channel(int(message_id.split('_')[1]))
                    message = await channel.fetch_message(int(message_id.split('_')[0]))
                    for reaction in message.reactions:
                        if reaction.emoji == "👍":
                            lfg_data["thumbs_up_count"] = reaction.count - 1
                            remaining_players = max(0, lfg_data["max_thumbs_up"] - lfg_data["thumbs_up_count"])
                            new_prompt = lfg_data["prompt"]
                            if remaining_players > 0:
                                new_prompt = f"Waiting for {remaining_players} more players to join..."
                            embed = discord.Embed(title=new_prompt, description="React with 👍 to join!")
                            await message.edit(embed=embed)
                            break
                except Exception as e:
                    logging.error(f"Error updating BigLFG: {e}")

            # Check if full
            if lfg_data["thumbs_up_count"] >= lfg_data["max_thumbs_up"]:
                embed = discord.Embed(title=lfg_data["prompt"], description="This game is full!")
                for message_id in lfg_data["message_ids"]:
                    try:
                        channel = client.get_channel(int(message_id.split('_')[1]))
                        message = await channel.fetch_message(int(message_id.split('_')[0]))
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                    except Exception as e:
                        logging.error(f"Error updating BigLFG: {e}")
                del big_lfg_data[lfg_id]  # Remove from data


# --- Main bot logic ---
client.run(TOKEN)
