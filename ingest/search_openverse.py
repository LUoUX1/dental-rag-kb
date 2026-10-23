"""搜索 Openverse + Wikimedia 找 P0(神经管关系) 和 P2(切口设计) 配图"""
import json
import urllib.request
import urllib.parse
import time

UA = {"User-Agent": "DentalKB-Research/1.0 (educational)"}

def openverse_search(query, limit=10):
    """Openverse API: 聚合 CC 授权图片"""
    params = {
        "q": query,
        "license_type": "commercial,modification",  # CC 可商用可修改
        "page_size": str(limit),
    }
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers=UA)
        resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
        results = resp.get("results", [])
        out = []
        for r in results:
            out.append({
                "title": r.get("title", "?"),
                "url": r.get("url", ""),
                "license": r.get("license", ""),
                "license_version": r.get("license_version", ""),
                "source": r.get("source", ""),
                "width": r.get("width", 0),
                "height": r.get("height", 0),
            })
        return out
    except Exception as e:
        return [{"error": str(e)}]

def wikimedia_category(category, limit=30):
    """浏览 Wikimedia 分类下的图片"""
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": str(limit),
        "format": "json",
        "utf8": 1,
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers=UA)
        resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
        return [m["title"] for m in resp.get("query", {}).get("categorymembers", [])]
    except Exception as e:
        return [f"ERROR: {e}"]

print("=" * 70)
print("P0 搜索: Openverse - inferior alveolar nerve")
print("=" * 70)
for item in openverse_search("inferior alveolar nerve mandible diagram"):
    if "error" in item:
        print(f"  ❌ {item['error']}")
    else:
        print(f"  🖼 {item['title'][:60]} | {item['source']} | {item['license']} {item['license_version']} | {item['width']}x{item['height']}")
        print(f"     {item['url']}")
    time.sleep(1)

print("\n" + "=" * 70)
print("P0 搜索: Openverse - mandibular canal")
print("=" * 70)
for item in openverse_search("mandibular canal nerve"):
    if "error" in item:
        print(f"  ❌ {item['error']}")
    else:
        print(f"  🖼 {item['title'][:60]} | {item['source']} | {item['license']} {item['license_version']} | {item['width']}x{item['height']}")
        print(f"     {item['url']}")
    time.sleep(1)

print("\n" + "=" * 70)
print("P2 搜索: Openverse - wisdom tooth surgery")
print("=" * 70)
for item in openverse_search("wisdom tooth extraction surgery"):
    if "error" in item:
        print(f"  ❌ {item['error']}")
    else:
        print(f"  🖼 {item['title'][:60]} | {item['source']} | {item['license']} {item['license_version']} | {item['width']}x{item['height']}")
        print(f"     {item['url']}")
    time.sleep(1)

print("\n" + "=" * 70)
print("Wikimedia 分类浏览: Wisdom teeth")
print("=" * 70)
for t in wikimedia_category("Wisdom teeth"):
    print(f"  {t}")
    time.sleep(0.5)
