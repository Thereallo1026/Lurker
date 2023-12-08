import os
import json
import discord
import aiofiles

from multiprocessing import Process
from dotenv import load_dotenv
from discord.ext import commands, tasks
from flask import Flask, jsonify

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

json_dir = './json/' 
os.makedirs(json_dir, exist_ok=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    check_presence.start()

@bot.command()
async def hello(ctx):
    await ctx.send('my name is emu otori, emu is meaning smile')

users = [454920881177624576, 704939945437167666]
PresenceData = {}

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

async def construct_presence_data(guild, userId):
    member = guild.get_member(userId)
    if not member:
        return None

    current_status = {
        "name": member.name,
        "id": member.id,
        "status": str(member.status) if member.status else None,
        'customStatus': str(member.activity) if member.activity else None,
        "activity": await getActivity(member) if member.activities else None,
    }
    return current_status

@tasks.loop(seconds=3)
async def check_presence():
    channel = bot.get_channel(1141536147391127562)
    guild = bot.get_guild(1131126447340261398)
    if guild:
        for userId in users:
            current_status = await construct_presence_data(guild, userId)
            if current_status and (userId not in PresenceData or PresenceData[userId] != current_status):
                PresenceData[userId] = current_status
                async with aiofiles.open(os.path.join(json_dir, f'{userId}.json'), mode='w', encoding='utf-8') as file:
                    await file.write(json.dumps(current_status, ensure_ascii=False))
                await channel.send(f'Updated `{userId}` ```json\n{json.dumps(current_status, indent=4, ensure_ascii=False)}```')

@app.route('/status/<int:user_id>', methods=['GET'])
async def get_status(user_id):
    try:
        async with aiofiles.open(os.path.join(json_dir, f'{user_id}.json'), mode='r', encoding='utf-8') as file:
            user_status = await file.read()
        return jsonify(json.loads(user_status))
    except Exception as e:
        return jsonify({"error": True, "message": "User not found or no data available"}), 404

def run_bot():
    load_dotenv()
    token = os.getenv('TOKEN')
    bot.run(token)

def run_flask():
    app.run(port=5000, use_reloader=False)

def run_bot():
    load_dotenv()
    token = os.getenv('TOKEN')
    bot.run(token)

def run_flask():
    app.run(port=1337, use_reloader=False)

if __name__ == "__main__":
    p1 = Process(target=run_bot)
    p2 = Process(target=run_flask)

    p1.start()
    p2.start()

    p1.join()
    p2.join()