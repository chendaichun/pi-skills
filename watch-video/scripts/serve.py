#!/usr/bin/env python3
"""局域网 Web 服务器：把报告目录暴露出来, 手机/平板浏览器可访问。

用法: python3 serve.py [--port 8000] [--bind 0.0.0.0]
"""
import argparse
import http.server
import socket
import socketserver
import sys
from pathlib import Path

from config import REPORT


def get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    p = argparse.ArgumentParser(description="局域网报告预览服务器")
    p.add_argument("--dir", default=str(REPORT), help="要暴露的目录")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--bind", default="0.0.0.0")
    args = p.parse_args()

    report_dir = Path(args.dir)
    if not (report_dir / "index.html").exists():
        print(f"[!] {report_dir}/index.html 不存在, 先生成报告: python3 report.py")
        sys.exit(1)

    Handler = partial_handler(report_dir)
    with socketserver.TCPServer(("", args.port), Handler) as httpd:
        ip = get_lan_ip()
        print("=" * 50)
        print(f"  📡 报告已在线")
        print(f"  本机:     http://127.0.0.1:{args.port}")
        print(f"  局域网:   http://{ip}:{args.port}")
        print("  Ctrl+C 停止")
        print("=" * 50, flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[!] 已停止")


def partial_handler(directory):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(directory), **kw)

        def log_message(self, fmt, *args):
            sys.stdout.write(f"  [req] {self.address_string()} {fmt % args}\n")

    return H


if __name__ == "__main__":
    main()
