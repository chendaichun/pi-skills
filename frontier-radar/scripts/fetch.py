#!/usr/bin/env python3
"""抓取 arxiv 最新论文（官方 RSS）→ 本地 JSON。

用法:
  python3 fetch.py                 # 抓全部关注分类
  python3 fetch.py --cats cs.DC    # 只抓指定分类
  python3 fetch.py --list          # 列出当前已抓到的当日条目数
"""
import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ARXIV_CATS, DATA, WORKDIR  # noqa: E402
import proxy  # noqa: E402

NS = {"arxiv": "http://arxiv.org/schemas/atom",
      "dc": "http://purl.org/dc/elements/1.1/"}


def _abstract(desc: str) -> str:
    # RSS description 形如 "arXiv:2609.09160v1 Announce Type: new \nAbstract: ..."
    return re.sub(r"^.*?Abstract:\s*", "", desc or "", flags=re.S).strip()


def parse_rss(raw: bytes, cat: str):
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        link = it.findtext("link", "") or ""
        m = re.search(r"abs/([0-9]+\.[0-9]+)", link)
        aid = m.group(1) if m else link.strip()
        out.append({
            "id": aid,
            "title": (it.findtext("title", "") or "").strip(),
            "abstract": _abstract(it.findtext("description", "")),
            "authors": it.findtext("dc:creator", "", NS) or "",
            "categories": [c.text for c in it.findall("category") if c.text],
            "announce_type": it.findtext("arxiv:announce_type", "", NS) or "new",
            "source_cat": cat,
            "url": f"https://arxiv.org/abs/{aid}",
            "pdf": f"https://arxiv.org/pdf/{aid}",
        })
    return out


def fetch_arxiv(cats):
    items = {}
    for cat in cats:
        try:
            raw = proxy.http_get(f"https://rss.arxiv.org/rss/{cat}", timeout=45)
            got = parse_rss(raw, cat)
            print(f"[fetch] {cat:6} {len(got):4} 条")
            for x in got:
                # 同一篇可能出现在多个分类，合并分类
                if x["id"] in items:
                    items[x["id"]]["categories"] = sorted(
                        set(items[x["id"]]["categories"]) | set(x["categories"]))
                else:
                    items[x["id"]] = x
        except Exception as e:
            print(f"[fetch] {cat} 失败: {type(e).__name__}: {e}", file=sys.stderr)
        time.sleep(1.2)
    return list(items.values())


def seen_path():
    return WORKDIR / "seen.json"


def load_seen():
    p = seen_path()
    return set(json.loads(p.read_text())) if p.exists() else set()


def save_seen(ids):
    WORKDIR.mkdir(parents=True, exist_ok=True)
    seen_path().write_text(json.dumps(sorted(ids)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", nargs="*", default=ARXIV_CATS)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = DATA / f"{today}.json"

    if args.list:
        if out_path.exists():
            d = json.loads(out_path.read_text())
            print(f"{today}: {len(d['items'])} 条")
        return

    if not proxy.ensure():
        print("[fetch] 代理不可用", file=sys.stderr)
        sys.exit(1)

    print(f"[fetch] arxiv RSS × {len(args.cats)} 分类 ...")
    items = fetch_arxiv(args.cats)
    seen = load_seen()
    fresh = [x for x in items if x["id"] not in seen]
    print(f"[fetch] 去重后共 {len(items)} 条，其中新论文 {len(fresh)} 条")

    # 合并进当日文件（同一天多次运行会累积）
    existing = json.loads(out_path.read_text()) if out_path.exists() else {"date": today, "items": []}
    by_id = {x["id"]: x for x in existing["items"]}
    for x in items:
        by_id[x["id"]] = x
    existing["items"] = list(by_id.values())
    existing["updated_at"] = datetime.now().isoformat(timespec="seconds")
    out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=1))

    save_seen(seen | {x["id"] for x in items})
    print(f"[fetch] ✓ 写入 {out_path}（累计 {len(existing['items'])} 条）")


if __name__ == "__main__":
    main()
