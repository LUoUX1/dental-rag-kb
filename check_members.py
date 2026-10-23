"""列出 Discord 服务器中所有机器人成员（识别"比价bot"）"""
import os
import json
from pathlib import Path

# 加载 .env
env = {}
env_path = Path(os.path.expanduser("~/Desktop/dental-kb/.env"))
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

TOKEN = env.get("DENTAL_BOT_TOKEN", "")
GUILD_ID = 1529311379339870228  # wwwhoney的服务器

import discord

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"登录成功: {client.user} (ID {client.user.id})")
    guild = client.get_guild(GUILD_ID)
    if not guild:
        print(f"找不到服务器 {GUILD_ID}")
        await client.close()
        return
    print(f"服务器: {guild.name} (成员 {guild.member_count})")
    print("\n=== 所有成员（标记 bot）===")
    for member in guild.members:
        bot_mark = "🤖 BOT" if member.bot else "👤 用户"
        print(f"  {bot_mark} | {member.name}#{member.discriminator if member.discriminator != '0' else ''} | ID {member.id}")
    print("\n=== 所有角色 ===")
    for role in guild.roles:
        print(f"  {role.name} (ID {role.id}) managed={role.managed}")
    await client.close()

client.run(TOKEN)
