#!/usr/bin/env python3
"""关键帧提取：1s 粒度采样 + 场景检测，输出画面变化大的关键帧（单帧存储，不拼图）。

用法: python3 frames.py <video> [interval]
输出: <WORKDIR>/frames/k*.png (关键帧) + manifest.json (每帧时间戳)
"""
import json
import subprocess
import sys
from pathlib import Path

from config import FRAMES, FRAMES_SMALL, SMALL_WIDTH, GROUPS, FRAME_INTERVAL, MAX_FRAMES


def probe_duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True)
    return float(out.stdout.strip())


def _auto_sampling(dur: float) -> tuple:
    """按视频时长自适应采样：(目标最快间隔秒, 帧数上限)。

    原则：越短抽越密，越长抽越稀，但**总帧数随时长温和增长**——
    不再用一个固定上限把长视频一律拉稀。
    """
    if dur <= 120:      # <2min  ：1s 一帧
        return 1, 120
    if dur <= 300:      # <5min  ：2s 一帧
        return 2, 150
    if dur <= 900:      # <15min ：5s 一帧
        return 5, 180
    if dur <= 1800:     # <30min ：8s 一帧
        return 8, 240
    if dur <= 3600:     # <60min ：10s 一帧
        return 10, 320
    return 15, 400      # >60min ：15s 一帧


def _auto_threshold(dur: float) -> float:
    """根据时长自适应 scene 阈值：短视频抽多点，长视频抽少点。"""
    if dur < 60:
        return 0.15
    if dur < 300:
        return 0.25
    if dur < 1800:
        return 0.32
    return 0.4


def extract_keyframes(video: Path, interval: float, scene_threshold: float = None) -> list:
    """双通道抽帧：scene 检测捕捉场景切换 + 固定间隔兑底，合并去重。
    新闻/演讲/教学等静态镜头多的视频, 场景变化少但每帧信息不同, 需要固定间隔兕底。
    返回关键帧文件列表。
    """
    FRAMES.mkdir(parents=True, exist_ok=True)
    for f in FRAMES.iterdir():
        if f.suffix == ".png":
            f.unlink()
    GROUPS.mkdir(parents=True, exist_ok=True)
    for f in GROUPS.iterdir():
        if f.suffix == ".png":
            f.unlink()

    dur = probe_duration(video)
    if scene_threshold is None:
        scene_threshold = _auto_threshold(dur)

    # 通道1: scene 检测（捕捉画面突变）
    scene_cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video),
                 "-vf", f"select='gt(scene,{scene_threshold})',showinfo",
                 "-vsync", "vfr", "-q:v", "3",
                 str(FRAMES / "s%06d.png")]
    subprocess.run(scene_cmd, check=True, capture_output=True)
    # 用 -v info 再跑一次拿时间戳顺序（showinfo 输出到 stderr）
    ts_cmd = ["ffmpeg", "-y", "-v", "info", "-i", str(video),
              "-vf", f"select='gt(scene,{scene_threshold})',showinfo",
              "-vsync", "vfr", "-f", "null", "-"]
    p = subprocess.run(ts_cmd, capture_output=True, text=True)
    import re
    scene_times = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", p.stderr)]

    # 通道2: 固定间隔兑底。间隔与总帧数上限都按视频时长自适应，
    # 显式传入的 interval 作为“更慢”的下限，WATCH_MAX_FRAMES>0 时覆盖自适应上限。
    auto_interval, auto_cap = _auto_sampling(dur)
    base_interval = max(interval, auto_interval)
    frame_cap = MAX_FRAMES if MAX_FRAMES > 0 else auto_cap
    if dur / base_interval > frame_cap:
        base_interval = dur / frame_cap
        print(f"[*] 长视频: 固定间隔自动拉大至 {base_interval:.1f}s "
              f"(上限 {frame_cap} 帧, 时长 {dur:.0f}s)", flush=True)
    n_fixed = int(dur / base_interval) + 1
    fixed_times = [round(i * base_interval) for i in range(n_fixed)]

    import os
    # 合并时间点 (秒, 取整), 去重排序；剔除超出时长的点(结尾抽不出帧)
    dur_int = max(int(dur) - 1, 0)
    all_times = set(round(t) for t in scene_times) | set(fixed_times)
    all_times = sorted(t for t in all_times if 0 <= t <= dur_int)
    print(f"[*] 检测: scene>{scene_threshold} 抓到{len(set(round(t) for t in scene_times))}帧,"
          f" + 固定间隔{base_interval}s 兑底, 合计 {len(all_times)} 帧", flush=True)

    # 从原视频在指定时间点精确取帧, 同时生成缩略图
    FRAMES_SMALL.mkdir(parents=True, exist_ok=True)
    for f in FRAMES_SMALL.glob("*"):
        f.unlink()
    frames = []
    used_times = []
    for sec in all_times:
        idx = len(frames)  # 用实际序号，避免中间失败造成编号断层
        out_png = FRAMES / f"k{idx:06d}.png"
        fcmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{sec}",
                "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out_png)]
        subprocess.run(fcmd, capture_output=True)
        if not out_png.exists():  # 该时间点无帧，跳过
            continue
        # 缩略图(jpg, 供 Agent 用 read 看, 省 token)
        small = FRAMES_SMALL / f"k{idx:06d}.jpg"
        scmd = ["ffmpeg", "-y", "-v", "error", "-i", str(out_png),
                "-vf", f"scale={SMALL_WIDTH}:-1", "-q:v", "4", str(small)]
        subprocess.run(scmd, capture_output=True)
        frames.append(out_png)
        used_times.append(sec)
    print(f"[*] 关键帧: {len(frames)} 个 (原图+{SMALL_WIDTH}px缩略图)", flush=True)
    return frames, used_times


def find_timestamps(frames: list, interval: float):
    """用 ffprobe 读每帧的时间戳（showinfo 已写入 stderr 不通用，改用 equals=1 技巧）。

    简化：用 ffmpeg showinfo 一次性输出每帧时间。
    """
    pass  # 改用下方 showinfo 提取


def make_manifest(frames: list, all_times: list) -> list:
    """由帧文件列表 + 对应时间列表生成清单 (帧顺序与时间一一对应)。"""
    manifest = []
    for i, f in enumerate(frames):
        t = all_times[i] if i < len(all_times) else round(i)
        manifest.append({"file": str(f), "time": t})
    return manifest


def main():
    video = Path(sys.argv[1])
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else FRAME_INTERVAL
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else None
    frames, times = extract_keyframes(video, interval, threshold)
    manifest = make_manifest(frames, times)
    # 去掉时间戳对不上的多余帧
    manifest = manifest[:len(frames)] if len(manifest) <= len(frames) else manifest
    # 保存清单到 GROUPS（沿用 scheduler/report 的读取位置）
    with open(GROUPS / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"[✓] 关键帧清单: {GROUPS / 'manifest.json'} ({len(manifest)} 帧)")
    # 打印时间分布预览
    if manifest:
        ts = [m["time"] for m in manifest]
        print(f"    时间范围: {ts[0]}s ~ {ts[-1]}s, 平均每 {round((ts[-1]-ts[0])/max(len(ts)-1,1))}s 一帧")


if __name__ == "__main__":
    main()
