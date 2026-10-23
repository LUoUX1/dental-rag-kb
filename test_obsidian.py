"""Obsidian版知识库端到端测试"""
import urllib.request, json, sys

API = "http://localhost:3002/api/kb/ask"

def ask(question):
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(API, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=180).read())

tests = [
    ("龋病按深度分哪几类？各自的治疗方式？", True),
    ("FDI牙齿编号怎么标记？列出象限含义", True),
    ("牙体解剖有哪些结构？", False),
]

all_ok = True
for q, expect_table in tests:
    print(f"\n{'='*60}\n❓ {q}\n{'='*60}")
    try:
        r = ask(q)
        answer = r.get("answer", "")
        tables = r.get("tables", [])
        images = r.get("images", [])

        print(answer[:1200])
        print(f"\n📊 来源: {len(r.get('sources',[]))} | 表格: {len(tables)} | 图片: {len(images)}")

        # 验证表格
        if expect_table and not tables:
            print("  ⚠️ 期望有表格但没有检索到!")
            all_ok = False
        if tables:
            print("\n📋 检索到的表格 (Markdown):")
            for t in tables[:2]:
                print(t.get("markdown", ""))
        if images:
            print(f"\n🖼 检索到的图片: {[i.get('url') for i in images]}")

        # 检查回答是否有表格标记
        if "|---" in answer or "| ---" in answer:
            print("\n✅ 回答中包含 Markdown 表格")
        if not answer or answer.startswith("⚠️"):
            all_ok = False
            print("  ❌ 回答异常")
    except Exception as e:
        print(f"❌ 错误: {e}")
        all_ok = False

print(f"\n{'='*60}")
print("✅ 全部通过!" if all_ok else "⚠️ 有测试未通过")
print(f"{'='*60}")
