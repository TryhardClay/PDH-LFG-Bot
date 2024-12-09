# events.py
import discord
import asyncio  # Import asyncio for task creation

from bot import client, logging, WEBHOOK_URLS, CHANNEL_FILTERS  # Import necessary variables and client
import biglfg  # Import the biglfg module


@client.event
async def on_ready():
    global WEBHOOK_URLS, CHANNEL_FILTERS
    logging.info(f'Logged in as {client.user}')
    try:
        with open('webhooks.json', 'r') as f:
            WEBHOOK_URLS = json.load(f)
    except FileNotFoundError:
        logging.warning("webhooks.json not found. Starting with empty configuration.")
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding webhooks.json: {e}")
    await client.tree.sync()

    # Start the BigLFG update task
    asyncio.create_task(biglfg.update_big_lfg())


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
