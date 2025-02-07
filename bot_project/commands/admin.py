# commands/admin.py

import discord
from discord.ext import commands
import uuid

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

@client.tree.command(name="setchannel", description="Set the channel for cross-server communication. (admin)")
@commands.has_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel, filter: str):
    """
    Assign a channel for cross-server communication and apply a filter.
    Only available to server administrators.
    """
    if not interaction.user.guild_permissions.administrator:
        logging.warning(f"Unauthorized /setchannel attempt by {interaction.user.name} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    filter = filter.lower()
    if filter not in ("cpdhtxt", "cpdhlfg", "casualtxt", "casuallfg"):
        await interaction.response.send_message("Invalid filter. Please specify 'cpdhtxt', 'cpdhlfg', 'casualtxt', or 'casuallfg'.", ephemeral=True)
        return

    webhook = await channel.create_webhook(name="Cross-Server Bot Webhook")
    WEBHOOK_URLS[f'{interaction.guild.id}_{channel.id}'] = {'url': webhook.url, 'id': webhook.id}
    CHANNEL_FILTERS[f'{interaction.guild.id}_{channel.id}'] = filter  # Store filter as a string
    save_webhook_data()
    save_channel_filters()

    logging.info(f"Admin {interaction.user.name} set {channel.mention} as a cross-server channel with filter '{filter}'")
    await interaction.response.send_message(f"Cross-server communication channel set to {channel.mention} with filter '{filter}'.", ephemeral=True)

@client.tree.command(name="disconnect", description="Disconnect a channel from cross-server communication. (admin)")
@commands.has_permissions(administrator=True)
async def disconnect(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    Remove a channel from the cross-server communication network.
    Only available to server administrators.
    """
    if not interaction.user.guild_permissions.administrator:
        logging.warning(f"Unauthorized /disconnect attempt by {interaction.user.name} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    channel_id = f'{interaction.guild.id}_{channel.id}'
    if channel_id in WEBHOOK_URLS:
        del WEBHOOK_URLS[channel_id]
        save_webhook_data()

        logging.info(f"Admin {interaction.user.name} disconnected {channel.mention} from cross-server communication.")
        await interaction.response.send_message(f"Disconnected {channel.mention} from cross-server communication.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{channel.mention} is not connected to cross-server communication.", ephemeral=True)

@client.tree.command(name="listconnections", description="List connected channels for cross-server communication.")
@has_permissions(manage_channels=True)
async def listconnections(interaction: discord.Interaction):
    """
    Display all active channel connections and their filters across servers.
    """
    try:
        if WEBHOOK_URLS:
            connections = "\n".join(
                [f"- <#{channel.split('_')[1]}> in {client.get_guild(int(channel.split('_')[0])).name} "
                 f"(filter: {CHANNEL_FILTERS.get(channel, 'none')})"
                 for channel in WEBHOOK_URLS]
            )
            await interaction.response.send_message(f"Connected channels:\n{connections}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no connected channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error listing connections: {e}")
        await interaction.response.send_message("An error occurred while listing connections.", ephemeral=True)

@client.tree.command(name="updateconfig", description="Reload the bot's configuration and resync commands. (admin)")
@commands.has_permissions(administrator=True)
async def updateconfig(interaction: discord.Interaction):
    """
    Reload the bot's configuration from persistent storage, resynchronize commands,
    and provide feedback on updates. Only available to server administrators.
    """
    if not interaction.user.guild_permissions.administrator:
        logging.warning(f"Unauthorized /updateconfig attempt by {interaction.user.name} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    try:
        await interaction.response.defer(ephemeral=True)

        # Reload configuration files
        global WEBHOOK_URLS, CHANNEL_FILTERS
        WEBHOOK_URLS = load_webhook_data()
        CHANNEL_FILTERS = load_channel_filters()

        # Resynchronize the command tree
        await client.tree.sync()

        logging.info(f"Admin {interaction.user.name} reloaded bot configuration and resynced commands.")
        await interaction.followup.send("Configuration reloaded successfully and command tree synchronized!", ephemeral=True)

    except Exception as e:
        logging.error(f"Error during /updateconfig: {e}")
        await interaction.followup.send(f"An error occurred while reloading configuration or syncing commands: {e}", ephemeral=True)

@client.tree.command(name="addspelltable", description="Add a SpellTable link (only links starting with 'https://').")
async def addspelltable(interaction: discord.Interaction, link: str):
    """
    Command to allow users to add a SpellTable link. Only links starting with 'https://' are permitted.
    The link is distributed to all connected channels with the same filter.
    """
    if not link.startswith("https://"):
        await interaction.response.send_message(
            "Invalid input. Please enter a valid link starting with 'https://'.",
            ephemeral=True
        )
        return

    # Prepare the message to be sent to channels
    embed = discord.Embed(
        title="New SpellTable Link Added",
        description=f"**SpellTable Link:** {link}",
        color=discord.Color.green()
    )
    embed.set_author(name="PDH LFG Bot", icon_url=IMAGE_URL)

    source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
    source_filter = str(CHANNEL_FILTERS.get(source_channel_id, 'none'))

    # Distribute the embed to all connected channels with the same filter
    sent_to_channels = 0
    for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
        destination_filter = str(CHANNEL_FILTERS.get(destination_channel_id, 'none'))
        if source_filter == destination_filter:
            destination_channel = client.get_channel(int(destination_channel_id.split('_')[1]))
            if destination_channel:
                await destination_channel.send(embed=embed)
                sent_to_channels += 1

    # Respond to the user with success or failure
    if sent_to_channels > 0:
        await interaction.response.send_message(
            f"SpellTable link successfully distributed to {sent_to_channels} channel(s).", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "No connected channels were found with the same filter to distribute the link.", ephemeral=True
        )

@client.tree.command(name="about", description="Show information about the bot and its commands.")
async def about(interaction: discord.Interaction):
    """
    Display details about the bot, its available commands, and the rules for use.
    """
    try:
        embed = discord.Embed(
            title="PDH LFG Bot - Information & Commands",
             description=(
                "This bot allows players to connect and coordinate games across different servers "
                "through shared announcements, player listings, and automated room creation. "
                "Below are the commands and features available.\n\n"
                "**Note:** Restricted commands require admin privileges or special access."
            ),
            color=discord.Color.blue()
        )

        # 📜 Rules Section
        embed.add_field(
            name="📜 Rules:",
            value=(
                "1️⃣ **Respect Others** - Treat all players with kindness and fairness.\n"
                "2️⃣ **No Harassment** - Any form of harassment, hate speech, or discrimination will result in bans.\n"
                "3️⃣ **Follow Server Guidelines** - Abide by each server's unique rules while using this bot.\n"
                "4️⃣ **No Spamming** - Avoid excessive message spam, command misuse, or abuse of LFG features.\n"
                "5️⃣ **No Poaching Users** - This bot is designed to bridge the gap between servers and not as a tool to grow your empire.\n"
                "6️⃣ **Report Issues** - If you encounter issues, inform the server admin; or reach out to **Clay** (User ID: 582548598584115211) on Discord or email: **gaming4tryhards@gmail.com**\n\n"
                "**🚨 Compliance Failure:** Breaking these rules may result in a user ID ban."
            ),
            inline=False
        )

        # 🌎 Public Commands
        embed.add_field(
            name="🌎 Public Commands:",
             value=(
                "**/biglfg** - Create a cross-server LFG request and automatically manage player listings.\n"
                "**/gamerequest** - Generate a personal TableStream game link.\n"
                "**/addspelltable** - Add your own custom SpellTable link to an lfg chat.\n"
                "**/about** - Display details about the bot, commands, and usage."
            ),
            inline=False
        )

        # 🔐 Admin Commands
        embed.add_field(
            name="🔐 Admin Commands (Server Admins Only):",
            value=(
                "**/setchannel (admin)** - Set a channel for cross-server communication.\n"
                "**/disconnect (admin)** - Remove a channel from cross-server communication.\n"
                "**/listadmins (admin)** - Display a list of current bot super admins."
            ),
            inline=False
        )

        # 🚨 Restricted Commands (Super Admins Only)
        embed.add_field(
            name="🚨 Restricted Commands (Super Admins Only):",
            value=(
                "**/banuser (restricted)** - Ban a user by User ID # from posting in bot-controlled channels and using commands.\n"
                "**/unbanuser (restricted)** - Unban a previously banned user.\n"
                "**/banserver (restricted)** - Ban a server by Server ID # from accessing the bot.\n"
                "**/unbanserver (restricted)** - Unban a previously banned server.\n"
                "**/listbans (restricted)** - Display a list of currently banned users along with their details.\n"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /about command: {e}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

@client.tree.command(name="gamerequest", description="Generate a test game request to verify TableStream integration.")
async def gamerequest(interaction: discord.Interaction):
    """
    Test command to generate a TableStream game request and display the link and password.
    """
    try:
        await interaction.response.defer(ephemeral=True)

        # Game data
        game_data = {
            "id": str(uuid.uuid4())  # Unique game ID
        }
        game_format = GameFormat.PAUPER_EDH
        player_count = 4

        logging.info(f"Preparing to generate TableStream link with game_data: {game_data}, game_format: {game_format}, player_count: {player_count}")

        # Generate TableStream link
        game_link, game_password = await generate_tablestream_link(game_data, game_format, player_count)

        # Handle the response
        if game_link:
            response_message = (
                f"**Game Request Generated Successfully!**\n\n"
                f"**Link:** {game_link}\n"
                f"**Password:** {game_password if game_password else 'No password required'}"
            )
        else:
            response_message = "Failed to generate the game request. Please check the configuration and try again."

        await interaction.followup.send(response_message, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in /gamerequest command: {e}")
        await interaction.followup.send("An error occurred while processing the game request.", ephemeral=True)

@client.tree.command(name="biglfg", description="Create a cross-server LFG request.")
async def biglfg(interaction: discord.Interaction):
    """
    Handles the creation and propagation of BigLFG embeds across connected servers
    with rate-limit handling for multiple destinations.
    """
    # Check if the user is banned
    user_id = str(interaction.user.id)
    if user_id in banned_users:
        logging.warning(f"Banned user {interaction.user.name} (ID: {user_id}) attempted to use /biglfg.")
        await interaction.response.send_message(
            "You are currently banned from using this command. Please contact an admin if you believe this is an error.",
            ephemeral=True
        )
        # DM the user to notify them of their restriction
        try:
            await interaction.user.send(
                "You attempted to use the /biglfg command but are currently banned from using it. "
                "Please contact an admin to resolve this issue."
            )
        except Exception as e:
            logging.error(f"Failed to send DM to banned user {interaction.user.name} (ID: {user_id}): {e}")
        return

    # Proceed with the normal /biglfg functionality if the user is not banned
    try:
        await interaction.response.defer()

        # Generate a unique UUID for this LFG instance
        lfg_uuid = str(uuid.uuid4())

        source_channel_id = f'{interaction.guild.id}_{interaction.channel.id}'
        source_filter = str(CHANNEL_FILTERS.get(source_channel_id, 'none'))  # Ensure string type

        # Create the initial embed
        embed = discord.Embed(
            title="Looking for more players...",
            color=discord.Color.yellow(),
            description="React below to join the game!",
        )
        embed.set_author(
            name="PDH LFG Bot",
            icon_url=IMAGE_URL,  # Add the image to the author section
            url="https://github.com/TryhardClay/PDH-LFG-Bot"
        )
        embed.set_thumbnail(url=IMAGE_URL)  # Add the image as a thumbnail
        embed.add_field(name="Players:", value=f"1. {interaction.user.name}", inline=False)

        # Track the BigLFG embed
        sent_messages = {}
        for destination_channel_id, webhook_data in WEBHOOK_URLS.items():
            destination_filter = str(CHANNEL_FILTERS.get(destination_channel_id, 'none'))  # Ensure string type
            # Only send embeds to *lfg channels
            if source_filter.endswith('lfg') and destination_filter.endswith('lfg') and source_filter == destination_filter:
                destination_channel = client.get_channel(int(destination_channel_id.split('_')[1]))
                if destination_channel:
                    # Introduce a small delay to prevent rate-limiting
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                    sent_message = await destination_channel.send(embed=embed, view=create_lfg_view())
                    if sent_message:
                        sent_messages[destination_channel_id] = sent_message

        if sent_messages:
            active_embeds[lfg_uuid] = {
                "players": {interaction.user.id: interaction.user.name},
                "messages": sent_messages,
                "task": asyncio.create_task(lfg_timeout(lfg_uuid)),
            }
            await interaction.followup.send("BigLFG request sent successfully!", ephemeral=True)
        else:
            await interaction.followup.send("Failed to send BigLFG request to any channels.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error in BigLFG command: {e}")
        await interaction.followup.send("An error occurred while processing the BigLFG request.", ephemeral=True)

@client.tree.command(name="banuser", description="Ban a user from interacting with bot-controlled channels. (restricted)")
async def banuser(interaction: discord.Interaction, user: discord.User, reason: str):
    """
    Bans a user from interacting with bot-controlled channels.
    First offense = 3-day temporary ban. Second offense = Permanent ban.
    """
    if interaction.user.id not in trusted_admins:
        logging.warning(f"Unauthorized /banuser attempt by {interaction.user} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    user_id = str(user.id)
    user_name = user.name

    # Determine if the user already served a temporary ban
    if user_id in banned_users and banned_users[user_id]["expiration"] is not None:
        ban_expiration = None  # Permanent ban
        ban_type = "Permanent"
    else:
        ban_expiration = int(time.time()) + (3 * 24 * 60 * 60)  # 3 days from now
        ban_type = "Temporary (3 days)"

    # Store ban data
    banned_users[user_id] = {
        "User ID#": user_name,
        "reason": reason,
        "expiration": ban_expiration
    }
    save_banned_users()

    # Log and send confirmation
    logging.info(f"{ban_type} ban issued: {user_name} (ID: {user_id}) - Reason: {reason}")
    await interaction.response.send_message(f"{ban_type} ban issued for {user.mention}.\n**Reason:** {reason}", ephemeral=True)

    # DM the banned user
    try:
        dm_message = (
            f"You have been issued a **{ban_type} Ban** which will prevent you from interacting within bot-controlled channels.\n"
            f"**Reason:** {reason}\n"
            f"{'Your ban will expire in 3 days.' if ban_expiration else 'Your ban is permanent until reviewed.'}\n\n"
            f"For appeals, inform the server admin, reach out to Clay (User ID: 582548598584115211) on Discord, "
            f"or email: gaming4tryhards@gmail.com."
        )
        await user.send(dm_message)
    except Exception as e:
        logging.error(f"Failed to send ban DM to {user_name}: {e}")


@client.tree.command(name="unbanuser", description="Unban a user from bot-controlled channels. (restricted)")
async def unbanuser(interaction: discord.Interaction, user: discord.User):
    """
    Unbans a user, restoring access to bot-controlled channels.
    """
    if interaction.user.id not in trusted_admins:
        logging.warning(f"Unauthorized /unbanuser attempt by {interaction.user} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    user_id = str(user.id)

    if user_id not in banned_users:
        await interaction.response.send_message(f"{user.mention} is not currently banned.", ephemeral=True)
        return

    # Remove user from banned list
    del banned_users[user_id]
    save_banned_users()

    logging.info(f"User {user.name} (ID: {user_id}) has been unbanned.")
    await interaction.response.send_message(f"{user.mention} has been unbanned.", ephemeral=True)

    # DM the unbanned user
    try:
        await user.send("You have been unbanned and can now interact in bot-controlled channels again.")
    except Exception as e:
        logging.error(f"Failed to send unban DM to {user.name}: {e}")

@client.tree.command(name="listbans", description="List all currently banned users. (restricted)")
async def listbans(interaction: discord.Interaction):
    """
    Lists all users who are currently banned.
    """
    if interaction.user.id not in trusted_admins:
        logging.warning(f"Unauthorized /listbans attempt by {interaction.user} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if not banned_users:
        await interaction.response.send_message("No users are currently banned.", ephemeral=True)
        return

    # Generate a ban list message
    ban_list = "**Banned Users:**\n"
    for user_id, data in banned_users.items():
        user_name = data.get("name", "Unknown")  # Default to 'Unknown' if the name key is missing
        expiration = f" (Expires: <t:{data['expiration']}:R>)" if data["expiration"] else " (Permanent)"
        ban_list += f"- **{user_name}** (ID: {user_id}) - **Reason:** {data.get('reason', 'No reason provided')}{expiration}\n"

    await interaction.response.send_message(ban_list, ephemeral=True)

@client.tree.command(name="banserver", description="Ban a server from using the bot. (restricted)")
async def banserver(interaction: discord.Interaction, server_id: int):
    """
    Bans a server from using the bot, forcing the bot to leave immediately.
    Restricted to super admins.
    """
    if interaction.user.id not in trusted_admins:
        logging.warning(f"Unauthorized /banserver attempt by {interaction.user.name} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    banned_servers.add(server_id)  # Add server ID to the banned list
    logging.info(f"Server with ID {server_id} has been banned by {interaction.user.name}.")

    # Check if the bot is currently in the banned server
    guild = discord.utils.get(client.guilds, id=server_id)
    if guild:
        await guild.leave()
        logging.info(f"Bot left the banned server: {guild.name} (ID: {server_id})")

    await interaction.response.send_message(f"Server with ID {server_id} has been banned successfully.", ephemeral=True)

@client.tree.command(name="unbanserver", description="Unban a server from using the bot. (restricted)")
async def unbanserver(interaction: discord.Interaction, server_id: int):
    """
    Unbans a server, allowing it to use the bot again.
    Restricted to super admins.
    """
    if interaction.user.id not in trusted_admins:
        logging.warning(f"Unauthorized /unbanserver attempt by {interaction.user.name} (ID: {interaction.user.id})")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if server_id in banned_servers:
        banned_servers.remove(server_id)
        logging.info(f"Server with ID {server_id} has been unbanned by {interaction.user.name}.")
        await interaction.response.send_message(f"Server with ID {server_id} has been unbanned successfully.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Server with ID {server_id} is not currently banned.", ephemeral=True)

@client.tree.command(name="listadmins", description="List all trusted administrators.")
async def listadmins(interaction: discord.Interaction):
    """
    Display all trusted admin user IDs.
    """
    try:
        trusted_admins = load_trusted_admins()
        if trusted_admins:
            admin_list = "\n".join([f"- <@{admin_id}>" for admin_id in trusted_admins])
            await interaction.response.send_message(f"Trusted Admins:\n{admin_list}", ephemeral=True)
        else:
            await interaction.response.send_message("No trusted admins found.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error retrieving trusted admins: {e}")
        await interaction.response.send_message("An error occurred while retrieving the list.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
