import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import asyncio

TOKEN = os.environ.get("DISCORD_TOKEN")
POLL_CHANNEL_ID = 1479982795651551447
EVENT_ROLE_NAME = "Guild Wars"
POLL_DAY = 0
POLL_HOUR = 12
POLL_DURATION_DAYS = 4
EVENT_QUESTION = "Guild War - Are you IN or OUT this week?"
ANNOUNCEMENT_DELETE_AFTER = 300

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_poll = {
    "message_id": None,
    "message_obj": None,
    "end_time": None,
    "voters_in": set()
}

IN_EMOJI = "\u2705"
OUT_EMOJI = "\u274c"


@bot.event
async def on_ready():
    print("Bot is online as " + str(bot.user))
    weekly_poll.start()
    check_poll_ended.start()


@tasks.loop(hours=1)
async def weekly_poll():
    now = datetime.utcnow()
    if now.weekday() == POLL_DAY and now.hour == POLL_HOUR:
        await post_poll()


@tasks.loop(minutes=10)
async def check_poll_ended():
    if not active_poll["message_id"] or not active_poll["end_time"]:
        return
    if datetime.utcnow() >= active_poll["end_time"]:
        await end_poll()


async def post_poll():
    channel = bot.get_channel(POLL_CHANNEL_ID)
    if not channel:
        print("Channel not found!")
        return

    guild = channel.guild
    role = discord.utils.get(guild.roles, name=EVENT_ROLE_NAME)

    # Reset all roles when new poll starts
    if role:
        removed = 0
        for member in guild.members:
            if role in member.roles:
                await member.remove_roles(role)
                removed += 1
        print("Reset roles from " + str(removed) + " members")

    end_time = datetime.utcnow() + timedelta(days=POLL_DURATION_DAYS)
    end_str = end_time.strftime("%A, %B %d at %I:%M %p UTC")

    desc = (
        "\u2705 **IN** - Vote IN to join the Guild War!\n"
        "\u274c **OUT** - Sit this one out\n\n"
        "Roles will be assigned on **Friday** when poll closes!\n"
        "Poll closes: **" + end_str + "**"
    )

    embed = discord.Embed(
        title=EVENT_QUESTION,
        description=desc,
        color=0x7289DA
    )
    embed.set_footer(text="Roles assigned Friday. Resets every Monday.")

    # Send @everyone then the embed
    await channel.send("@everyone \u2694\ufe0f **Guild War poll is now open!** Vote below!")
    msg = await channel.send(embed=embed)
    await msg.add_reaction(IN_EMOJI)
    await msg.add_reaction(OUT_EMOJI)

    active_poll["message_id"] = msg.id
    active_poll["message_obj"] = msg
    active_poll["end_time"] = end_time
    active_poll["voters_in"] = set()
    print("Poll posted! Closes: " + end_str)


async def end_poll():
    channel = bot.get_channel(POLL_CHANNEL_ID)
    if not channel:
        return

    guild = channel.guild
    role = discord.utils.get(guild.roles, name=EVENT_ROLE_NAME)

    if not role:
        print("Role not found: " + EVENT_ROLE_NAME)
        return

    # Assign roles to everyone who voted IN
    assigned = 0
    for user_id in active_poll["voters_in"]:
        member = guild.get_member(user_id)
        if member and role not in member.roles:
            await member.add_roles(role)
            assigned += 1
            print("Gave role to " + member.name)

    # Delete the original poll message
    try:
        if active_poll["message_obj"]:
            await active_poll["message_obj"].delete()
            print("Poll message deleted")
    except Exception as e:
        print("Could not delete poll message: " + str(e))

    active_poll["message_id"] = None
    active_poll["message_obj"] = None
    active_poll["end_time"] = None
    active_poll["voters_in"] = set()

    # Send @everyone closing announcement
    embed = discord.Embed(
        title="\u2694\ufe0f Guild War Starting!",
        description=(
            "Poll is closed! **" + str(assigned) + " members** have been given the Guild Wars role!\n\n"
            "Roles will reset next Monday when the new poll opens. Good luck! \U0001f3c6\n\n"
            "_This message will disappear in 5 minutes_"
        ),
        color=0xFFD700
    )
    await channel.send("@everyone \u2694\ufe0f **Guild War is starting!** Roles have been assigned!")
    announcement = await channel.send(embed=embed)
    print("Poll ended. Assigned role to " + str(assigned) + " members.")

    # Delete announcement after 5 minutes
    await asyncio.sleep(ANNOUNCEMENT_DELETE_AFTER)
    try:
        await announcement.delete()
        print("Announcement deleted")
    except Exception as e:
        print("Could not delete announcement: " + str(e))


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.id != active_poll["message_id"]:
        return

    if str(reaction.emoji) == IN_EMOJI:
        active_poll["voters_in"].add(user.id)
        print(user.name + " voted IN")

    elif str(reaction.emoji) == OUT_EMOJI:
        active_poll["voters_in"].discard(user.id)
        print(user.name + " voted OUT")


@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    if reaction.message.id != active_poll["message_id"]:
        return

    if str(reaction.emoji) == IN_EMOJI:
        active_poll["voters_in"].discard(user.id)
        print(user.name + " removed IN vote")


@bot.command()
@commands.has_permissions(administrator=True)
async def startpoll(ctx):
    await post_poll()
    await ctx.message.delete()


@bot.command()
@commands.has_permissions(administrator=True)
async def endpoll(ctx):
    await end_poll()
    await ctx.message.delete()


@bot.command()
@commands.has_permissions(administrator=True)
async def pollstatus(ctx):
    if not active_poll["message_id"]:
        await ctx.send("No active poll right now.", delete_after=10)
        return
    count = len(active_poll["voters_in"])
    time_left = active_poll["end_time"] - datetime.utcnow()
    hours_left = int(time_left.total_seconds() // 3600)
    await ctx.send(
        "Poll Status - Voted IN: " + str(count) + " - Time left: " + str(hours_left) + " hours",
        delete_after=15
    )
    await ctx.message.delete()


bot.run(TOKEN)
