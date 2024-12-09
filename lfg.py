import discord
from discord.ext import commands, tasks
import requests
import asyncio

class LFG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lfg_list = []
        self.check_for_games.start()

    def cog_unload(self):
        self.check_for_games.cancel()

    @discord.slash_command(name="xserverlfg", description="Add yourself to the Looking-For-Group queue")  # Corrected decorator
    async def xserverlfg(self, ctx: discord.ApplicationContext):  # Corrected context
        user = ctx.author  # Access user from context
        if user.id not in self.lfg_list:
            self.lfg_list.append(user.id)
            await ctx.respond(f"{user.mention} has been added to the LFG queue.", ephemeral=True)  # Use ctx.respond()
        else:
            await ctx.respond(f"{user.mention} is already in the LFG queue.", ephemeral=True)  # Use ctx.respond()

    @tasks.loop(seconds=60)  # Check every minute
    async def check_for_games(self):
        if len(self.lfg_list) >= 4:
            players = self.lfg_list[:4]
            self.lfg_list = self.lfg_list[4:]

            # Create game room using Table Stream API
            room_name = "SB1"  # You might want to generate unique names
            game_link = await self.create_game_room(room_name)

            if game_link:
                for player_id in players:
                    player = self.bot.get_user(player_id)
                    if player:
                        try:
                            await player.send(f"Game ready! Join here: {game_link}")
                        except discord.HTTPException:
                            print(f"Failed to DM {player.name}")
            else:
                print("Failed to create a game room.")

    async def create_game_room(self, room_name):
        url = "https://api.table-stream.com/create-room"
        headers = {
            "Content-Type": "application/json"
            # Add any required authentication headers here
        }
        data = {
            "roomName": room_name,
            "gameType": "MTGCommander",
            "maxPlayers": 4,
            "private": True
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()  # Raise an exception for bad status codes
            # Assuming the API returns the game link in the response
            return response.json().get("gameLink")
        except requests.exceptions.RequestException as e:
            print(f"Error creating game room: {e}")
            return None

async def setup(bot):
    await bot.add_cog(LFG(bot))