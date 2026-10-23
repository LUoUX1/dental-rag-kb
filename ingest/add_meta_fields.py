"""批量给 Obsidian 笔记 frontmatter 添加 updated + status 字段"""
import os
import re
from datetime import datetime

KB = r"D:\Documents\Obsidian Vault\口腔医学知识库"
TODAY = datetime.now().strftime("%Y-%m-%d")

count = 0
for root, dirs, files in os.walk(KB):
    dirs[:] = [d for d in dirs if d != ".obsidian" and d != "模板" and not d.startswith(".")]
    for f in files:
        if not f.endswith(".md"):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding="utf-8").read()

        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)

        # 添加 status（若没有）
        if "status:" not in fm:
            fm += "\nstatus: 稳定"
        # 添加 updated（若没有）
        if "updated:" not in fm:
            fm += f"\nupdated: {TODAY}"

        new_content = f"---\n{fm}\n---\n" + content[m.end():]
        if new_content != content:
            open(path, "w", encoding="utf-8").write(new_content)
            count += 1
            print(f"✅ {os.path.relpath(path, KB)}")

print(f"\n共更新 {count} 篇笔记，更新时间基准: {TODAY}")
