"""
口腔医学知识库 Discord 机器人
监听服务器消息 → 调用本地知识库 API → 返回基于知识库的回答（含表格/图片）

启动: python dental_bot.py
依赖: discord.py (已安装 2.7.1)
"""
import os
import json
import re
import urllib.request
import asyncio
import sys
from pathlib import Path

import discord
from discord.ext import commands
import aiohttp

# ─── 配置（从 .env 加载） ───
def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

load_env()

# 代理（中国大陆访问 Discord 必需；aiohttp 3.14 移除了 ProxyConnector，
# 代理改为 ClientSession(proxy=...) 参数，这里 monkey-patch 注入）
PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY

_original_client_session_init = aiohttp.ClientSession.__init__
def _patched_client_session_init(self, *args, **kwargs):
    # discord.py 创建 session 时未传 proxy，这里补上
    kwargs.setdefault("proxy", PROXY)
    _original_client_session_init(self, *args, **kwargs)
aiohttp.ClientSession.__init__ = _patched_client_session_init

KB_API = os.environ.get("KB_API", "http://localhost:3002/api/kb/ask")
TOKEN = os.environ.get("DENTAL_BOT_TOKEN", "")

# 机器人只在指定频道响应（留空=所有频道）
ALLOWED_CHANNELS = [c.strip() for c in os.environ.get("DENTAL_BOT_CHANNELS", "").split(",") if c.strip()]

intents = discord.Intents.default()
intents.message_content = True  # 必须：读取消息内容

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def ask_kb(question: str) -> dict:
    """调用知识库 RAG API"""
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        KB_API,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


def format_answer(result: dict, mention: str) -> str:
    """格式化回答：文字 + 表格 + 图片说明"""
    answer = result.get("answer", "")
    images = result.get("images", [])
    sources = result.get("sources", [])

    # 截断过长回答（Discord 单条消息上限 2000 字符）
    if len(answer) > 1800:
        answer = answer[:1800] + "\n\n…（回答过长已截断）"

    msg = f"{mention}\n{answer}"

    # 图片：Discord 直接渲染 URL（需 Embed Links 权限）
    # 后端已做相关性过滤（score≥0.65 且 ≥文本最高分70%），这里再兜底一道
    relevant_images = [img for img in images if img.get("score", 0) >= 0.65]
    if relevant_images:
        msg += "\n\n**📎 相关配图：**"
        for img in relevant_images[:3]:
            url = img.get("url")
            if url:
                msg += f"\nhttp://localhost:3002{url}"

    return msg


@bot.event
async def on_ready():
    print(f"✅ 口腔医学知识库机器人已上线: {bot.user}")
    print(f"   代理: {PROXY}")
    print(f"   知识库API: {KB_API}")
    if ALLOWED_CHANNELS:
        print(f"   限定频道: {ALLOWED_CHANNELS}")


@bot.event
async def on_message(message: discord.Message):
    # 日志：记录所有收到的消息（排查用）
    try:
        print(f"[MSG] #{message.channel.name} | {message.author} | content='{message.content[:80]}' | mentions={[m.id for m in message.mentions]} | raw_mentions={message.raw_mentions}")
    except Exception as e:
        print(f"[MSG-LOG-ERR] {e}")

    # 忽略机器人自己的消息
    if message.author.bot:
        return

    # 频道白名单
    if ALLOWED_CHANNELS and str(message.channel.id) not in ALLOWED_CHANNELS:
        return

    content = message.content.strip()

    # 触发方式：@机器人 或 频道内直接提问
    is_mention = bot.user in message.mentions
    # 兼容：raw_mentions 也能识别（intent 未开时 mentions 可能为空，但 raw_mentions 有值）
    if not is_mention and bot.user.id in message.raw_mentions:
        is_mention = True

    # 兼容：@角色（role mention）也响应——用户给机器人分配了角色并@角色
    if not is_mention and message.role_mentions and message.guild:
        try:
            bot_member = message.guild.get_member(bot.user.id)
            bot_role_ids = {r.id for r in bot_member.roles} if bot_member else set()
            mentioned_role_ids = {r.id for r in message.role_mentions}
            if bot_role_ids & mentioned_role_ids:
                is_mention = True
                print(f"[DECIDE] 角色提及命中机器人所在角色")
        except Exception as e:
            print(f"[ROLE-CHECK-ERR] {e}")

    print(f"[DECIDE] is_mention={is_mention} | content='{content[:50]}'")

    if not is_mention:
        # 非 @ 时不响应（避免误触发）
        return

    # 去掉 @提及 部分
    question = re.sub(r"<@!?\d+>", "", content).strip()
    if not question:
        await message.channel.send(f"{message.author.mention} 请把口腔医学问题发给我，例如：\n@口腔医学知识库 牙周炎怎么治疗？")
        return

    # 打字指示
    async with message.channel.typing():
        try:
            result = await asyncio.to_thread(ask_kb, question)
            reply = format_answer(result, message.author.mention)
            # 分片发送（超 2000 字符时）
            for i in range(0, len(reply), 1900):
                await message.channel.send(reply[i:i + 1900])
        except Exception as e:
            await message.channel.send(f"{message.author.mention} ⚠️ 知识库查询失败：{str(e)[:200]}")


if __name__ == "__main__":
    if not TOKEN:
        print("❌ 未设置 DENTAL_BOT_TOKEN 环境变量")
        print("   请在 dental-kb/.env 中配置，或 export DENTAL_BOT_TOKEN=xxx")
        raise SystemExit(1)
    bot.run(TOKEN)
