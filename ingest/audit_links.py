"""全库双链审计：检查每个 [[链接]] 是否有对应笔记文件"""
import os
import re

KB = r"D:\Documents\Obsidian Vault\口腔医学知识库"

# 收集所有笔记文件名（不含 .md）
notes = set()
for root, dirs, files in os.walk(KB):
    dirs[:] = [d for d in dirs if d != ".obsidian" and d != "模板" and not d.startswith(".")]
    for f in files:
        if f.endswith(".md"):
            notes.add(os.path.splitext(f)[0])

# 扫描所有链接
broken = []
links_found = 0
for root, dirs, files in os.walk(KB):
    dirs[:] = [d for d in dirs if d != ".obsidian" and d != "模板" and not d.startswith(".")]
    for f in files:
        if not f.endswith(".md"):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding="utf-8").read()
        for m in re.finditer(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]", content):
            target = m.group(1).strip()
            links_found += 1
            if target not in notes:
                broken.append((os.path.relpath(path, KB), target))

print(f"全库笔记: {len(notes)} 篇")
print(f"链接总数: {links_found}")
if broken:
    print(f"\n❌ 断链 {len(broken)} 处:")
    for src, tgt in broken:
        print(f"  {src} → [[{tgt}]]")
else:
    print("✅ 无断链")
