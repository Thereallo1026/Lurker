import os
import json
import discord
import aiofiles
import datetime

from multiprocessing import Process
from dotenv import load_dotenv
from discord.ext import commands, tasks
from flask import Flask, jsonify

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

json_dir = './json/' 
os.makedirs(json_dir, exist_ok=True)

async def load_config():
    try:
        async with aiofiles.open('./config.json', mode='r', encoding='utf-8') as file:
            return json.loads(await file.read())
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    check_presence.start()

@bot.command()
@commands.is_owner()
async def add(ctx, user_id: int):
    if user_id not in bot.users_list:
        bot.users_list.append(user_id)
        async with aiofiles.open('./list.json', 'w') as file:
            await file.write(json.dumps(bot.users_list))
        await ctx.send(f'User ID `{user_id}` added.')
    else:
        await ctx.send(f'User ID `{user_id}` is already in the list.')

@bot.command()
async def list(ctx):
    await ctx.send(f'```json\n{json.dumps(bot.users_list, indent=4, ensure_ascii=False)}```')

@bot.command()
async def config(ctx):
    await ctx.send(f'```json\n{json.dumps(bot.config, indent=4, ensure_ascii=False)}```')

@bot.command()
@commands.is_owner()
async def channel(ctx, id):
    try:
        id = int(id)
    except ValueError:
        await ctx.send(f'Invalid channel ID: `{id}`')
        return
    try:
        async with aiofiles.open('./config.json', 'r') as file:
            config = json.loads(await file.read())
    except Exception as e:
        await ctx.send(f'Error loading configuration: {e}')
        return
    
    config['channel'] = id
    try:
        async with aiofiles.open('./config.json', 'w') as file:
            await file.write(json.dumps(config))
        await ctx.send(f'Updated alerts channel to `{id}`')
    except Exception as e:
        await ctx.send(f'Error updating configuration: {e}')


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
                "twitchName": activity.twitch_name if activity.twitch_name else None,
                "url": activity.url if activity.url else None,
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
                "timestamps": {
                    "start": activity.start if activity.start else None,
                    "end": activity.end if activity.end else None
                },
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

    def datetime_to_timestamp(dt):
        return int(dt.timestamp()) if isinstance(dt, datetime.datetime) else None

    current_status = {
        "name": member.name,
        "id": member.id,
        "status": str(member.status) if member.status else None,
        'customStatus': str(member.activity) if member.activity else None,
        "activity": await getActivity(member) if member.activities else None,
    }

    if "activity" in current_status and current_status["activity"]:
        for activity in current_status["activity"]:
            if "timestamps" in activity:
                if "start" in activity["timestamps"] and isinstance(activity["timestamps"]["start"], datetime.datetime):
                    activity["timestamps"]["start"] = datetime_to_timestamp(activity["timestamps"]["start"])
                if "end" in activity["timestamps"] and isinstance(activity["timestamps"]["end"], datetime.datetime):
                    activity["timestamps"]["end"] = datetime_to_timestamp(activity["timestamps"]["end"])

    return current_status

@tasks.loop(seconds=5)
async def check_presence():
    bot.config = await load_config()
    if bot.config:
        bot.users_list = bot.config.get("list", [])
        bot.channel_id = bot.config.get("channel")
        bot.send_alerts = bot.config.get("alerts", False)
        channel = bot.get_channel(bot.channel_id)
        guild = bot.get_guild(1131126447340261398)
        if guild and channel:
            for userId in bot.users_list:
                current_status = await construct_presence_data(guild, userId)
                if current_status and (userId not in PresenceData or PresenceData[userId] != current_status):
                    PresenceData[userId] = current_status
                    async with aiofiles.open(os.path.join(json_dir, f'{userId}.json'), mode='w', encoding='utf-8') as file:
                        await file.write(json.dumps(current_status, ensure_ascii=False))
                    if bot.send_alerts:
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
    app.run(port=1337, use_reloader=False, host="0.0.0.0")

if __name__ == "__main__":
    p1 = Process(target=run_bot)
    p2 = Process(target=run_flask)

    p1.start()
    p2.start()

    p1.join()
    p2.join()