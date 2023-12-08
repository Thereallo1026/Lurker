import os
import json
import discord

from dotenv import load_dotenv
from discord.ext import commands, tasks

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


@bot.event
async def on_ready():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f'Logged in as {bot.user.name}')
    check_presence.start()


@bot.command()
async def hello(ctx):
    await ctx.send('my name is emu otori, emu is meaning smile')

users = [454920881177624576]
Presencedata = {}


async def getActivity(member):
    activities = []
    for activity in member.activities:
        if isinstance(activity, discord.Game):
            activities.append({
                "type": "Game",
                "name": activity.name
            })
        elif isinstance(activity, discord.Streaming):
            activities.append({
                "type": "Streaming",
                "name": activity.name,
                "details": activity.details if activity.details else None,
                "state": activity.state if activity.state else None,
            })
        elif isinstance(activity, discord.Spotify):
            activities.append({
                "type": "Spotify",
                "trackId": activity.track_id,
                "trackName": activity.title,
                "artist": activity.artist,
                "album": activity.album,
                "albumCoverUrl": activity.album_cover_url,
                "state": "Playing" if activity is not None else "Not Playing"
            })
        elif isinstance(activity, discord.Activity):
            activities.append({
                "type": "Rich Presence",
                "name": str(activity.name),
                "state": activity.state if activity.state else None,
                "details": activity.details if activity.details else None,
                "images": {
                    "large": {"text": activity.large_image_text if activity.large_image_text else None,
                              "url": activity.large_image_url if activity.large_image_url else None},
                    "small": {"text": activity.small_image_text if activity.small_image_text else None,
                              "url": activity.small_image_url if activity.small_image_url else None
                              }
                }
            })
    return activities if activities else [{"type": "None"}]

@tasks.loop(seconds=3)
async def check_presence():
    channel = bot.get_channel(1141536147391127562)
    guild = bot.get_guild(1131126447340261398)
    if guild:
        for user_id in users:
            member = guild.get_member(user_id)
            if member:
                current_status = {
                    "name": member.name,
                    "status": str(member.status),
                    'customStatus': str(member.activity) if member.activity else None,
                    "activity": await getActivity(member),
                }
                if user_id not in Presencedata or Presencedata[user_id] != current_status:
                    Presencedata[user_id] = current_status
                    await channel.send(f'```json\n{json.dumps(current_status, indent=2, ensure_ascii=False)}\n```')

load_dotenv()
bot.run(os.getenv('TOKEN'))
