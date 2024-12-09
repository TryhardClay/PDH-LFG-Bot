# biglfg.py
import asyncio
import datetime
import discord

from bot import client, logging, big_lfg_data, WEBHOOK_URLS  # Import necessary variables and client


# BigLFG command with timeout and "full" features
@client.tree.command(name="biglfg", description="Create a BigLFG prompt with reactions.")  # Changed to lowercase
async def biglfg(interaction: discord.Interaction, prompt: str):  # Changed to lowercase
    embed = discord.Embed(title=prompt, description="React with 👍 to join!")
    message_ids = []

    # Send the embed to all connected channels
    for channel_id in WEBHOOK_URLS:
        channel = client.get_channel(int(channel_id.split('_')[1]))
        message = await channel.send(embed=embed)
        await message.add_reaction("👍")  # Add thumbs up reaction
        message_ids.append(f"{message.id}_{channel.id}")

    # Store BigLFG data
    big_lfg_data[message.id] = {
        "prompt": prompt,
        "start_time": datetime.datetime.now(),
        "timeout": datetime.timedelta(minutes=15),  # 15-minute timeout
        "max_thumbs_up": 4,
        "thumbs_up_count": 0,
        "message_ids": message_ids
    }


async def update_big_lfg():
    while True:
        await asyncio.sleep(5)  # Update every 5 seconds
        for lfg_id, lfg_data in big_lfg_data.copy().items():  # Use a copy to avoid errors when deleting
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

            # Update thumbs up count
            for message_id in lfg_data["message_ids"]:
                try:
                    channel = client.get_channel(int(message_id.split('_')[1]))
                    message = await channel.fetch_message(int(message_id.split('_')[0]))
                    for reaction in message.reactions:
                        if reaction.emoji == "👍":
                            lfg_data["thumbs_up_count"] = reaction.count - 1  # Subtract 1 for the bot's reaction
                            break  # No need to check other reactions
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


# Start the BigLFG update task
asyncio.create_task(update_big_lfg())
