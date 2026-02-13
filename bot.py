import asyncio
import discord
import aiohttp
import json
import os
import logging
import uuid
import time
from enum import Enum
from discord.ext import commands
from discord.ext.commands import has_permissions

# -------------------------------------------------------------------------
# Setup and Configuration
# -------------------------------------------------------------------------

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Access the token from the environment variable
TOKEN = os.environ.get('TOKEN')
CONVOKE_API_KEY = os.environ.get('CONVOKE_API_KEY')
CONVOKE_ROOT = "https://api.convoke.gg"

# Persistent storage paths
CHANNEL_FILTERS_PATH = '/var/data/channel_filters.json'
BANNED_USERS_PATH = "/var/data/banned_users.json"
TRUSTED_ADMINS_PATH = "/var/data/trusted_admins.json"
BANNED_SERVERS_PATH = "/var/data/banned_servers.json"

# Bot image URL
IMAGE_URL = "https://raw.githubusercontent.com/TryhardClay/PDH-LFG-Bot/main/PDHBot.jpg"

# BigLFG Embed Tracking
active_embeds = {}

# -------------------------------------------------------------------------
# Persistent Storage Functions
# -------------------------------------------------------------------------

def load_json_file(filepath, default_value):
    """Generic function to load JSON data from a file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            if isinstance(data, type(default_value)):
                return data
            else:
                logging.error(f"Invalid data format in {filepath}")
                return default_value
    except FileNotFoundError:
        return default_value
    except json.decoder.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {filepath}: {e}")
        return default_value

def save_json_file(filepath, data):
    """Generic function to save JSON data to a file."""
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving data to {filepath}: {e}")

def load_channel_filters():
    """Load channel filters from persistent storage."""
    return load_json_file(CHANNEL_FILTERS_PATH, {})

def save_channel_filters():
    """Save channel filters to persistent storage."""
    save_json_file(CHANNEL_FILTERS_PATH, CHANNEL_FILTERS)

def load_banned_users():
    """Load banned users from persistent storage."""
    return load_json_file(BANNED_USERS_PATH, {})

def save_banned_users():
    """Save banned users to persistent storage."""
    save_json_file(BANNED_USERS_PATH, banned_users)

def load_banned_servers():
    """Load banned servers from persistent storage."""
    data = load_json_file(BANNED_SERVERS_PATH, [])
    return set(data) if isinstance(data, list) else set()

def save_banned_servers():
    """Save banned servers to persistent storage."""
    save_json_file(BANNED_SERVERS_PATH, list(banned_servers))

def load_trusted_admins():
    """Load trusted admins from persistent storage."""
    default_super_admin = 582548598584115211  # Clay's ID only
    data = load_json_file(TRUSTED_ADMINS_PATH, [default_super_admin])
    
    # Ensure the default super admin is always included
    if default_super_admin not in data:
        data.append(default_super_admin)
    
    return data

def save_trusted_admins():
    """Save trusted admins to persistent storage."""
    save_json_file(TRUSTED_ADMINS_PATH, trusted_admins)

# Load data on startup
CHANNEL_FILTERS = load_channel_filters()
banned_users = load_banned_users()
banned_servers = load_banned_servers()
trusted_admins = load_trusted_admins()

# -------------------------------------------------------------------------
# Bot Setup
# -------------------------------------------------------------------------

class GameFormat(Enum):
    PAUPER_COMMANDER = "Pauper Commander"

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = commands.Bot(command_prefix='/', intents=intents)

# -------------------------------------------------------------------------
# Convoke Integration
# -------------------------------------------------------------------------

class ConvokeGameTypes(Enum):
    Commander = "commander"

async def generate_convoke_link(game_data: dict) -> tuple[str | None, str | None]:
    """
    Generate a Convoke game link using the provided game data.
    Returns (game_url, None) since we're not using passwords.
    """
    try:
        logging.info(f"Generating Convoke link for game ID: {game_data['id']}")

        if not CONVOKE_API_KEY:
            logging.error("Convoke API key is missing!")
            return None, None

        # Prepare the payload
        payload = {
            "apiKey": CONVOKE_API_KEY,
            "isPublic": False,
            "name": f"PDH Game {game_data['id']}",
            "spellbotGameId": str(game_data['id']),
            "seatLimit": 4,  # Hardcoded for 4-player Pauper Commander
            "format": ConvokeGameTypes.Commander.value,
            "discordGuild": str(game_data['guild_id']),
            "discordChannel": str(game_data['channel_id']),
            "discordPlayers": [
                {"id": str(player_id), "name": player_name}
                for player_id, player_name in game_data['players'].items()
            ]
        }

        headers = {"user-agent": "pdh-lfg-bot/1.0"}
        endpoint = f"{CONVOKE_ROOT}/game/create-game"

        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                if response.status == 200 or response.status == 201:
                    data = await response.json()
                    game_url = data.get("url")
                    logging.info(f"Successfully generated Convoke link: {game_url}")
                    return game_url, None
                else:
                    error = await response.text()
                    logging.error(f"Failed to generate Convoke link. Status: {response.status}, Error: {error}")
                    return None, None

    except Exception as e:
        logging.error(f"Error while generating Convoke link: {e}")
        return None, None

# -------------------------------------------------------------------------
# BigLFG Functions
# -------------------------------------------------------------------------

def create_lfg_view():
    """Create and return a Discord UI View with JOIN and LEAVE buttons."""
    view = discord.ui.View(timeout=45 * 60)  # 45-minute timeout

    async def join_button_callback(button_interaction: discord.Interaction):
        try:
            user_id = str(button_interaction.user.id)

            # Check if the user is banned
            if user_id in banned_users:
                logging.warning(f"Banned user {button_interaction.user.name} (ID: {user_id}) attempted to join a game.")
                
                try:
                    reason = banned_users[user_id]["reason"]
                    expiration = banned_users[user_id].get("expiration")
                    expiration_text = (
                        f"Your ban will expire <t:{expiration}:R>."
                        if expiration else "Your ban is permanent."
                    )
                    dm_message = (
                        f"You are currently banned from joining games through this bot.\n"
                        f"**Reason:** {reason}\n{expiration_text}\n\n"
                        f"For appeals, inform the server admin, reach out to Clay (User ID: 582548598584115211) on Discord, "
                        f"or email: gaming4tryhards@gmail.com."
                    )
                    await button_interaction.user.send(dm_message)
                except Exception as e:
                    logging.error(f"Failed to DM banned user {button_interaction.user.name}: {e}")

                await button_interaction.response.send_message(
                    "You are banned from joining games through this bot.",
                    ephemeral=True
                )
                return

            # Find the LFG UUID for this embed
            lfg_uuid = None
            for uuid, data in active_embeds.items():
                if any(message.id == button_interaction.message.id for message in data["messages"].values()):
                    lfg_uuid = uuid
                    break

            if not lfg_uuid or lfg_uuid not in active_embeds:
                await button_interaction.response.send_message("This LFG request is no longer active.", ephemeral=True)
                return

            user_id = button_interaction.user.id
            display_name = button_interaction.user.name

            # Add player if not already in the list
            if user_id not in active_embeds[lfg_uuid]["players"]:
                active_embeds[lfg_uuid]["players"][user_id] = display_name
                await update_embeds(lfg_uuid)

            await button_interaction.response.defer()
        except discord.errors.NotFound:
            logging.error("Interaction not found. This might be caused by a timeout or invalid interaction.")

    async def leave_button_callback(button_interaction: discord.Interaction):
        try:
            # Find the LFG UUID for this embed
            lfg_uuid = None
            for uuid, data in active_embeds.items():
                if any(message.id == button_interaction.message.id for message in data["messages"].values()):
                    lfg_uuid = uuid
                    break

            if not lfg_uuid or lfg_uuid not in active_embeds:
                await button_interaction.response.send_message("This LFG request is no longer active.", ephemeral=True)
                return

            user_id = button_interaction.user.id

            # Remove player if they're in the list
            if user_id in active_embeds[lfg_uuid]["players"]:
                del active_embeds[lfg_uuid]["players"][user_id]
                await update_embeds(lfg_uuid)

                # Restart timeout if player count falls below four
                if len(active_embeds[lfg_uuid]["players"]) < 4:
                    task = active_embeds[lfg_uuid].get("task")
                    if not task or task.done():
                        active_embeds[lfg_uuid]["task"] = asyncio.create_task(lfg_timeout(lfg_uuid))
                        logging.info(f"Timeout task restarted for LFG UUID {lfg_uuid}")

            await button_interaction.response.defer()
        except discord.errors.NotFound:
            logging.error("Interaction not found. This might be caused by a timeout or invalid interaction.")

    join_button = discord.ui.Button(style=discord.ButtonStyle.success, label="JOIN")
    leave_button = discord.ui.Button(style=discord.ButtonStyle.danger, label="LEAVE")

    join_button.callback = join_button_callback
    leave_button.callback = leave_button_callback

    view.add_item(join_button)
    view.add_item(leave_button)

    return view

async def update_embeds(lfg_uuid):
    """Update all embeds associated with the given LFG UUID."""
    try:
        if lfg_uuid not in active_embeds:
            logging.warning(f"LFG UUID {lfg_uuid} not found in active_embeds.")
            return

        data = active_embeds[lfg_uuid]
        players = data["players"]
        is_game_ready = len(players) == 4

        # Generate the Convoke link only once when game is ready
        if is_game_ready and "game_link" not in data:
            logging.info("Game is ready! Generating Convoke link...")
            
            game_data = {
                "id": lfg_uuid,
                "guild_id": data["guild_id"],
                "channel_id": data["channel_id"],
                "players": players
            }

            game_link, _ = await generate_convoke_link(game_data)

            if game_link:
                data["game_link"] = game_link
            else:
                logging.error("Failed to generate Convoke link.")
                data["game_link"] = "Error generating game link"

        # Update all embeds
        for channel_id, message in data["messages"].items():
            try:
                embed = discord.Embed(
                    title="Your game is ready!" if is_game_ready else "Looking for more players...",
                    color=discord.Color.green() if is_game_ready else discord.Color.yellow(),
                )
                embed.set_author(
                    name="PDH LFG Bot",
                    icon_url=IMAGE_URL,
                    url="https://github.com/TryhardClay/PDH-LFG-Bot"
                )
                if not is_game_ready:
                    embed.set_thumbnail(url=IMAGE_URL)

                # Add the player list
                embed.add_field(
                    name="Players:",
                    value="\n".join([f"{i + 1}. {name}" for i, name in enumerate(players.values())]),
                    inline=False
                )

                if is_game_ready:
                    # Add the Convoke link to the embed
                    embed.add_field(
                        name="Convoke Game:",
                        value=f"[Click here to join your game!]({data['game_link']})",
                        inline=False
                    )

                    # Remove buttons when game is ready
                    view = discord.ui.View()
                    await message.edit(embed=embed, view=view)

                    # Cancel the timeout task
                    task = data.pop("task", None)
                    if task and not task.done():
                        task.cancel()
                        logging.info(f"Timeout task canceled for LFG UUID {lfg_uuid}")

                    # Send DMs to all players
                    if "dm_sent" not in data or not data["dm_sent"]:
                        for user_id in players:
                            try:
                                user = await client.fetch_user(user_id)
                                if user:
                                    message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                                    dm_content = (
                                        f"**Your Pauper Commander game is ready!**\n\n"
                                        f"**Convoke Link:** {data['game_link']}\n\n"
                                        f"View the original message: [Click here]({message_link})"
                                    )
                                    await user.send(dm_content)
                                    logging.info(f"DM sent to {user.name} (ID: {user.id})")
                            except Exception as e:
                                logging.error(f"Failed to DM player {user_id}: {e}")
                        data["dm_sent"] = True
                else:
                    # Update embed with current players (game not ready yet)
                    await message.edit(embed=embed, view=create_lfg_view())

            except Exception as e:
                logging.error(f"Error updating embed in channel {channel_id} for LFG UUID {lfg_uuid}: {e}")

    except Exception as e:
        logging.error(f"Error in update_embeds for LFG UUID {lfg_uuid}: {e}")

async def lfg_timeout(lfg_uuid):
    """Handle timeout for an LFG embed."""
    try:
        await asyncio.sleep(45 * 60)  # Wait 45 minutes
        if lfg_uuid in active_embeds:
            data = active_embeds.pop(lfg_uuid)
            for message in data["messages"].values():
                try:
                    embed = discord.Embed(
                        title="This request has timed out.",
                        color=discord.Color.red()
                    )
                    embed.set_author(
                        name="PDH LFG Bot",
                        icon_url=IMAGE_URL
                    )
                    await message.edit(embed=embed, view=None)
                except Exception as e:
                    logging.error(f"Error updating embed on timeout for LFG UUID {lfg_uuid}: {e}")
    except Exception as e:
        logging.error(f"Error in lfg_timeout for LFG UUID {lfg_uuid}: {e}")

# -------------------------------------------------------------------------
# Event Handlers
# -------------------------------------------------------------------------

@client.event
async def on_ready():
    """Event triggered when the bot is ready."""
    logging.info(f"Bot is ready and logged in as {client.user}")

    # Reload configurations
    global CHANNEL_FILTERS
    CHANNEL_FILTERS = load_channel_filters()
    logging.info("Configurations reloaded successfully.")

    try:
        # Sync global commands
        logging.info("Syncing global commands...")
        synced_commands = await client.tree.sync()
        logging.info(f"Global commands synced: {len(synced_commands)} commands")
    except Exception as e:
        logging.error(f"Error during command syncing: {e}")

@client.event
async def on_guild_join(guild):
    """Event triggered when the bot joins a new server."""
    if guild.id in banned_servers:
        logging.warning(f"Joined banned server: {guild.name} (ID: {guild.id}). Leaving immediately.")
        await guild.leave()
    else:
        logging.info(f"Joined new server: {guild.name} (ID: {guild.id})")

@client.event
async def on_guild_remove(guild):
    """Event triggered when the bot is removed from a server."""
    logging.info(f"Bot removed from server: {guild.name} (ID: {guild.id})")

@client.event
async def on_message(message):
    """Prevent non-slash commands in LFG channels."""
    if message.author == client.user or message.webhook_id:
        return

    user_id = str(message.author.id)

    # Check if the user is banned
    if user_id in banned_users:
        logging.warning(f"Blocked message from banned user {message.author.name} (ID: {user_id})")
        try:
            await message.delete()
            reason = banned_users[user_id].get("reason", "No reason provided")
            expiration = banned_users[user_id].get("expiration")
            expiration_text = (
                f"Your ban will expire <t:{expiration}:R>."
                if expiration else "This is a permanent ban."
            )
            await message.author.send(
                f"Your message in **{message.guild.name} - {message.channel.name}** was blocked.\n"
                f"**Reason:** {reason}\n{expiration_text}\n\n"
                f"For appeals, contact the server admin or Clay (User ID: 582548598584115211)."
            )
        except Exception as e:
            logging.error(f"Failed to handle banned user message: {e}")
        return

    # Check if message is in an LFG channel
    source_channel_id = f'{message.guild.id}_{message.channel.id}'
    source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

    if source_filter.endswith('lfg') and not message.content.startswith('/'):
        await message.delete()
        await message.channel.send(
            "Text messages are not allowed in this channel. Please use slash commands.",
            delete_after=5
        )

# -------------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------------

@client.tree.command(name="setchannel", description="Set the channel for LFG requests (admin only)")
@commands.has_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    """Assign a channel for LFG requests with a specific game type filter."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    filter = filter.lower()
    if filter not in ("cpdhlfg", "casuallfg"):
        await interaction.response.send_message(
            "Invalid filter. Please specify 'cpdhlfg' or 'casuallfg'.",
            ephemeral=True
        )
        return

    CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter
    save_channel_filters()

    logging.info(f"Admin {interaction.user.name} set {channel.mention} with filter '{filter}'")
    await interaction.response.send_message(
        f"LFG channel set to {channel.mention} with filter '{filter}'.",
        ephemeral=True
    )

@client.tree.command(name="disconnect", description="Disconnect a channel from LFG requests (admin only)")
@commands.has_permissions(administrator=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    """Remove a channel from the LFG system."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    channel_id = f'{interaction.guild.id}_{channel.id}'
    if channel_id in CHANNEL_FILTERS:
        del CHANNEL_FILTERS[channel_id]
        save_channel_filters()
        logging.info(f"Admin {interaction.user.name} disconnected {channel.mention}")
        await interaction.response.send_message(
            f"Disconnected {channel.mention} from LFG system.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{channel.mention} is not configured for LFG requests.",
            ephemeral=True
        )

@client.tree.command(name="listconnections", description="List LFG-enabled channels")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    """Display all LFG-enabled channels and their filters."""
    try:
        if CHANNEL_FILTERS:
            connections = "\n".join(
                [f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} "
                 f"(filter: {filter_type})"
                 for channel, filter_type in CHANNEL_FILTERS.items()]
            )
            await interaction.response.send_message(
                f"LFG-enabled channels:\n{connections}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No LFG-enabled channels configured.",
                ephemeral=True
            )
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message(
            "An error occurred while listing connections.",
            ephemeral=True
        )

@client.tree.command(name="biglfg", description="Create a cross-server LFG request for Pauper Commander")
async def biglfg(interaction: discord.Interaction):
    """Create a BigLFG embed for finding players across connected servers."""
    user_id = str(interaction.user.id)
    
    # Check if user is banned
    if user_id in banned_users:
        logging.warning(f"Banned user {interaction.user.name} (ID: {user_id}) attempted to use /biglfg")
        await interaction.response.send_message(
            "You are currently banned from using this command.",
            ephemeral=True
        )
        return

    try:
        await interaction.response.defer()

        # Generate unique UUID for this LFG request
        lfg_uuid = str(uuid.uuid4())

        source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
        source_filter = CHANNEL_FILTERS.get(source_channel_id, 'none')

        # Verify this is an LFG channel
        if not source_filter.endswith('lfg'):
            await interaction.followup.send(
                "This command can only be used in LFG-enabled channels.",
                ephemeral=True
            )
            return

        # Create the initial embed
        embed = discord.Embed(
            title="Looking for more players...",
            color=discord.Color.yellow(),
            description="Click JOIN below to join this Pauper Commander game!"
        )
        embed.set_author(
            name="PDH LFG Bot",
            icon_url=IMAGE_URL,
            url="https://github.com/TryhardClay/PDH-LFG-Bot"
        )
        embed.set_thumbnail(url=IMAGE_URL)
        embed.add_field(
            name="Players:",
            value=f"1. {interaction.user.name}",
            inline=False
        )

        # Send embed to all matching LFG channels
        sent_messages = {}
        for channel_id, filter_type in CHANNEL_FILTERS.items():
            if filter_type == source_filter:
                try:
                    guild_id, chan_id = channel_id.split('_')
                    destination_channel = client.get_channel(int(chan_id))
                    if destination_channel:
                        sent_message = await destination_channel.send(
                            embed=embed,
                            view=create_lfg_view()
                        )
                        sent_messages[channel_id] = sent_message
                        await asyncio.sleep(0.5)  # Rate limit prevention
                except Exception as e:
                    logging.error(f"Error sending to channel {channel_id}: {e}")

        if sent_messages:
            # Store the LFG data
            active_embeds[lfg_uuid] = {
                "players": {interaction.user.id: interaction.user.name},
                "messages": sent_messages,
                "guild_id": interaction.guild.id,
                "channel_id": interaction.channel.id,
                "task": asyncio.create_task(lfg_timeout(lfg_uuid))
            }
            await interaction.followup.send(
                "LFG request created successfully!",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Failed to create LFG request. No matching channels found.",
                ephemeral=True
            )

    except Exception as e:
        logging.error(f"Error in /biglfg command: {e}")
        await interaction.followup.send(
            "An error occurred while creating the LFG request.",
            ephemeral=True
        )

@client.tree.command(name="about", description="Show information about the bot")
async def about(interaction: discord.Interaction):
    """Display bot information, commands, and rules."""
    try:
        embed = discord.Embed(
            title="PDH LFG Bot - Information & Commands",
            description=(
                "This bot helps players find Pauper Commander games across multiple Discord servers.\n\n"
                "**Note:** Restricted commands require special permissions."
            ),
            color=discord.Color.blue()
        )

        # Rules Section
        embed.add_field(
            name="📜 Rules:",
            value=(
                "1️⃣ **Respect Others** - Treat all players with kindness\n"
                "2️⃣ **No Harassment** - Zero tolerance for hate speech or discrimination\n"
                "3️⃣ **Follow Server Guidelines** - Respect each server's rules\n"
                "4️⃣ **No Spamming** - Don't abuse commands or LFG features\n"
                "5️⃣ **No Poaching** - Don't use this bot to recruit users to other servers\n"
                "6️⃣ **Report Issues** - Contact server admin or Clay (ID: 582548598584115211)\n\n"
                "**🚨 Breaking rules may result in a permanent ban**"
            ),
            inline=False
        )

        # Public Commands
        embed.add_field(
            name="🌎 Public Commands:",
            value=(
                "**/biglfg** - Create a cross-server LFG request\n"
                "**/about** - Display this information"
            ),
            inline=False
        )

        # Admin Commands
        embed.add_field(
            name="🔐 Admin Commands:",
            value=(
                "**/setchannel** - Configure a channel for LFG requests\n"
                "**/disconnect** - Remove LFG configuration from a channel\n"
                "**/listconnections** - View configured LFG channels\n"
                "**/listadmins** - View bot administrators"
            ),
            inline=False
        )

        # Restricted Commands
        embed.add_field(
            name="🚨 Super Admin Commands:",
            value=(
                "**/banuser** - Ban a user from using the bot\n"
                "**/unbanuser** - Unban a user\n"
                "**/listbans** - View all banned users\n"
                "**/banserver** - Ban a server from using the bot\n"
                "**/unbanserver** - Unban a server"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message(
            "An error occurred.",
            ephemeral=True
        )

@client.tree.command(name="banuser", description="Ban a user from using the bot (super admin only)")
async def banuser(interaction: discord.Interaction, user: discord.User, reason: str):
    """Ban a user. First offense = 3 days, second offense = permanent."""
    if interaction.user.id not in trusted_admins:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    user_id = str(user.id)

    # Check for previous temporary ban
    if user_id in banned_users and banned_users[user_id].get("expiration"):
        # Second offense - permanent ban
        ban_expiration = None
        ban_type = "Permanent"
    else:
        # First offense - 3 day ban
        ban_expiration = int(time.time()) + (3 * 24 * 60 * 60)
        ban_type = "Temporary (3 days)"

    banned_users[user_id] = {
        "name": user.name,
        "reason": reason,
        "expiration": ban_expiration
    }
    save_banned_users()

    logging.info(f"{ban_type} ban issued: {user.name} (ID: {user_id}) - Reason: {reason}")
    await interaction.response.send_message(
        f"{ban_type} ban issued for {user.mention}.\n**Reason:** {reason}",
        ephemeral=True
    )

    # DM the user
    try:
        expiration_text = (
            "Your ban will expire in 3 days."
            if ban_expiration else "This is a permanent ban."
        )
        dm_message = (
            f"You have been banned from using PDH LFG Bot.\n"
            f"**Reason:** {reason}\n{expiration_text}\n\n"
            f"For appeals, contact Clay (User ID: 582548598584115211) or email: gaming4tryhards@gmail.com"
        )
        await user.send(dm_message)
    except Exception as e:
        logging.error(f"Failed to DM banned user {user.name}: {e}")

@client.tree.command(name="unbanuser", description="Unban a user (super admin only)")
async def unbanuser(interaction: discord.Interaction, user: discord.User):
    """Remove a user's ban."""
    if interaction.user.id not in trusted_admins:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    user_id = str(user.id)

    if user_id not in banned_users:
        await interaction.response.send_message(
            f"{user.mention} is not currently banned.",
            ephemeral=True
        )
        return

    del banned_users[user_id]
    save_banned_users()

    logging.info(f"User {user.name} (ID: {user_id}) unbanned")
    await interaction.response.send_message(
        f"{user.mention} has been unbanned.",
        ephemeral=True
    )

    try:
        await user.send("You have been unbanned from PDH LFG Bot.")
    except Exception as e:
        logging.error(f"Failed to DM unbanned user: {e}")

@client.tree.command(name="listbans", description="List all banned users (super admin only)")
async def listbans(interaction: discord.Interaction):
    """Display all currently banned users."""
    if interaction.user.id not in trusted_admins:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    if not banned_users:
        await interaction.response.send_message(
            "No users are currently banned.",
            ephemeral=True
        )
        return

    ban_list = "**Banned Users:**\n"
    for user_id, data in banned_users.items():
        name = data.get("name", "Unknown")
        reason = data.get("reason", "No reason provided")
        expiration = data.get("expiration")
        exp_text = f" (Expires: <t:{expiration}:R>)" if expiration else " (Permanent)"
        ban_list += f"- **{name}** (ID: {user_id}) - {reason}{exp_text}\n"

    await interaction.response.send_message(ban_list, ephemeral=True)

@client.tree.command(name="banserver", description="Ban a server from using the bot (super admin only)")
async def banserver(interaction: discord.Interaction, server_id: str):
    """Ban a server and force the bot to leave."""
    if interaction.user.id not in trusted_admins:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    try:
        server_id_int = int(server_id)
        banned_servers.add(server_id_int)
        save_banned_servers()
        
        logging.info(f"Server ID {server_id_int} banned by {interaction.user.name}")

        # Leave the server if currently in it
        guild = discord.utils.get(client.guilds, id=server_id_int)
        if guild:
            await guild.leave()
            logging.info(f"Left banned server: {guild.name}")

        await interaction.response.send_message(
            f"Server with ID {server_id_int} has been banned.",
            ephemeral=True
        )
    except ValueError:
        await interaction.response.send_message(
            "Invalid server ID. Please provide a numeric server ID.",
            ephemeral=True
        )

@client.tree.command(name="unbanserver", description="Unban a server (super admin only)")
async def unbanserver(interaction: discord.Interaction, server_id: str):
    """Remove a server's ban."""
    if interaction.user.id not in trusted_admins:
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    try:
        server_id_int = int(server_id)
        
        if server_id_int in banned_servers:
            banned_servers.remove(server_id_int)
            save_banned_servers()
            logging.info(f"Server ID {server_id_int} unbanned by {interaction.user.name}")
            await interaction.response.send_message(
                f"Server with ID {server_id_int} has been unbanned.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Server with ID {server_id_int} is not currently banned.",
                ephemeral=True
            )
    except ValueError:
        await interaction.response.send_message(
            "Invalid server ID. Please provide a numeric server ID.",
            ephemeral=True
        )

@client.tree.command(name="listadmins", description="List all bot administrators")
async def listadmins(interaction: discord.Interaction):
    """Display all trusted admin user IDs."""
    try:
        if trusted_admins:
            admin_list = "\n".join([f"- <@{admin_id}>" for admin_id in trusted_admins])
            await interaction.response.send_message(
                f"**Trusted Admins:**\n{admin_list}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No trusted admins found.",
                ephemeral=True
            )
    except Exception as e:
        logging.error(f"Error listing admins: {e}")
        await interaction.response.send_message(
            "An error occurred.",
            ephemeral=True
        )

# -------------------------------------------------------------------------
# Start Bot
# -------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        client.run(TOKEN)
    except Exception as e:
        logging.critical(f"Failed to start bot: {e}")
