"""下载 P0/P2 配图候选到 Obsidian 附件目录"""
import json
import urllib.request
import urllib.parse
import os
import time

API = "https://commons.wikimedia.org/w/api.php"
ATTACH_DIR = r"D:\Documents\Obsidian Vault\口腔医学知识库\附件"
UA = {"User-Agent": "DentalKB-Research/1.0 (educational)"}

IMAGES = [
    ("File:Coronectomy wisdom tooth.png", "智齿_冠切术_神经管关系示意图.png", "CC BY-SA 3.0"),
    ("File:PELL Y GREGORY.png", "智齿_PellGregory分类图.png", "CC BY-SA 4.0"),
    ("File:Severely impacted wisdom tooth CT scan - upper right.jpg", "智齿_重度阻生CT_右上.jpg", "CC BY-SA 3.0"),
    ("File:Missing roots after removal of severely impacted wisdom tooth CT scan - upper left.jpg", "智齿_重度阻生CT_左上.jpg", "CC BY-SA 3.0"),
    ("File:Lower wisdom tooth.png", "智齿_下颌位置示意图.png", "CC BY-SA 3.0"),
]

def get_url(title):
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
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
                return ii.get("url", "").split("?")[0]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"   ⏳ 限流，等待 {20*(attempt+1)}s...")
                time.sleep(20 * (attempt + 1))
            else:
                print(f"   ❌ HTTP {e.code}")
                return None
        except Exception as e:
            print(f"   ❌ {e}")
            return None
    return None

for title, fname, lic in IMAGES:
    try:
        print(f"📥 {title}")
        url = get_url(title)
        if not url:
            print("   ❌ 无法获取 URL")
            continue
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers=UA)
                data = urllib.request.urlopen(req, timeout=60).read()
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    print(f"   ⏳ 下载限流，等待 {20*(attempt+1)}s...")
                    time.sleep(20 * (attempt + 1))
                else:
                    raise
        dest = os.path.join(ATTACH_DIR, fname)
        with open(dest, "wb") as f:
            f.write(data)
        print(f"   ✅ 已保存: {fname} ({len(data)//1024}KB) | {lic}")
        print(f"   来源: {url}")
        time.sleep(4)
    except Exception as e:
        print(f"   ❌ 失败: {e}")
