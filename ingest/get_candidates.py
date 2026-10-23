"""获取候选图片的详细信息(URL/许可证) + 更精确搜索 P0/P2"""
import json
import urllib.request
import urllib.parse

API = "https://commons.wikimedia.org/w/api.php"

def get_image_info(titles):
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "format": "json",
        "utf8": 1,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "DentalKB/1.0 (educational use)"})
    resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
    pages = resp.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        title = page.get("title", "?")
        ii = page.get("imageinfo", [{}])[0]
        url = ii.get("url", "")
        w, h = ii.get("width", 0), ii.get("height", 0)
        license = ""
        ext = ii.get("extmetadata", {})
        lic = ext.get("LicenseShortName", {}).get("value", "")
        artist = ext.get("Artist", {}).get("value", "")[:60]
        print(f"📄 {title}")
        print(f"   尺寸: {w}x{h} | 许可证: {lic}")
        print(f"   URL: {url}")
        if artist:
            print(f"   作者: {artist}")

def search_commons(query, limit=8):
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

print("=" * 70)
print("P1 候选图详细信息")
print("=" * 70)
get_image_info([
    "File:Third molar impacted mesioangular.jpg",
    "File:Lower mandibular third molar impaction pericoronitis diagram.jpg",
    "File:Impacted Wisdom Tooth aka Lower Left Third Molar 38 RVG IOPA Xray.jpg",
])

print("\n" + "=" * 70)
print("P0 搜索: mandibular nerve canal third molar anatomy")
print("=" * 70)
for t, s in search_commons("mandibular canal third molar anatomy"):
    print(f"  {t} | {s}")

print("\n" + "=" * 70)
print("P2 搜索: wisdom tooth surgery flap incision diagram")
print("=" * 70)
for t, s in search_commons("wisdom tooth flap incision diagram"):
    print(f"  {t} | {s}")

print("\n" + "=" * 70)
print("P0 搜索2: inferior alveolar nerve diagram")
print("=" * 70)
for t, s in search_commons("inferior alveolar nerve mandible diagram"):
    print(f"  {t} | {s}")
