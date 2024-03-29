import os
import io
import json
import discord
import aiofiles
import aiohttp
import datetime

from multiprocessing import Process
from dotenv import load_dotenv
from discord.ext import commands, tasks
from flask import Flask, jsonify
import pytz

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
    check_arc_beta.start()
    check_presence.start()

@bot.command()
@commands.is_owner()
async def add(ctx, user_id: int):
    bot.config = await load_config()
    if user_id not in bot.config["list"]:
        bot.config["list"].append(user_id)
        async with aiofiles.open('./config.json', 'w') as file:
            await file.write(json.dumps(bot.config))
        await ctx.send(f'User ID `{user_id}` added.')
    else:
        await ctx.send(f'User ID `{user_id}` is already in the list.')

@bot.command()
@commands.is_owner()
async def remove(ctx, user_id: int):
    bot.config = await load_config()
    if user_id in bot.config["list"]:
        bot.config["list"].remove(user_id)
        async with aiofiles.open('./config.json', 'w') as file:
            await file.write(json.dumps(bot.config))
        await ctx.send(f'User ID `{user_id}` removed.')
    else:
        await ctx.send(f'User ID `{user_id}` is not in the list.')

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

@bot.command()
@commands.is_owner()
async def arc(ctx):
    value = await fetch_arc_beta()
    await ctx.send(value[0])

@bot.command()
@commands.is_owner()
async def alerts(ctx, value):
    if value.lower() == 'true':
        alerts_value = True
    elif value.lower() == 'false':
        alerts_value = False
    else:
        await ctx.send(f'Invalid value for alerts: `{value}`. Please use "true" or "false".')
        return

    try:
        async with aiofiles.open('./config.json', 'r') as file:
            config = json.loads(await file.read())
    except Exception as e:
        await ctx.send(f'Error loading configuration: {e}')
        return

    config['alerts'] = alerts_value
    try:
        async with aiofiles.open('./config.json', 'w') as file:
            await file.write(json.dumps(config))
        await ctx.send(f'Updated alerts to `{alerts_value}`')
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

    current_status = {}
    if member.name is not None:
        current_status["name"] = member.name
    if member.id is not None:
        current_status["id"] = member.id
    if member.status is not None:
        current_status["status"] = str(member.status)

    if member.activity and isinstance(member.activity, discord.CustomActivity):
        emoji = str(member.activity.emoji) if member.activity.emoji else None
        message = member.activity.name if member.activity.name else None
        if emoji or message:
            current_status['customStatus'] = {"emoji": emoji, "message": message}

    activities = await getActivity(member)
    if activities and activities != [{"type": "None"}]:
        current_status["activity"] = activities

    if "activity" in current_status:
        for activity in current_status["activity"]:
            if "timestamps" in activity:
                start = activity["timestamps"].get("start")
                end = activity["timestamps"].get("end")
                if isinstance(start, datetime.datetime):
                    activity["timestamps"]["start"] = datetime_to_timestamp(start)
                else:
                    activity["timestamps"].pop("start", None)
                if isinstance(end, datetime.datetime):
                    activity["timestamps"]["end"] = datetime_to_timestamp(end)
                else:
                    activity["timestamps"].pop("end", None)

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
                        status_json = json.dumps(current_status, indent=4, ensure_ascii=False)
                        if len(status_json) > 1500:
                            # file
                            with io.BytesIO(status_json.encode('utf-8')) as f:
                                await channel.send(f"Updated `{userId}`:", file=discord.File(f, f'{userId}_status.json'))
                        else:
                            # message
                            await channel.send(f'Updated `{userId}` ```json\n{status_json}```')

CONFIG_FILE = './config.json'
ARC_BETA_KEY = 'arcBeta'

async def fetch_arc_beta():
    url = "https://arc.net/api/get-windows-beta-user-count"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                resp = await response.text()
                print(f"{datetime.datetime.now()} {response.status}: {resp}")
                if response.status == 200:
                    json_data = await response.json()
                    testers = int(json_data.get("betaTesters"))
                    return testers, json_data
                else:
                    print(f"Failed to fetch data: {response.status}")
                    return None
    except Exception as e:
        print(f"Failed to fetch data: {e}")
        return None

async def send_error_message(guild_id, channel_id, error_message):
    guild = bot.get_guild(guild_id)
    if guild:
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(f"Error in `fetch_arc_beta`: {error_message}")


def save_to_config(key, value):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    config[key] = value

    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def load_from_config(key):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get(key)
    return None

arc_beta_msg_id = None

@tasks.loop(seconds=60)
async def check_arc_beta():
    global arc_beta_msg_id
    old_beta = load_from_config(ARC_BETA_KEY)
    new_beta_result = await fetch_arc_beta()
    if new_beta_result is not None:
        new_beta = new_beta_result[0]
        raw = new_beta_result[1]
    else:
        new_beta = None
        raw = None

    guild = bot.get_guild(1131126447340261398)
    channel = guild.get_channel(1195470811226722465)

    timestamp = datetime.datetime.now(pytz.timezone('America/New_York')).strftime("%Y-%m-%d %H:%M:%S")
    
    if new_beta is not None and old_beta is not None:
        diff = new_beta - old_beta
        diff_sign = "+" if diff >= 0 else ""
    else:
        diff = None
        diff_sign = ""

    embed = discord.Embed(title="Arc Windows Beta", color=0x3139fb)
    embed.set_thumbnail(url="https://framerusercontent.com/images/Fcy9YNKBYDx1Vj7UYJygYk6PCo.png?scale-down-to=512")
    embed.set_footer(text=f"Last updated: {timestamp}")
    if raw is not None:
        embed.add_field(name="Raw", value=f"```json\n{raw}\n```", inline=False)
    if diff is not None:
        embed.add_field(name="Diff", value=f"```diff\n{diff_sign}{diff}\n```", inline=True)
    if new_beta is not None:
        embed.add_field(name="Overall", value=f"```{str(new_beta)}```", inline=True)

    if diff is not None and diff > 1:
        await channel.send(f"<@454920881177624576> | `{timestamp}` | `{diff_sign}{diff}` new beta testers has been added.")
    elif arc_beta_msg_id:
        try:
            message = await channel.fetch_message(arc_beta_msg_id)
            await message.edit(embed=embed)
        except discord.NotFound:
            message = await channel.send(embed=embed)
            arc_beta_msg_id = message.id
    else:
        message = await channel.send(embed=embed)
        arc_beta_msg_id = message.id

    if new_beta is not None:
        save_to_config(ARC_BETA_KEY, new_beta)

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
    app.run(port=1337, use_reloader=False, host="0.0.0.0")

if __name__ == "__main__":
    p1 = Process(target=run_bot)
    p2 = Process(target=run_flask)

    p1.start()
    p2.start()

    p1.join()
    p2.join()
