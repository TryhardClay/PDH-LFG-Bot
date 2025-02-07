import asyncio
from discord import Client, Embed, HTTPException
from retrying import retry

@retry(stop_max_attempt_number=3, wait_fixed=2000)
async def safe_send_message(channel, content=None, embed=None):
    try:
        if content:
            await channel.send(content=content)
        elif embed:
            await channel.send(embed=embed)
    except HTTPException as e:
        print(f"Error sending message: {e}")

async def safe_edit_message(message, new_content=None, new_embed=None):
    try:
        if new_content:
            await message.edit(content=new_content)
        elif new_embed:
            await message.edit(embed=new_embed)
    except HTTPException as e:
        print(f"Error editing message: {e}")

async def safe_delete_message(message):
    try:
        await message.delete()
    except HTTPException as e:
        print(f"Error deleting message: {e}")
