import discord
from discord.ext import commands
from services.tablestream_service import generate_tablestream_link

class GameRequestCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="gamerequest", help="Generate a personal TableStream game link.")
    async def gamerequest(self, ctx):
        # Simulate a test game payload
        test_game = {
            "id": 1,
            "format": "MTGCommander",
            "players": 4
        }
        
        room_url, password = await generate_tablestream_link(test_game)

        if room_url:
            await ctx.send(f"API test successful! Room URL: {room_url}")
        else:
            await ctx.send("API test failed. Please check the server or API configuration.")

async def setup(bot):
    await bot.add_cog(GameRequestCommand(bot))
