"""获取新候选图的详细信息 + 许可证"""
import json
import urllib.request
import urllib.parse
import time

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "DentalKB-Research/1.0 (educational)"}

TITLES = [
    "File:Coronectomy wisdom tooth.png",
    "File:PELL Y GREGORY.png",
    "File:Gebit verstandskiezen.PNG",
    "File:Missing roots after removal of severely impacted wisdom tooth CT scan - upper left.jpg",
    "File:Severely impacted wisdom tooth CT scan - upper right.jpg",
    "File:Wisdom Tooth (PSF).png",
    "File:MuelaJuicio.jpg",
    "File:Lower wisdom tooth.png",
]

params = {
    "action": "query",
    "titles": "|".join(TITLES),
    "prop": "imageinfo",
    "iiprop": "url|size|extmetadata",
    "format": "json",
    "utf8": 1,
}
url = API + "?" + urllib.parse.urlencode(params)
req = urllib.request.Request(url, headers=UA)
resp = json.loads(urllib.request.urlopen(req, timeout=30).read())

for pid, page in resp.get("query", {}).get("pages", {}).items():
    title = page.get("title", "?")
    ii = page.get("imageinfo", [{}])[0]
    ext = ii.get("extmetadata", {})
    lic = ext.get("LicenseShortName", {}).get("value", "?")
    artist = ext.get("Artist", {}).get("value", "")
    # 去 HTML 标签
    import re
    artist_clean = re.sub(r"<[^>]+>", "", artist)[:60]
    print(f"📄 {title}")
    print(f"   尺寸: {ii.get('width',0)}x{ii.get('height',0)} | 许可证: {lic} | 作者: {artist_clean}")
    print(f"   URL: {ii.get('url','').split('?')[0]}")
    print()
    time.sleep(1)
