#!/usr/bin/env python3
"""抓取单篇论文全文，转成 Markdown 供 Agent 深读。

优先 arxiv 官方 HTML（arxiv.org/html/<id>），失败则下 PDF 用 pdftotext。
产出: <WORKDIR>/papers/<id>.md  与 <id>.meta.json

用法:
  python3 fetch_paper.py 2609.09338
  python3 fetch_paper.py https://arxiv.org/abs/2609.09338
"""
import json
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import PAPERS, PROXY  # noqa: E402
import proxy  # noqa: E402


def norm_id(s: str) -> str:
    m = re.search(r"([0-9]{4}\.[0-9]{4,5})(v\d+)?", s)
    return m.group(1) + (m.group(2) or "") if m else s.strip()


class MarkdownExtractor(HTMLParser):
    """把 arxiv(LaTeXML) HTML 抽成 Markdown，丢弃公式/脚本/导航的噪声。"""

    SKIP = {"script", "style", "nav", "header", "footer", "svg", "math"}
    BLOCK = {"p", "section", "div", "ul", "ol", "table", "figure", "tr"}
    HEAD = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ",
            "h5": "##### ", "h6": "###### "}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0
        self.head_prefix = None
        self.head_buf = []
        self.in_math = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if tag == "math":
            self.in_math += 1
            return
        if tag in self.HEAD:
            self.head_prefix = self.HEAD[tag]
            self.head_buf = []
            self._nl()
        if tag == "li":
            self._nl(); self.parts.append("- ")
        if tag in ("p", "figcaption", "tr"):
            self._nl()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag == "math":
            self.in_math = max(0, self.in_math - 1)
            return
        if tag in self.HEAD:
            title = " ".join(x for x in self.head_buf if x).strip()
            self.parts.append(self.head_prefix + title + "\n")
            self.head_prefix = None
            self.head_buf = []
            self._nl()
        if tag in self.BLOCK:
            self._nl()

    def handle_data(self, data):
        if self.skip_depth or self.in_math:
            return
        t = data.strip()
        if not t:
            return
        if self.head_prefix is not None:
            self.head_buf.append(t)
            return
        self.parts.append(t + " ")

    def _nl(self):
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def text(self):
        s = "".join(self.parts)
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        # 砍掉 References 之后的参考文献列表（对深读是噪声），保留 Appendix
        m = re.search(r"\n#+ *(References|Bibliography)\b", s, re.I)
        if m and m.start() > 3000:
            s = s[:m.start()]
        return s.strip()


def html_to_md(html: str) -> str:
    # 尽量只取正文，去掉网页导航噪声
    for pat in (r'<article[^>]*>', r'<div[^>]*class="[^"]*ltx_page_content[^"]*"[^>]*>'):
        m = re.search(pat, html)
        if m:
            end = html.rfind("</article>") if pat.startswith("<article") else len(html)
            html = html[m.start():end if end > m.start() else len(html)]
            break
    ex = MarkdownExtractor()
    ex.feed(html)
    return ex.text()


def _get_retry(url, timeout=60, tries=3):
    last = None
    for i in range(tries):
        try:
            return proxy.http_get(url, timeout=timeout)
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def fetch_by_html(pid: str):
    for url in (f"https://arxiv.org/html/{pid}",
                f"https://ar5iv.labs.arxiv.org/html/{pid}"):
        try:
            raw = _get_retry(url).decode("utf-8", "replace")
            md = html_to_md(raw)
            if len(md) > 6000:  # 太短说明只有摘要/没正文
                return md, url
            print(f"[paper] {url} 正文过短({len(md)})，跳过", file=sys.stderr)
        except Exception as e:
            print(f"[paper] HTML {url} 失败: {e}", file=sys.stderr)
    return None, None


def fetch_by_pdf(pid: str):
    try:
        data = proxy.http_get(f"https://arxiv.org/pdf/{pid}", timeout=120)
    except Exception as e:
        print(f"[paper] PDF 下载失败: {e}", file=sys.stderr)
        return None, None
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        out = subprocess.run(["pdftotext", "-layout", tmp, "-"],
                             capture_output=True, text=True, timeout=120)
        return (out.stdout or None), f"https://arxiv.org/pdf/{pid}"
    finally:
        Path(tmp).unlink(missing_ok=True)


def fetch(pid: str):
    pid = norm_id(pid)
    PAPERS.mkdir(parents=True, exist_ok=True)
    md, src = fetch_by_html(pid)
    if not md:
        print(f"[paper] HTML 不可用，改用 PDF ...", file=sys.stderr)
        md, src = fetch_by_pdf(pid)
    if not md:
        print(f"[paper] ✗ 无法获取 {pid}", file=sys.stderr)
        return None
    out = PAPERS / f"{pid}.md"
    out.write_text(f"<!-- source: {src} -->\n\n" + md, encoding="utf-8")
    (PAPERS / f"{pid}.meta.json").write_text(
        json.dumps({"id": pid, "source": src, "chars": len(md)}, ensure_ascii=False))
    print(f"[paper] ✓ {pid}: {len(md)} 字符 -> {out}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 fetch_paper.py <arxiv-id|url>")
        sys.exit(1)
    fetch(sys.argv[1])
