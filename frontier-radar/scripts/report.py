#!/usr/bin/env python3
"""前沿雷达网页生成器：把「速览 + 深读」渲染成 HTML，写进 ~/video-notes/radar/。

复用 watch-video 的 web 服务器（同一个 8000 端口、同一个根目录），因此无需改服务。

输入：
  <DIGEST>/<date>-shortlist.json   由 filter.py 产出（速览 & 深读候选）
  <DIGEST>/<date>-notes.json       可选：{arxiv_id: "一句话中文点评"}
  <DIGEST>/<date>-deep.md          可选：Agent 撰写的深度解读（## 标题 分节）
产出：
  <NOTES>/<date>/index.html        当日速览+深读
  <NOTES>/index.html               雷达主页（按日期列表）
"""
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import NOTES, DIGEST, PAPERS, WORKDIR  # noqa: E402

IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t: str) -> str:
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def first_sentence(text: str, limit=160) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    s = parts[0]
    if len(s) < 30 and len(parts) > 1:
        s = parts[0] + " " + parts[1]
    return s[:limit] + ("…" if len(s) > limit else "")


def md_to_html(md: str) -> str:
    """轻量 Markdown -> HTML（标题/段落/图/列表/引用/代码）。"""
    out, para, in_code, code = [], [], False, []
    for raw in md.splitlines():
        line = raw.rstrip()
        if in_code:
            if line.strip().startswith("```"):
                out.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
                code, in_code = [], False
            else:
                code.append(raw)
            continue
        if line.strip().startswith("```"):
            if para:
                out.append("<p>" + "".join(para) + "</p>"); para = []
            in_code = True; continue
        if not line.strip():
            if para:
                out.append("<p>" + "".join(para) + "</p>"); para = []
            continue
        m = IMG_RE.search(line)
        if m and line.strip().startswith("!["):
            if para:
                out.append("<p>" + "".join(para) + "</p>"); para = []
            cap, img = m.groups()
            fname = img.split("/")[-1]
            out.append(f'<figure><img src="images/{fname}" loading="lazy" '
                       f'onclick="lightbox(this)"><figcaption>{esc(cap)}</figcaption></figure>')
            continue
        if line.startswith("### "):
            para and out.append("<p>" + "".join(para) + "</p>"); para = []
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            para and out.append("<p>" + "".join(para) + "</p>"); para = []
            out.append(f'<h2 class="paper">{inline(line[3:])}</h2>')
        elif line.startswith("# "):
            para and out.append("<p>" + "".join(para) + "</p>"); para = []
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("> "):
            para and out.append("<p>" + "".join(para) + "</p>"); para = []
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
        elif line.startswith(("- ", "* ")):
            para and out.append("<p>" + "".join(para) + "</p>"); para = []
            out.append(f"<li>{inline(line[2:])}</li>")
        else:
            para.append(inline(line))
    if para:
        out.append("<p>" + "".join(para) + "</p>")
    return "\n".join(out)


CSS = """
:root{--bg:#0f1420;--card:#171d2c;--card2:#1c2436;--ink:#e9edf5;--muted:#8b95a8;
--accent:#4f9dff;--accent2:#38d39f;--line:#252d40;--warn:#ffb454;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC",
"Microsoft YaHei",sans-serif;line-height:1.8}
.wrap{max-width:820px;margin:0 auto;padding:26px 18px 90px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header{background:linear-gradient(135deg,#16223a,#22314f);border:1px solid var(--line);
border-radius:14px;padding:26px 24px;margin-bottom:22px}
header h1{font-size:1.5rem;margin-bottom:8px}
header .sub{color:#a9b6cc;font-size:.92rem}
header .meta{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;font-size:.82rem;color:#8291aa}
.nav{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.nav a{background:var(--card);border:1px solid var(--line);border-radius:20px;
padding:6px 14px;font-size:.85rem}
h2.sec{font-size:1.15rem;margin:30px 0 14px;padding-left:12px;border-left:4px solid var(--accent)}
.paper-list{display:flex;flex-direction:column;gap:10px}
.paper-item{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:14px 16px}
.paper-item:hover{border-color:#3a4a6b}
.pi-title{font-size:1rem;font-weight:600;color:#fff;line-height:1.5}
.pi-title a{color:#fff}
.pi-desc{color:#a9b6cc;font-size:.88rem;margin-top:6px}
.pi-tags{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap}
.tag{font-size:.72rem;padding:2px 9px;border-radius:20px;background:#22304a;color:#9dc0ff}
.tag.org{background:#1e3a2f;color:#6ee7b7}
.tag.score{background:#3a2a1a;color:var(--warn)}
.tag.link{background:#20242f;color:#8b95a8}
article h2.paper{font-size:1.18rem;margin:34px 0 12px;padding:10px 14px;background:var(--card2);
border-left:4px solid var(--accent2);border-radius:0 8px 8px 0}
article h3{font-size:1.02rem;margin:18px 0 8px;color:#7dd3fc}
article p{margin:10px 0;color:#cbd5e6;text-align:justify}
article b{color:#fff}
article code{background:#22304a;padding:1px 5px;border-radius:4px;font-size:.85rem}
blockquote{margin:14px 0;padding:12px 16px;background:#16233b;border-left:4px solid var(--accent);
border-radius:6px;color:#bcd2f2;font-size:.94rem}
figure{margin:20px 0}
figure img{width:100%;border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,.35);cursor:zoom-in}
figcaption{margin-top:8px;font-size:.82rem;color:var(--muted);text-align:center}
li{margin:4px 0 4px 1.4em}
pre{background:#0b1020;border:1px solid var(--line);border-radius:8px;padding:14px 16px;
margin:14px 0;overflow-x:auto}
pre code{background:none;color:#d7e2f7;font-size:.8rem}
.lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.94);z-index:99;
align-items:center;justify-content:center}
.lightbox img{max-width:94vw;max-height:92vh;border-radius:8px}
.toTop{position:fixed;right:18px;bottom:18px;background:var(--card);border:1px solid var(--line);
color:var(--ink);border-radius:50%;width:42px;height:42px;font-size:1.1rem;cursor:pointer}
"""

JS = """
function lightbox(img){var lb=document.getElementById('lb');
document.getElementById('lbimg').src=img.src;lb.style.display='flex';}
"""


def collect_images(date: str, md: str, note_dir: Path):
    """把深读文章引用的图片从 WORKDIR/papers/images 复制到笔记目录。"""
    needed = {m.group(2).split("/")[-1] for m in IMG_RE.finditer(md)}
    if not needed:
        return
    img_dir = note_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    for src_root in (PAPERS / "images", WORKDIR / "figures", WORKDIR / "images"):
        if not src_root.exists():
            continue
        for f in src_root.rglob("*"):
            if f.is_file() and f.name in needed:
                shutil.copy(f, img_dir / f.name)
                needed.discard(f.name)
        if not needed:
            break


def build_daily(date: str):
    sl_path = DIGEST / f"{date}-shortlist.json"
    if not sl_path.exists():
        print(f"[report] 缺 {sl_path}", file=sys.stderr)
        return None
    d = json.loads(sl_path.read_text())
    notes = {}
    npath = DIGEST / f"{date}-notes.json"
    if npath.exists():
        notes = json.loads(npath.read_text())
    deep_md = ""
    dpath = DIGEST / f"{date}-deep.md"
    if dpath.exists():
        deep_md = dpath.read_text(encoding="utf-8")

    note_dir = NOTES / date
    note_dir.mkdir(parents=True, exist_ok=True)
    collect_images(date, deep_md, note_dir)

    # 速览
    items = []
    for i, p in enumerate(d["shortlist"], 1):
        tags = "".join(f'<span class="tag org">{esc(o)}</span>' for o in p.get("org_hits", [])[:3])
        for g in list(p.get("topic_hits", {}).keys()):
            tags += f'<span class="tag">{esc(g)}</span>'
        tags += f'<span class="tag score">{p.get("score", 0)}</span>'
        desc = notes.get(p["id"]) or first_sentence(p.get("abstract", ""))
        items.append(f"""<div class="paper-item">
  <div class="pi-title"><a href="{p['url']}" target="_blank">{i}. {esc(p['title'])}</a></div>
  {('<div class="pi-desc">'+inline(desc)+'</div>') if desc else ''}
  <div class="pi-tags">{tags}
    <a class="tag link" href="{p['url']}" target="_blank">abs</a>
    <a class="tag link" href="{p['pdf']}" target="_blank">pdf</a></div>
</div>""")

    deep_html = ""
    if deep_md.strip():
        deep_html = f'<h2 class="sec">🔬 深度解读</h2><article>{md_to_html(deep_md)}</article>'

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>前沿雷达 · {date}</title><style>{CSS}</style></head><body>
<div class="wrap">
<div class="nav"><a href="../">🔭 雷达主页</a><a href="/">📚 笔记总站</a></div>
<header>
  <h1>🔭 前沿雷达 · {date}</h1>
  <div class="sub">当日 arxiv 更新 {d.get('total', 0)} 篇，精选 {len(d['shortlist'])} 条速览 + {len(d.get('deep_candidates', []))} 篇候选深读</div>
  <div class="meta"><span>📅 {date}</span><span>⚙️ frontier-radar</span></div>
</header>
<h2 class="sec">⚡ 速览</h2>
<div class="paper-list">{''.join(items)}</div>
{deep_html}
</div>
<div class="lightbox" id="lb" onclick="this.style.display='none'"><img id="lbimg"></div>
<button class="toTop" onclick="scrollTo({{top:0,behavior:'smooth'}})">↑</button>
<script>{JS}</script></body></html>"""
    (note_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"[report] ✓ {note_dir / 'index.html'}")
    return note_dir


def build_index():
    NOTES.mkdir(parents=True, exist_ok=True)
    days = sorted([d.name for d in NOTES.glob("*") if (d / "index.html").exists()
                   and re.match(r"\d{4}-\d{2}-\d{2}", d.name)], reverse=True)
    cards = ""
    for day in days:
        cnt = ""
        sl = DIGEST / f"{day}-shortlist.json"
        if sl.exists():
            dd = json.loads(sl.read_text())
            cnt = f"速览 {len(dd['shortlist'])} · 深读候选 {len(dd.get('deep_candidates', []))}"
        cards += (f'<a class="card" href="{day}/"><div class="card-title">🔭 {day}</div>'
                  f'<div class="card-meta">{cnt}</div></a>')
    if not cards:
        cards = '<div class="empty">暂无雷达日报，运行 frontier-radar 技能生成。</div>'
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🔭 前沿雷达</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1420;color:#eaeaf1;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7}}
.wrap{{max-width:760px;margin:0 auto;padding:30px 18px 80px}}
h1{{font-size:1.5rem;margin-bottom:6px}} .sub{{color:#8b95a8;font-size:.92rem;margin-bottom:22px}}
.nav{{margin-bottom:20px}} .nav a{{color:#4f9dff;text-decoration:none;font-size:.9rem}}
.card{{display:block;background:#171d2c;border:1px solid #252d40;color:#eaeaf1;text-decoration:none;
border-radius:12px;padding:18px 20px;margin:12px 0;transition:.15s}}
.card:hover{{background:#1d2437;border-color:#3a4a6b;transform:translateY(-1px)}}
.card-title{{font-size:1.08rem;font-weight:600;color:#fff;margin-bottom:4px}}
.card-meta{{color:#6f7a8f;font-size:.8rem}}
.empty{{color:#8b95a8;text-align:center;padding:60px 0}}
</style></head><body><div class="wrap">
<div class="nav"><a href="/">← 笔记总站</a></div>
<h1>🔭 前沿雷达</h1>
<div class="sub">由 frontier-radar 技能生成的每日 AI 前沿速览与深度解读</div>
{cards}
</div></body></html>"""
    (NOTES / "index.html").write_text(html, encoding="utf-8")
    print(f"[report] ✓ {NOTES / 'index.html'} ({len(days)} 天)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        build_daily(sys.argv[1])
    else:
        build_daily(datetime.now().strftime("%Y-%m-%d"))
    build_index()
