"""下载已确认的智齿图片到 Obsidian 附件目录"""
import json
import urllib.request
import urllib.parse
import os
import re
import time

API = "https://commons.wikimedia.org/w/api.php"
ATTACH_DIR = r"D:\Documents\Obsidian Vault\口腔医学知识库\附件"
os.makedirs(ATTACH_DIR, exist_ok=True)

# 已确认的图片: (标题, 文件名, 许可证)
IMAGES = [
    ("File:Third molar impacted mesioangular.jpg", "智齿_近中阻生_X线.jpg", "CC BY-SA 4.0"),
    ("File:Impacted Wisdom Tooth aka Lower Left Third Molar 38 RVG IOPA Xray.jpg", "智齿_左下38近中阻生_X线.jpg", "CC BY-SA 4.0"),
    ("File:Lower mandibular third molar impaction pericoronitis diagram.jpg", "智齿_冠周炎示意图.jpg", "CC0"),
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
            req = urllib.request.Request(url, headers={"User-Agent": "DentalKB-Research/1.0 (educational; contact: local)"})
            resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
            pages = resp.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                ii = page.get("imageinfo", [{}])[0]
                return ii.get("url", "")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"   ⏳ 429限流，等待 {20*(attempt+1)}s...")
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
        # 去掉 URL 中的查询参数（utm_source 等）
        clean_url = url.split("?")[0]
        for attempt in range(4):
            try:
                req = urllib.request.Request(clean_url, headers={"User-Agent": "DentalKB-Research/1.0 (educational; contact: local)"})
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
        print(f"   ✅ 已保存: {fname} ({len(data)//1024}KB) | 许可证: {lic}")
        print(f"   来源: {clean_url}")
        time.sleep(5)  # 每次下载间隔
    except Exception as e:
        print(f"   ❌ 失败: {e}")
