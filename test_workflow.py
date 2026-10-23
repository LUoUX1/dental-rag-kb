"""验证工作流结构下的问答效果"""
import urllib.request, json

API = "http://localhost:3002/api/kb/ask"

def ask(q):
    payload = json.dumps({"question": q}).encode("utf-8")
    req = urllib.request.Request(API, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=180).read())

# 按临床工作流各环节提问
questions = [
    ("接诊", "患者主诉牙龈出血，可能是什么问题？该怎么问诊？"),
    ("检查", "怎么判断牙齿是牙髓炎还是根尖周炎？检查要点是什么？"),
    ("诊断", "牙痛的鉴别诊断有哪些？怎么区分？"),
    ("治疗", "深龋接近牙髓应该怎么治疗？有哪些方案？"),
    ("操作", "根管治疗的步骤是什么？"),
    ("并发症", "拔牙后出血不止怎么办？"),
    ("急救", "患者打麻药后晕厥了怎么处理？"),
    ("材料", "后牙大面积缺损用什么材料修复好？"),
]

for stage, q in questions:
    print(f"\n{'='*60}\n[{stage}] {q}\n{'='*60}")
    try:
        r = ask(q)
        ans = r.get("answer", "")
        tables = r.get("tables", [])
        cats = set()
        for s in r.get("sources", []):
            if s.get("category"):
                cats.add(s["category"])
        print(ans[:700])
        if len(ans) > 700:
            print(f"... (共{len(ans)}字符)")
        print(f"\n📊 来源:{len(r.get('sources',[]))} 表格:{len(tables)} 命中分类:{sorted(cats)}")
        if tables:
            print(f"   表格示例: {tables[0]['markdown'][:150].replace(chr(10),' | ')}")
    except Exception as e:
        print(f"❌ {e}")
