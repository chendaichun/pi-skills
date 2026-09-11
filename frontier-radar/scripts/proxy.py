#!/usr/bin/env python3
"""隔离代理管理：确保 mihomo 在线、测试出口、刷新订阅、切换节点。

代理只监听 127.0.0.1:7899，不设系统代理、不开 TUN，只有显式使用它的进程才走。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import urllib.request

sys.path.insert(0, str(Path(__file__).parent))
from config import (  # noqa: E402
    MIHOMO_BIN, MIHOMO_CONF_DIR, PROXY, PROXY_PORT, CTRL_PORT,
    SUBSCRIPTION_URL_FILE, SUBSCRIPTIONS_DIR, UA,
)

SERVICE = "frontier-radar-proxy.service"


# ---------- 基础工具 ----------
def _opener(use_proxy=True):
    if use_proxy and PROXY:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_get(url, timeout=30, use_proxy=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return _opener(use_proxy).open(req, timeout=timeout).read()


def systemctl(*args):
    return subprocess.run(["systemctl", "--user", *args],
                          capture_output=True, text=True)


def is_active():
    return systemctl("is-active", SERVICE).stdout.strip() == "active"


def port_open(port=PROXY_PORT):
    import socket
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ctrl_secret():
    try:
        import yaml
        return yaml.safe_load(open(MIHOMO_CONF_DIR / "config.yaml")).get("secret", "")
    except Exception:
        return ""


def ensure(max_wait=15):
    """确保代理在线且可用。返回 True/False。"""
    if not is_active() or not port_open():
        print("[proxy] 启动服务 ...")
        systemctl("start", SERVICE)
        for _ in range(max_wait):
            time.sleep(1)
            if port_open():
                break
    if not port_open():
        print("[proxy] ✗ 端口未监听", file=sys.stderr)
        return False
    return True


def test(urls=("https://export.arxiv.org/api/query?search_query=all:test&max_results=1",
               "https://rss.arxiv.org/rss/cs.DC",
               "https://www.google.com")):
    ok = True
    for u in urls:
        try:
            n = len(http_get(u, timeout=20))
            print(f"[proxy] ✓ {u[:60]} -> 200 ({n}B)")
        except Exception as e:
            ok = False
            print(f"[proxy] ✗ {u[:60]} -> {type(e).__name__}: {e}", file=sys.stderr)
    return ok


# ---------- 节点切换 ----------
def switch_node(node, group="🔰国外流量"):
    secret = ctrl_secret()
    url = f"http://127.0.0.1:{CTRL_PORT}/proxies/{group}"
    data = json.dumps({"name": node}).encode()
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Authorization": f"Bearer {secret}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=8).read()
        print(f"[proxy] 切换到节点: {node}")
        return True
    except Exception as e:
        print(f"[proxy] 切换失败: {e}", file=sys.stderr)
        return False


# ---------- 订阅刷新 ----------
def apply_overrides(cfg):
    """把订阅配置改成隔离运行：专属端口、只听本机、独立控制端口。"""
    import yaml
    secret = ctrl_secret() or os.urandom(16).hex()
    cfg["mixed-port"] = PROXY_PORT
    for k in ("port", "socks-port", "redir-port", "tproxy-port"):
        cfg.pop(k, None)
    cfg["allow-lan"] = False
    cfg["bind-address"] = "127.0.0.1"
    cfg["external-controller"] = f"127.0.0.1:{CTRL_PORT}"
    cfg["secret"] = secret
    cfg["log-level"] = "warning"
    cfg["ipv6"] = False
    cfg["mode"] = "rule"
    # 关键：把各代理组里的 DIRECT 选项挪到末尾，避免默认直连导致全部超时
    for g in cfg.get("proxy-groups", []):
        ps = g.get("proxies", [])
        direct_like = {"DIRECT", "🚀直接连接", "REJECT", "🛑广告拦截"}
        real = [p for p in ps if p not in direct_like]
        direct = [p for p in ps if p in direct_like]
        if real and direct and ps and ps[0] in direct_like:
            g["proxies"] = real + direct
    return cfg


def refresh_subscription():
    """用当前代理抓订阅 -> 覆盖 config -> 重启服务。"""
    import yaml
    if not SUBSCRIPTION_URL_FILE.exists():
        print("[proxy] 找不到订阅地址文件", file=sys.stderr)
        return False
    url = SUBSCRIPTION_URL_FILE.read_text().strip()
    print("[proxy] 拉取订阅 ...")
    try:
        raw = http_get(url, timeout=40)
    except Exception as e:
        print(f"[proxy] 订阅拉取失败: {e}", file=sys.stderr)
        return False
    try:
        cfg = yaml.safe_load(raw)
        assert "proxies" in cfg
    except Exception as e:
        print(f"[proxy] 订阅不是合法 Clash 配置: {e}", file=sys.stderr)
        return False

    # 备份快照
    SUBSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    import time as _t
    (SUBSCRIPTIONS_DIR / f"snapshot-{_t.strftime('%Y%m%d-%H%M%S')}.yaml").write_bytes(raw)

    cfg = apply_overrides(cfg)
    MIHOMO_CONF_DIR.mkdir(parents=True, exist_ok=True)
    with open(MIHOMO_CONF_DIR / "config.yaml", "w") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"[proxy] 已更新配置（{len(cfg['proxies'])} 节点），重启服务 ...")
    systemctl("restart", SERVICE)
    time.sleep(4)
    return ensure() and test()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(f"service: {'active' if is_active() else 'inactive'}")
        print(f"port {PROXY_PORT}: {'open' if port_open() else 'closed'}")
        test()
    elif cmd == "start":
        ensure()
    elif cmd == "test":
        sys.exit(0 if test() else 1)
    elif cmd == "refresh":
        sys.exit(0 if refresh_subscription() else 1)
    elif cmd == "node":
        switch_node(sys.argv[2])
    else:
        print("用法: proxy.py [status|start|test|refresh|node <名称>]")
