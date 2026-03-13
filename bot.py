import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================

# CONFIGURATION - Edit these values!

# ============================================================

TOKEN = “MTQ4MTkwNzc1NzAzNTU1NjkwNg.G-0NMk.CymmoM46XNYNDiCZ1sISzWUmpllJALejA6M048”
POLL_CHANNEL_ID = 1479982795651551447        # Right click channel → Copy ID
EVENT_ROLE_NAME = “Guild Wars”   # Must match role name in your server exactly
POLL_DAY = 0       # 0=Monday 1=Tuesday 2=Wednesday 3=Thursday 4=Friday 5=Saturday 6=Sunday
POLL_HOUR = 12     # 24hr UTC time (12 = noon UTC)
POLL_DURATION_DAYS = 7
EVENT_QUESTION = “🎉 Weekly Event — Are you IN or OUT this week?”

# ============================================================

# — Keep-alive web server for Render —

class Handler(BaseHTTPRequestHandler):
def do_GET(self):
self.send_response(200)
self.end_headers()
self.wfile.write(b”Bot is running!”)
def log_message(self, format, *args):
pass

def run_server():
server = HTTPServer((“0.0.0.0”, 8080), Handler)
server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# ––––––––––––––––––––

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix=”!”, intents=intents)

active_poll = {
“message_id”: None,
“end_time”: None,
“voters_in”: set()
}

IN_EMOJI = “✅”
OUT_EMOJI = “❌”

@bot.event
async def on_ready():
print(f”✅ Bot is online as {bot.user}”)
weekly_poll.start()
check_poll_ended.start()

@tasks.loop(hours=1)
async def weekly_poll():
now = datetime.utcnow()
if now.weekday() == POLL_DAY and now.hour == POLL_HOUR:
await post_poll()

@tasks.loop(minutes=30)
async def check_poll_ended():
if not active_poll[“message_id”] or not active_poll[“end_time”]:
return
if datetime.utcnow() >= active_poll[“end_time”]:
await end_poll()

async def post_poll():
channel = bot.get_channel(POLL_CHANNEL_ID)
if not channel:
print(“❌ Channel not found! Check POLL_CHANNEL_ID”)
return

```
end_time = datetime.utcnow() + timedelta(days=POLL_DURATION_DAYS)
end_str = end_time.strftime("%A, %B %d at %I:%M %p UTC")

embed = discord.Embed(
    title=EVENT_QUESTION,
    description=(
        f"{IN_EMOJI} **IN** — You'll get access to the event channel!\n"
        f"{OUT_EMOJI} **OUT** — No worries, see you next time!\n\n"
        f"⏰ Poll closes: **{end_str}**"
    ),
    color=0x7289DA
)
embed.set_footer(text="Roles reset automatically when event ends.")

msg = await channel.send(embed=embed)
await msg.add_reaction(IN_EMOJI)
await msg.add_reaction(OUT_EMOJI)

active_poll["message_id"] = msg.id
active_poll["end_time"] = end_time
active_poll["voters_in"] = set()
print(f"✅ Poll posted! Ends: {end_str}")
```

async def end_poll():
channel = bot.get_channel(POLL_CHANNEL_ID)
if not channel:
return

```
guild = channel.guild
role = discord.utils.get(guild.roles, name=EVENT_ROLE_NAME)

if not role:
    print(f"❌ Role '{EVENT_ROLE_NAME}' not found!")
    return

removed = 0
for member in guild.members:
    if role in member.roles:
        await member.remove_roles(role)
        removed += 1

active_poll["message_id"] = None
active_poll["end_time"] = None
active_poll["voters_in"] = set()

embed = discord.Embed(
    title="🏁 Event Poll Closed!",
    description="All event roles have been reset. See you next week! 🎉",
    color=0xFF6B6B
)
await channel.send(embed=embed)
print(f"✅ Poll ended. Removed role from {removed} members.")
```

@bot.event
async def on_reaction_add(reaction, user):
if user.bot:
return
if reaction.message.id != active_poll[“message_id”]:
return

```
guild = reaction.message.guild
role = discord.utils.get(guild.roles, name=EVENT_ROLE_NAME)
member = guild.get_member(user.id)

if not role or not member:
    return

if str(reaction.emoji) == IN_EMOJI:
    await member.add_roles(role)
    active_poll["voters_in"].add(user.id)
    print(f"✅ Gave role to {user.name}")

elif str(reaction.emoji) == OUT_EMOJI:
    if role in member.roles:
        await member.remove_roles(role)
    active_poll["voters_in"].discard(user.id)
    print(f"❌ Removed role from {user.name}")
```

@bot.event
async def on_reaction_remove(reaction, user):
if user.bot:
return
if reaction.message.id != active_poll[“message_id”]:
return

```
guild = reaction.message.guild
role = discord.utils.get(guild.roles, name=EVENT_ROLE_NAME)
member = guild.get_member(user.id)

if not role or not member:
    return

if str(reaction.emoji) == IN_EMOJI:
    if role in member.roles:
        await member.remove_roles(role)
    active_poll["voters_in"].discard(user.id)
```

# ============================================================

# ADMIN COMMANDS

# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def startpoll(ctx):
“”“Manually start a poll right now for testing”””
await post_poll()
await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def endpoll(ctx):
“”“Manually end poll and reset all roles”””
await end_poll()
await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def pollstatus(ctx):
“”“Check current poll status”””
if not active_poll[“message_id”]:
await ctx.send(“❌ No active poll right now.”, delete_after=10)
return
count = len(active_poll[“voters_in”])
time_left = active_poll[“end_time”] - datetime.utcnow()
hours_left = int(time_left.total_seconds() // 3600)
await ctx.send(
f”📊 **Poll Status**\n✅ Voted IN: **{count}**\n⏰ Time left: **{hours_left} hours**”,
delete_after=15
)
await ctx.message.delete()

bot.run(TOKEN)
