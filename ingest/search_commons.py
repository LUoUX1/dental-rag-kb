"""搜索 Wikimedia Commons 上的智齿相关权威图片
四类: P0 神经管位置 / P1 阻生分类 / P2 切口设计 / P3 手术照片
"""
import json
import urllib.request
import urllib.parse

API = "https://commons.wikimedia.org/w/api.php"

def search_commons(query, limit=8):
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",  # File namespace
        "srlimit": str(limit),
        "format": "json",
        "utf8": 1,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "DentalKB/1.0 (educational use)"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
        return [(r["title"], r.get("snippet", "")[:120]) for r in resp.get("query", {}).get("search", [])]
    except Exception as e:
        return [("ERROR", str(e))]

queries = {
    "P0_神经管与智齿根尖": "mandibular canal impacted wisdom tooth",
    "P1_阻生智齿分类": "impacted wisdom tooth classification",
    "P1b_阻生智齿解剖": "impacted third molar",
    "P2_下颌切口": "mandibular third molar surgery incision",
}

for label, q in queries.items():
    print(f"\n=== {label}: {q} ===")
    for title, snippet in search_commons(q):
        print(f"  📄 {title}")
        print(f"     {snippet}")
