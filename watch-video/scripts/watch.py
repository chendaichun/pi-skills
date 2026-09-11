#!/usr/bin/env python3
"""watch 一键入口：视频 → 眼睛+耳朵 → 图文报告 → Web 预览。

用法:
  python3 watch.py <B站链接或视频文件> [--interval 20] [--skip-download] [--no-serve]
  python3 watch.py <文件> --report-only <transcript.txt>   # 只用已有素材生成报告
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

from config import (WORKDIR, GROUPS, RESULTS, OUT, REPORT,
                    FRAME_INTERVAL, PARALLEL)
import frames as frames_mod
import importlib

SCRIPT_DIR = Path(__file__).resolve().parent


def run_py(module, *args, timeout=600):
    subprocess.run([sys.executable, str(SCRIPT_DIR / module), *map(str, args)],
                   check=True, timeout=timeout)


def download(url, workdir):
    """下载 B站 最佳画质含音频。返回本地视频文件路径。"""
    print("[*] 下载视频:", url)
    exe = shutil.which("yt-dlp")
    if not exe:
        exe = str(Path.home() / ".local/bin/yt-dlp")
    out = workdir / "source"
    proc = subprocess.run(
        [exe, "--no-warnings",
         "-f", "bv*[height<=720]+ba/b[height<=720]",
         "-o", str(out) + ".%(ext)s", url],
        capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"下载失败: {proc.stderr[-400:]}")
    cands = sorted(workdir.glob("source.*"))
    if not cands:
        raise RuntimeError("未找到下载文件")
    print(f"[*] 视频: {cands[-1].name}")
    return cands[-1]


def main():
    p = argparse.ArgumentParser(description="一键看懂视频")
    p.add_argument("target", help="B站链接 或 本地视频/音频文件")
    p.add_argument("--interval", type=float, default=FRAME_INTERVAL,
                   help="抽帧间隔秒 (默认20)")
    p.add_argument("--skip-download", action="store_true",
                   help="target 是本地文件, 跳过下载")
    p.add_argument("--no-serve", action="store_true", help="不启动 Web 服务器")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--transcript", help="已有转录文本, 跳过转录")
    args = p.parse_args()

    WORKDIR.mkdir(parents=True, exist_ok=True)
    (WORKDIR / "results").mkdir(exist_ok=True)

    is_url = args.target.startswith(("http://", "https://"))

    # ---- 1. 取视频 ----
    if args.transcript:
        video = args.target
    elif args.skip_download or not is_url:
        video = args.target
    else:
        video = download(args.target, WORKDIR)
    print(f"[*] 输入: {video}")

    # ---- 2. 眼睛：抽帧+识别 ----
    if not (GROUPS / "manifest.json").exists():
        run_py("frames.py", video, args.interval)
    else:
        print("[*] 复用已有 manifest")
    run_py("scheduler.py")

    # ---- 3. 耳朵：转录 ----
    transcript = args.transcript
    if not transcript:
        transcript = WORKDIR / "transcript.txt"
        if not transcript.exists():
            print("[*] 转录中... (本地 faster-whisper)")
            run_py("transcribe_file.py", video, str(transcript))

    # ---- 4. 合成报告 ----
    import report as report_mod
    importlib.reload(report_mod)
    report_mod.build(Path(transcript))

    # ---- 5. Web 预览 ----
    if not args.no_serve:
        import subprocess as sp
        sp.Popen([sys.executable, str(SCRIPT_DIR / "serve.py"),
                  "--port", str(args.port)],
                 stdout=open(WORKDIR / "serve.log", "w"),
                 stderr=subprocess.STDOUT,
                 start_new_session=True)
        print(f"[✓] Web 服务已启动 (日志: {WORKDIR / 'serve.log'})")
        webbrowser.open(f"http://localhost:{args.port}")

    print("\n✅ 全部完成！")
    print(f"  图文报告: {REPORT / 'index.html'}")
    print(f"  纯文本汇总: {OUT / 'summary.txt'}")


if __name__ == "__main__":
    main()
