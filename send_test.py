"""让机器人主动往服务器发测试消息，验证双向连接"""
import os
import asyncio
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

import discord
import aiohttp

# 代理注入
PROXY = os.environ.get("HTTP_PROXY") or "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
_orig = aiohttp.ClientSession.__init__
def _patched(self, *args, **kwargs):
    kwargs.setdefault("proxy", PROXY)
    _orig(self, *args, **kwargs)
aiohttp.ClientSession.__init__ = _patched

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ 已连接: {client.user}")
    for g in client.guilds:
        print(f"📡 服务器: {g.name}")
        # 找第一个可发消息的文字频道
        for ch in g.text_channels:
            try:
                await ch.send("🤖 **口腔医学知识库机器人连接测试成功！**\n\n在频道里 @我 提问即可，例如：\n`@口腔医学知识库 牙周炎怎么分期？`\n\n（如果你看到这条消息，说明双向连接正常 ✅）")
                print(f"   ✅ 已发送测试消息到 #{ch.name} (ID: {ch.id})")
                break
            except Exception as e:
                print(f"   ⚠️ 无法发送到 #{ch.name}: {e}")
                continue
    await client.close()

asyncio.run(client.start(TOKEN))
