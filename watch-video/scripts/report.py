#!/usr/bin/env python3
"""笔记库网页生成器。

核心思路：Agent(大脑) 撰写一篇微信推文风格的 Markdown 文章（导读+小节+配图指令），
本脚本读取文章 + 图库，渲染成漂亮 HTML，写入 report/<note-id>/。
主页 report/index.html 列出所有笔记供选择。

文章语法约定（Agent 撰写时遵循）：
  # 标题
  ## 每节标题
  ![caption](images/xxx.png@12s)   # 图片：caption 对图注, @NNs 映射到对应时间帧
  普通段落
"""
import json
import re
import shutil
from pathlib import Path
from datetime import datetime

from config import GROUPS, RESULTS, OUT, REPORT, WORKDIR

IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    """转义 HTML 并处理行内粗体（段落/列表/引题/标题通用）。"""
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    return out


def get_frames():
    """frames 图片与其时间戳映射: {文件名: 时间秒}"""
    manifest_path = GROUPS / "manifest.json"
    if not manifest_path.exists():
        return {}
    m = json.loads(manifest_path.read_text())
    out = {}
    for item in m:
        f = Path(item["file"])
        out[f.name] = item.get("time", 0)
    return out


def copy_frames(note_dir: Path, needed_names=None):
    """把 frames 图片复制进笔记目录。needed_names 为 None 时复制全部，
    否则只复制文章实际引用的图（避免笔记库冗余）。"""
    img_dir = note_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    # 清理旧图（重新生成时避免残留）
    for old in img_dir.glob("*"):
        old.unlink()
    frames_dir = GROUPS.parent / "frames"
    if needed_names is None:
        srcs = sorted(frames_dir.glob("*.png"))
    else:
        srcs = [frames_dir / n for n in sorted(needed_names)]
    for src in srcs:
        if src.exists():
            shutil.copy(src, img_dir / src.name)
    return img_dir


def md_to_html(md: str, frames_map: dict) -> str:
    """把 MD 转成 HTML（处理标题/段落/图片）。"""
    lines = md.splitlines()
    html_parts = []
    para = []
    in_code = False
    code_buf = []
    for raw in lines:
        line = raw.rstrip()
        if in_code:
            if line.strip().startswith("```"):
                html_parts.append("<pre><code>" + "\n".join(code_buf) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                code_buf.append(raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            continue
        if line.strip().startswith("```"):
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            in_code = True
            continue
        if not line.strip():
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            continue
        m = IMG_RE.search(line)
        if m:
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            cap, img = m.groups()
            img_path = img.lstrip("/").replace("\\", "/")
            fname = img_path.split("/")[-1]
            time_s = frames_map.get(fname, "")
            ts = ""
            if isinstance(time_s, int):
                mm, ss = divmod(time_s, 60)
                ts = f'<span class="ts">@{mm}:{ss:02d}</span>'
            html_parts.append(
                f'<figure><img src="images/{fname}" loading="lazy" onclick="lightbox(this)">'
                f'<figcaption>{cap} {ts}</figcaption></figure>')
            continue
        if line.startswith("### "):
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            html_parts.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            html_parts.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            html_parts.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("> "):
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            html_parts.append(f'<blockquote>{_inline(line[2:])}</blockquote>')
        elif line.startswith("- ") or line.startswith("* "):
            if para:
                html_parts.append("<p>" + "".join(para) + "</p>")
                para = []
            html_parts.append(f'<li>{_inline(line[2:])}</li>')
        else:
            para.append(_inline(line))
    if para:
        html_parts.append("<p>" + "".join(para) + "</p>")
    return "\n".join(html_parts)


EMAIL_CLS = "inherit"


def build_note(note_id: str, meta: dict, article_md_path: Path):
    """生成单篇笔记页面 + 更新主页。"""
    note_dir = REPORT / note_id
    note_dir.mkdir(parents=True, exist_ok=True)

    md = article_md_path.read_text(encoding="utf-8")
    # 只复制文章实际引用的图（防止笔记库冗余）
    needed = set()
    for m in IMG_RE.finditer(md):
        fname = m.group(2).lstrip("/").replace("\\", "/").split("/")[-1]
        needed.add(fname)
    copy_frames(note_dir, needed)

    frames_map = get_frames()
    body = md_to_html(md, frames_map)

    title = meta.get("title", f"笔记 {note_id}")
    subtitle = meta.get("subtitle", "")
    author = meta.get("author", "watch-video")
    date = meta.get("date", datetime.now().strftime("%Y-%m-%d"))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>
:root {{ --bg:#f7f8fa; --card:#fff; --ink:#333; --muted:#8892a0;
         --accent:#1a7ef2; --line:#e8eaee; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--ink); font-family:-apple-system,
       "PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
       line-height:1.9; }}
.wrap {{ max-width:680px; margin:0 auto; padding:24px 18px 80px; }}
header {{ background:linear-gradient(135deg,#1c2537,#2e4057); color:#fff;
         border-radius:14px; padding:30px 26px; margin-bottom:22px; }}
header h1 {{ font-size:1.45rem; line-height:1.5; margin-bottom:10px; }}
header .sub {{ color:#c2ccdc; font-size:.95rem; margin-bottom:14px; }}
header .meta {{ display:flex; gap:16px; flex-wrap:wrap; font-size:.8rem; color:#9aa8bd; }}
article h2 {{ font-size:1.2rem; margin:28px 0 12px; padding-left:12px;
             border-left:4px solid var(--accent); }}
article h3 {{ font-size:1.05rem; margin:20px 0 8px; color:#0f5fc4; }}
article p {{ margin:10px 0; color:#3d4450; text-align:justify; }}
article b {{ color:#111; }}
blockquote {{ margin:14px 0; padding:12px 16px; background:#eef4ff;
             border-left:4px solid var(--accent); color:#27486e;
             border-radius:6px; font-size:.95rem; }}
figure {{ margin:22px 0; }}
figure img {{ width:100%; border-radius:10px; display:block;
             box-shadow:0 4px 18px rgba(0,0,0,.12); cursor:zoom-in; }}
figcaption {{ margin-top:8px; font-size:.83rem; color:var(--muted);
             text-align:center; }}
.ts {{ display:inline-block; background:#e8eefb; color:#5a7fd0; border-radius:10px;
      padding:0 8px; font-size:.75rem; margin-left:6px; }}
li {{ margin:4px 0 4px 1.4em; }}
pre {{ background:#0f1626; color:#d7e2f7; border-radius:8px;
      padding:14px 16px; margin:16px 0; overflow-x:auto; }}
pre code {{ font-family:"SF Mono",Consolas,Menlo,monospace;
           font-size:.82rem; line-height:1.65; white-space:pre; }}
.back {{ position:fixed; top:16px; right:16px; background:var(--card);
        border:1px solid var(--line); color:var(--ink); border-radius:20px;
        padding:7px 14px; font-size:.85rem; text-decoration:none;
        box-shadow:0 2px 8px rgba(0,0,0,.08); }}
.lightbox {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.92);
            align-items:center; justify-content:center; z-index:99; }}
.lightbox img {{ max-width:92vw; max-height:92vh; border-radius:8px; }}
@media(max-width:480px){{ header{{padding:22px 18px}} header h1{{font-size:1.15rem}} }}
</style>
</head>
<body>
<a class="back" href="./">← 返回笔记列表</a>
<div class="wrap">
<header>
  <h1>{title}</h1>
  {('<div class="sub">' + subtitle + '</div>') if subtitle else ''}
  <div class="meta"><span>✍ {author}</span><span>📅 {date}</span></div>
</header>
<article>{body}</article>
</div>
<div class="lightbox" id="lb" onclick="this.style.display='none'">
  <img id="lbimg" src="">
</div>
<script>
function lightbox(img){{ document.getElementById('lbimg').src=img.src;
  document.getElementById('lb').style.display='flex'; }}
</script>
</body>
</html>"""
    (note_dir / "index.html").write_text(html, encoding="utf-8")
    # 保存元数据
    (note_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    print(f"[✓] 笔记: {note_dir / 'index.html'}")
    return note_dir


def build_index():
    """扫描 report/ 下所有笔记, 生成主页 index.html。"""
    REPORT.mkdir(parents=True, exist_ok=True)
    notes = []
    for d in sorted(REPORT.glob("*/")):
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        notes.append((d.name, meta))

    cards = ""
    if notes:
        for nid, meta in notes:
            cards += f"""
<a class="card" href="{nid}/">
  <div class="card-title">{meta.get('title','未命名')}</div>
  {('<div class="card-sub">'+meta.get('subtitle','')+'</div>') if meta.get('subtitle') else ''}
  <div class="card-meta">{meta.get('date','')} · {meta.get('source','')}</div>
</a>"""
    else:
        cards = '<div class="empty">暂无笔记。运行 watch-video 技能生成。</div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📚 视频笔记库</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:#0f1420; color:#eaeaf1; font-family:-apple-system,"PingFang SC",
       "Microsoft YaHei",sans-serif; line-height:1.7; }}
.wrap {{ max-width:760px; margin:0 auto; padding:30px 18px 80px; }}
h1 {{ font-size:1.5rem; margin-bottom:6px; }}
.sub {{ color:#8b95a8; font-size:.92rem; margin-bottom:26px; }}
.nav {{ margin-bottom:16px; }}
.nav a {{ display:inline-block; background:#171d2c; border:1px solid #2a3550; color:#7db2ff;
        text-decoration:none; border-radius:20px; padding:6px 14px; font-size:.85rem; }}
.nav a:hover {{ border-color:#3a4a6b; }}
.card {{ display:block; background:#171d2c; border:1px solid #252d40; color:#eaeaf1;
        text-decoration:none; border-radius:12px; padding:18px 20px; margin:14px 0;
        transition:.15s; }}
.card:hover {{ background:#1d2437; border-color:#3a4a6b; transform:translateY(-1px); }}
.card-title {{ font-size:1.1rem; font-weight:600; margin-bottom:4px; color:#fff; }}
.card-sub {{ color:#9aa4b8; font-size:.9rem; margin-bottom:8px; }}
.card-meta {{ color:#6f7a8f; font-size:.78rem; }}
.empty {{ color:#8b95a8; text-align:center; padding:60px 0; }}
</style></head>
<body>
<div class="wrap">
  <div class="nav"><a href="/radar/">🔭 前沿雷达 · AI 论文速览与深读 →</a></div>
  <h1>📚 视频笔记库</h1>
  <div class="sub">由 watch-video 技能生成的视频图文笔记</div>
  {cards}
</div>
</body></html>"""
    (REPORT / "index.html").write_text(html, encoding="utf-8")
    print(f"[✓] 主页: {REPORT / 'index.html'} ({len(notes)} 篇笔记)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        nid = sys.argv[1]
        meta = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        build_note(nid, meta, Path(sys.argv[3]))
    build_index()
