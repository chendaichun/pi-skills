#!/usr/bin/env python3
"""对当日抓取的论文打分排序，产出「速览」清单和「深读候选」。

用法:
  python3 filter.py                 # 处理当天
  python3 filter.py 2026-09-11
  python3 filter.py --top 50 --deep 10
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA, TOPICS, ORGS, HEADLINE_HINTS, WORKDIR, DIGEST  # noqa: E402

TOPIC_WEIGHT = {"模型/训练": 1.0, "Infra/推理部署": 1.25, "评测/安全": 0.5}


def _hits(text: str, kws):
    """词边界匹配，避免 Yi 命中 yields、FAIR 命中 fairness 之类的误报。"""
    hits = []
    for k in kws:
        pat = r"\b" + re.escape(k.lower()) + r"\b"
        if re.search(pat, text):
            hits.append(k)
    return hits


def score_paper(p):
    text = (p["title"] + " \n " + p.get("abstract", "")).lower()
    title = p["title"].lower()

    topic_hits = {}
    topic_score = 0.0
    for group, kws in TOPICS.items():
        hits = _hits(text, kws)
        if hits:
            topic_hits[group] = hits
            # 标题命中额外加权
            title_hits = [k for k in hits if k in title]
            topic_score += TOPIC_WEIGHT[group] * (len(hits) + 1.0 * len(title_hits))

    org_hits = _hits(text, ORGS)
    org_score = 3.0 * len(org_hits)

    headline = len(_hits(title, HEADLINE_HINTS))
    type_bonus = 1.0 if p.get("announce_type") == "new" else 0.0

    total = topic_score + org_score + headline + type_bonus
    p2 = dict(p)
    p2["score"] = round(total, 2)
    p2["topic_hits"] = topic_hits
    p2["org_hits"] = org_hits
    p2["why"] = ([f"机构:{','.join(org_hits)}"] if org_hits else []) + \
                [f"{g}:{','.join(h[:4])}" for g, h in topic_hits.items()][:2]
    return p2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--top", type=int, default=60, help="速览保留条数")
    ap.add_argument("--deep", type=int, default=10, help="深读候选条数")
    args = ap.parse_args()

    src = DATA / f"{args.date}.json"
    if not src.exists():
        print(f"[filter] 找不到 {src}，先运行 fetch.py", file=sys.stderr)
        sys.exit(1)
    data = json.loads(src.read_text())
    papers = [score_paper(p) for p in data["items"]]
    papers.sort(key=lambda p: p["score"], reverse=True)

    # 标题近似去重（保守：小写去标点后前 60 字符相同视为重复）
    def key(p):
        return re.sub(r"[^a-z0-9]", "", p["title"].lower())[:60]
    uniq, seen = [], set()
    for p in papers:
        k = key(p)
        if k and k in seen:
            continue
        seen.add(k)
        uniq.append(p)

    shortlist = uniq[:args.top]
    deep = uniq[:args.deep]

    DIGEST.mkdir(parents=True, exist_ok=True)
    out = DIGEST / f"{args.date}-shortlist.json"
    out.write_text(json.dumps({
        "date": args.date,
        "total": len(data["items"]),
        "shortlist": shortlist,
        "deep_candidates": deep,
    }, ensure_ascii=False, indent=1))

    print(f"[filter] {args.date}: 共 {len(data['items'])} 条 → 速览 {len(shortlist)} / 深读候选 {len(deep)}")
    print(f"[filter] ✓ {out}\n")
    print("== 深读候选 ==")
    for p in deep:
        org = ("｜" + ",".join(p["org_hits"][:2])) if p["org_hits"] else ""
        print(f"  [{p['score']:5.1f}] {p['title'][:72]}{org}")
    print("\n== 速览前 15 ==")
    for p in shortlist[:15]:
        print(f"  [{p['score']:5.1f}] {p['title'][:70]}")


if __name__ == "__main__":
    main()
