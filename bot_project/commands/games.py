import discord
from discord.ext import commands
from services.game_service import load_active_lfg_requests, save_active_lfg_request, remove_lfg_request

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="creategame", help="Create a new game and look for players.")
    async def create_game(self, ctx, game_format: str, max_players: int = 4):
        request = {
            "id": ctx.message.id,
            "host": ctx.author.id,
            "game_format": game_format,
            "max_players": max_players,
            "players": [ctx.author.id]
        }
        save_active_lfg_request(request)
        await ctx.send(f"Game created by {ctx.author.mention} in format {game_format} for {max_players} players.")

    @commands.command(name="leavegame", help="Leave an active game.")
    async def leave_game(self, ctx, game_id: int):
        active_requests = load_active_lfg_requests()
        game_request = next((req for req in active_requests if req["id"] == game_id), None)

        if game_request and ctx.author.id in game_request["players"]:
            game_request["players"].remove(ctx.author.id)
            if not game_request["players"]:
                remove_lfg_request(game_id)
                await ctx.send(f"Game {game_id} has been removed due to no players.")
            else:
                await ctx.send(f"{ctx.author.mention} left the game.")
        else:
            await ctx.send("You are not part of this game or it does not exist.")

async def setup(bot):
    await bot.add_cog(GameCommands(bot))
