#!/usr/bin/env python3
"""并行识别：对 manifest.json 里每个关键帧分别调用多模态模型（单帧，不拼接）。

结果写入 results/r000.json... 每个对应一帧；自动跳过已完成的（断点续跑）。
"""
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path

from config import GROUPS, RESULTS, OUT, PARALLEL

WORKER = Path(__file__).resolve().parent / "worker.py"


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((GROUPS / "manifest.json").read_text())
    # 兼容两种格式：{file,time} 或 {file,times}
    jobs = []
    for i, m in enumerate(manifest):
        f = Path(m["file"])
        t = m.get("time", (m.get("times") or [0])[0])
        jobs.append((f, t, i))

    def run(job):
        img, t, idx = job
        outf = RESULTS / f"r{idx:04d}.json"
        if outf.exists():
            return idx, "cached", outf
        subprocess.run([sys.executable, str(WORKER), str(img), str(outf)],
                       timeout=120)
        return idx, "done", outf

    print(f"[*] 并行 {PARALLEL} 识别关键帧, 共 {len(jobs)} 帧...", flush=True)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        futs = {ex.submit(run, j): j for j in jobs}
        results = {}
        for fut in concurrent.futures.as_completed(futs):
            idx, status, outf = fut.result()
            results[idx] = json.loads(outf.read_text())
            done += 1
            if status == "done":
                print(f"[进度 {done}/{len(jobs)}] 帧{idx} @ {futs[fut][1]}s", flush=True)

    ordered = [results[i] if i in results else {"ok": False, "error": "missing"}
               for i in range(len(jobs))]
    ok = sum(1 for r in ordered if r.get("ok"))
    print(f"[*] 完成: {ok}/{len(ordered)} 帧识别成功")

    # 汇总（按时间排序输出）
    summary_path = OUT / "summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        for i, (job, r) in enumerate(zip(jobs, ordered)):
            img, t, _ = job
            f.write(f"=== {t}s ({img.name}) ===\n")
            f.write(r["text"] if r.get("ok") else f"[失败: {r.get('error')}]\n")
            f.write("\n")
    print(f"[✓] 汇总: {summary_path}")


if __name__ == "__main__":
    main()
