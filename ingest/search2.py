"""第二轮搜索: P0 神经管关系图 / P2 切口示意图"""
import json
import urllib.request
import urllib.parse

API = "https://commons.wikimedia.org/w/api.php"

def search_commons(query, limit=10):
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",
        "srlimit": str(limit),
        "format": "json",
        "utf8": 1,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "DentalKB/1.0 (educational use)"})
    resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
    return [(r["title"], r.get("snippet", "")[:100]) for r in resp.get("query", {}).get("search", [])]

queries = [
    ("P0a 智齿神经管", "third molar inferior alveolar nerve"),
    ("P0b 智齿神经", "wisdom tooth nerve canal"),
    ("P0c 智齿X光神经", "impacted molar inferior alveolar nerve radiograph"),
    ("P2a 智齿拔除术", "third molar extraction surgery"),
    ("P2b 牙科翻瓣", "dental flap surgery diagram"),
    ("P2c 下颌阻生拔除", "mandibular third molar coronectomy"),
    ("P1c 阻生智齿分型", "wisdom tooth positions mesioangular distoangular vertical horizontal"),
]

for label, q in queries:
    print(f"\n=== {label}: {q} ===")
    results = search_commons(q)
    for t, s in results:
        # 只显示 jpg/png/svg 图片（排除 pdf/djvu）
        if any(ext in t.lower() for ext in [".jpg", ".jpeg", ".png", ".svg", ".gif", ".tif"]):
            print(f"  🖼 {t}")
            print(f"     {s}")
