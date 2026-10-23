"""下载根尖片对比图候选"""
import json
import urllib.request
import urllib.parse
import os
import time

API = "https://commons.wikimedia.org/w/api.php"
ATTACH_DIR = r"D:\Documents\Obsidian Vault\口腔医学知识库\附件"
UA = {"User-Agent": "DentalKB-Research/1.0 (educational)"}

IMAGES = [
    ("File:Abscessed tooth periapical radiograph.jpg", "影像_根尖脓肿X线.jpg"),
    ("File:Gingival cyst of adult radiograph.jpg", "影像_成人龈囊肿X线.jpg"),
]

def get_info(title):
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "format": "json",
        "utf8": 1,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
            for pid, page in resp.get("query", {}).get("pages", {}).items():
                ii = page.get("imageinfo", [{}])[0]
                ext = ii.get("extmetadata", {})
                lic = ext.get("LicenseShortName", {}).get("value", "?")
                return ii.get("url", "").split("?")[0], ii.get("width", 0), ii.get("height", 0), lic
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20 * (attempt + 1))
            else:
                return None, 0, 0, str(e.code)
        except Exception as e:
            return None, 0, 0, str(e)
    return None, 0, 0, "?"

for title, fname in IMAGES:
    url, w, h, lic = get_info(title)
    if not url:
        print(f"❌ {title}: 无法获取 ({lic})")
        continue
    print(f"📥 {title} | {w}x{h} | {lic}")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=60).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"   ⏳ 限流等待 {20*(attempt+1)}s")
                time.sleep(20 * (attempt + 1))
            else:
                raise
    dest = os.path.join(ATTACH_DIR, fname)
    with open(dest, "wb") as f:
        f.write(data)
    print(f"   ✅ 已保存 {fname} ({len(data)//1024}KB) | 许可证: {lic}")
    time.sleep(4)
