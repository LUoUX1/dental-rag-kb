"""
Obsidian → 向量库 同步脚本
扫描 Obsidian Vault 中的口腔医学笔记，解析并索引到知识库后端

功能：
1. 解析 frontmatter（title/category/tags/aliases/source）
2. 提取 Markdown 表格 → 单独索引（table 集合）
3. 提取图片引用 ![[xxx.png]] → 复制到 server/data/images → 索引（image 集合）
4. 正文分块 → 索引（text 集合，附带元数据）

用法:
    python vault_sync.py              # 全量同步
    python vault_sync.py --reindex    # 清空向量库后全量重建
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request

try:
    import yaml
except ImportError:
    print("缺少 pyyaml，请安装: uv pip install pyyaml")
    sys.exit(1)

# ─── 配置 ───
VAULT_ROOT = r"D:\Documents\Obsidian Vault"
KB_DIR_NAME = "口腔医学知识库"
ATTACH_DIR = "附件"
TEMPLATE_DIR = "模板"
API_BASE = os.environ.get("KB_API_BASE", "http://localhost:3002/api/kb")
SERVER_IMAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "server", "data", "images")

# 忽略的文件（目录名或文件名精确匹配）
IGNORE = {"模板", "Templates", ".obsidian", ".trash", "欢迎.md"}


def api_post(path, payload, timeout=300):
    """调用后端 API"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {body}")


def parse_frontmatter(content: str):
    """解析 YAML frontmatter，返回 (meta, body)。date 类型统一转 str（json 序列化用）"""
    meta = {}
    body = content
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
            if not isinstance(meta, dict):
                meta = {}
            # YAML 会把 2026-08-12 解析为 date，转成字符串
            import datetime
            for k, v in list(meta.items()):
                if isinstance(v, (datetime.date, datetime.datetime)):
                    meta[k] = v.isoformat()
                elif isinstance(v, list):
                    meta[k] = [x.isoformat() if isinstance(x, (datetime.date, datetime.datetime)) else x for x in v]
        except Exception as e:
            print(f"  ⚠️ frontmatter 解析失败: {e}")
        body = content[m.end():]
    return meta, body


def extract_tables(body: str):
    """
    提取 Markdown 表格用于 table 集合索引，但正文中原样保留表格（不替换占位符）
    —— 这样 text 块保留完整表格数据，DeepSeek 能看到内容
    返回 (tables, body)
    """
    tables = []
    lines = body.split("\n")
    i = 0
    table_idx = 0

    while i < len(lines):
        line = lines[i]
        # 表格以 | 开头
        if line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            # 解析表格
            rows = []
            for tl in table_lines:
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows.append(cells)
            if len(rows) >= 2:
                sep_re = re.compile(r"^[\s:\-|]+$")
                if len(rows) > 1 and all(sep_re.match(c) for c in rows[1]):
                    header = rows[0]
                    data_rows = rows[2:]
                else:
                    header = rows[0]
                    data_rows = rows[1:]
                data = [header] + data_rows
                if data_rows:
                    table_idx += 1
                    tid = hashlib.md5(json.dumps(data, ensure_ascii=False).encode()).hexdigest()[:10]
                    lines_txt = [f"列名: {', '.join(header)}"]
                    for r_i, r in enumerate(data_rows[:8], 1):
                        lines_txt.append(f"第{r_i}行: " + " | ".join(f"{h}: {v}" for h, v in zip(header, r) if h and v))
                    tables.append({
                        "id": tid,
                        "data": data,
                        "text_repr": f"口腔医学表格（{len(data_rows)}行数据）:\n" + "\n".join(lines_txt),
                    })
            # 表格行原样保留在正文（不替换占位符）
        else:
            i += 1

    return tables, body


def extract_images(body: str, note_path: str, note_title: str):
    """
    提取 Obsidian 图片引用 ![[xxx.png]] 或 ![](xxx)
    返回 (images, body_without_images)
    """
    images = []
    attach_dir = os.path.join(VAULT_ROOT, KB_DIR_NAME, ATTACH_DIR)

    def repl(m):
        img_name = m.group(1).strip()
        # 去掉尺寸后缀 ![[xxx.png|300]]
        img_name = re.sub(r"\|.*$", "", img_name).strip()
        if not img_name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return m.group(0)

        # 在附件目录查找
        src = os.path.join(attach_dir, img_name)
        if not os.path.exists(src):
            # 在笔记同目录找
            src = os.path.join(os.path.dirname(note_path), img_name)
        if not os.path.exists(src):
            print(f"  ⚠️ 图片未找到: {img_name}")
            return f"[图片: {img_name}(缺失)]"

        # 复制到 server/images，带前缀避免重名
        img_id = hashlib.md5(img_name.encode()).hexdigest()[:10]
        ext = os.path.splitext(img_name)[1].lower()
        dest_name = f"obs_{img_id}{ext}"
        dest_path = os.path.join(SERVER_IMAGE_DIR, dest_name)
        os.makedirs(SERVER_IMAGE_DIR, exist_ok=True)
        if not os.path.exists(dest_path):
            shutil.copy2(src, dest_path)

        images.append({
            "id": img_id,
            "filename": dest_name,
            "path": str(dest_path).replace("\\", "/"),
            "note": note_title,
            "page": None,
            "size": os.path.getsize(src),
        })
        return f"[图片: {img_name}]"

    # 匹配 ![[xxx]] 和 ![](xxx)
    pattern = r"!\[\[([^\]]+)\]\]|!\[[^\]]*\]\(([^)]+)\)"
    new_body = re.sub(pattern, lambda m: repl(m) if m.group(1) else repl(m), body)
    return images, new_body


def sync_note(md_path: str, reindex_all: bool):
    """同步单篇 Obsidian 笔记"""
    rel = os.path.relpath(md_path, os.path.join(VAULT_ROOT, KB_DIR_NAME))
    note_title = os.path.splitext(os.path.basename(md_path))[0]

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. frontmatter
    meta, body = parse_frontmatter(content)
    title = meta.get("title") or note_title
    category = meta.get("category") or os.path.dirname(rel).replace("\\", "/")
    tags = meta.get("tags") or []
    aliases = meta.get("aliases") or []
    source = meta.get("source") or ""
    # Q9/Q12: 维护治理字段
    updated = meta.get("updated") or meta.get("last_updated") or ""
    status = meta.get("status") or "稳定"  # 稳定/待更新/待审核/草稿
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # 保留一级标题（作为检索上下文；title 与文件名一致时无重复问题）
    # 仅当标题行与文件名完全相同才保留——不删除，确保块内有关键词上下文
    body = body.lstrip("\n")

    doc_id = hashlib.md5((KB_DIR_NAME + "/" + rel).encode()).hexdigest()[:12]

    print(f"\n📝 {note_title}")
    print(f"   分类: {category} | 标签: {tags} | 来源: {source or '无'}")
    if updated or status != "稳定":
        print(f"   维护: 更新时间={updated or '未标注'} | 状态={status}")

    # 2. 提取表格
    tables, body = extract_tables(body)
    print(f"   表格: {len(tables)} 个")

    # 3. 提取图片
    images, body = extract_images(body, md_path, note_title)
    print(f"   图片: {len(images)} 张")

    # 4. 正文（去表格/图片引用后）分块索引
    text = body.strip()
    if text:
        text_payload = {
            "text": text[:50000],
            "fileName": f"{title}（Obsidian）",
            "docId": doc_id,
            "type": "text",
            "category": category,
            "tags": tags,
            "source": source,
            "updated": updated,
            "status": status,
            "mdSource": True,  # 按 Markdown 标题分块
        }
        resp = api_post("/index", text_payload)
        print(f"   文本: {resp.get('chunkCount', 0)} 片段")

    # 5. 表格索引（带笔记标题上下文）
    for t in tables:
        table_text = f"[Obsidian笔记:{title}] {t['text_repr']}"
        resp = api_post("/index", {
            "text": table_text,
            "fileName": f"{title} - 表格",
            "docId": doc_id,
            "type": "table",
            "tableId": t["id"],
            "tableData": t["data"],
            "category": category,
            "source": source,
            "updated": updated,
            "status": status,
        })
        print(f"   表格索引: {t['id']} → {resp.get('chunkCount', 0)} 片段")

    # 6. 图片索引（描述 = 笔记标题 + 文件名）
    for img in images:
        desc = f"[Obsidian图片] 来自笔记《{title}》(分类:{category})。图片文件: {img['filename']}"
        resp = api_post("/index", {
            "text": desc,
            "fileName": f"{title} - 图片",
            "docId": doc_id,
            "type": "image",
            "imageId": img["id"],
            "imagePath": img["path"],
            "category": category,
            "source": source,
            "updated": updated,
            "status": status,
        })
        print(f"   图片索引: {img['id']} → {resp.get('chunkCount', 0)} 片段")


def main():
    parser = argparse.ArgumentParser(description="Obsidian → 向量库同步")
    parser.add_argument("--reindex", action="store_true", help="清空向量库后全量重建")
    args = parser.parse_args()

    kb_dir = os.path.join(VAULT_ROOT, KB_DIR_NAME)
    if not os.path.exists(kb_dir):
        print(f"❌ 知识库目录不存在: {kb_dir}")
        sys.exit(1)

    # 健康检查
    try:
        req = urllib.request.Request(f"{API_BASE}/health")
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
        print(f"🦷 服务器: {resp.get('status')}, 模型: {resp.get('model')}")
    except Exception as e:
        print(f"❌ 无法连接服务器: {e}\n请先启动: cd server && node server.js")
        sys.exit(1)

    # --reindex: 清空向量库与图片目录
    if args.reindex:
        vectors_dir = os.path.join(os.path.dirname(__file__), "..", "server", "data", "vectors")
        if os.path.exists(vectors_dir):
            shutil.rmtree(vectors_dir)
            print("🧹 已清空向量库")
        if os.path.exists(SERVER_IMAGE_DIR):
            shutil.rmtree(SERVER_IMAGE_DIR)
            print("🧹 已清空图片目录")
        os.makedirs(vectors_dir, exist_ok=True)
        os.makedirs(SERVER_IMAGE_DIR, exist_ok=True)

    # 收集所有 .md 笔记（排除模板和忽略目录）
    notes = []
    for root, dirs, files in os.walk(kb_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE and not d.startswith(".")]
        for f in files:
            if f.endswith(".md") and f not in IGNORE:
                notes.append(os.path.join(root, f))
    notes.sort()

    if not notes:
        print("❌ 未找到任何笔记")
        sys.exit(1)

    print(f"📚 找到 {len(notes)} 篇笔记\n{'='*50}")
    for note in notes:
        try:
            sync_note(note, args.reindex)
        except Exception as e:
            print(f"  ❌ 同步失败: {e}")

    print(f"\n{'='*50}\n🎉 同步完成!")


if __name__ == "__main__":
    main()
