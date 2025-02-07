import discord
from discord.ext import commands
import os
from config.settings import settings

intents = discord.Intents.default()
intents.message_content = True  # Ensure the bot can read message content

# Initialize bot
bot = commands.Bot(command_prefix=settings.BOT_PREFIX, intents=intents)

# Load cogs (commands)
async def load_cogs():
    for filename in os.listdir("./commands"):
        if filename.endswith(".py"):
            cog = filename[:-3]
            try:
                await bot.load_extension(f"commands.{cog}")
                print(f"Loaded {cog}")
            except Exception as e:
                print(f"Failed to load {cog}: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await load_cogs()  # Load cogs when the bot is ready

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Please check your input.")
    else:
        await ctx.send(f"An error occurred: {error}")
        print(f"Error: {error}")

# Start the bot
if __name__ == "__main__":
    bot.run(settings.DISCORD_BOT_TOKEN)
