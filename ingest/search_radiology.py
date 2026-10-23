"""搜索 Wikimedia Commons 根尖片/影像判读对比图"""
import json
import urllib.request
import urllib.parse
import time

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "DentalKB-Research/1.0 (educational)"}

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
    req = urllib.request.Request(url, headers=UA)
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
        return [(r["title"], r.get("snippet", "")[:100]) for r in resp.get("query", {}).get("search", [])]
    except Exception as e:
        return [("ERROR", str(e))]

queries = [
    ("正常根尖片", "periapical radiograph normal"),
    ("根尖囊肿X线", "periapical cyst radiograph"),
    ("根尖肉芽肿", "periapical granuloma radiograph"),
    ("根尖脓肿", "periapical abscess radiograph"),
    ("根管治疗X线", "root canal treatment radiograph"),
    ("牙周病X线", "periodontal disease radiograph bone loss"),
]

for label, q in queries:
    print(f"\n=== {label}: {q} ===")
    results = search_commons(q)
    for t, s in results:
        if any(ext in t.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".tif", ".svg"]):
            print(f"  🖼 {t}")
            print(f"     {s}")
    time.sleep(2)
