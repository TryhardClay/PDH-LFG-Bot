# commands/games.py

import discord
from discord.ext import commands
from services.game_service import save_active_lfg_request

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="biglfg", help="Create a cross-server LFG request and automatically manage player listings.")
    async def big_lfg(self, ctx, game_format: str, max_players: int = 4):
        request = {
            "id": ctx.message.id,
            "host": ctx.author.id,
            "game_format": game_format,
            "max_players": max_players,
            "players": [ctx.author.id]
        }
        save_active_lfg_request(request)
        await ctx.send(f"LFG game created by {ctx.author.mention} in format {game_format} for {max_players} players.")

async def setup(bot):
    await bot.add_cog(GameCommands(bot))
