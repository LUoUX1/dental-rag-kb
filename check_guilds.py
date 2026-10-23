"""快速检查机器人已加入的服务器"""
import os
import sys
from pathlib import Path

# 加载 .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

TOKEN = os.environ.get("DENTAL_BOT_TOKEN", "")

import asyncio
import discord

# 代理注入
PROXY = os.environ.get("HTTP_PROXY") or "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
import aiohttp
_orig = aiohttp.ClientSession.__init__
def _patched(self, *args, **kwargs):
    kwargs.setdefault("proxy", PROXY)
    _orig(self, *args, **kwargs)
aiohttp.ClientSession.__init__ = _patched

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ 机器人: {client.user} (ID: {client.user.id})")
    print(f"   已加入 {len(client.guilds)} 个服务器:")
    for g in client.guilds:
        print(f"   - {g.name} (ID: {g.id}, 成员: {g.member_count})")
    await client.close()

asyncio.run(client.start(TOKEN))
