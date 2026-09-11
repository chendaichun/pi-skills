#!/usr/bin/env python3
"""转录：本地 faster-whisper 把音频转成带时间戳文本。

用法: python3 transcribe_file.py <音频> <输出txt> [language]
复用 bv2txt 的转录模块（模型已缓存，秒加载）。
"""
import sys
from pathlib import Path


def main():
    audio = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    lang = sys.argv[3] if len(sys.argv) > 3 else "zh"

    # 复用 bv2txt（已安装或本地项目）
    sys.path.insert(0, str(Path.home() / "bv2txt"))
    from bv2txt import audio as a_mod
    from bv2txt.transcribe import transcribe

    # 转 16k 单声道 wav
    wav = out_path.with_suffix(".wav")
    print(f"[*] 转码 {audio.name} ...", flush=True)
    a_mod.to_wav(audio, wav)
    print(f"[*] 转录中 ...", flush=True)
    lines = transcribe(wav, language=lang)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for start, end, text in lines:
            m1, s1 = divmod(int(start), 60)
            m2, s2 = divmod(int(end), 60)
            f.write(f"[{m1:02d}:{s1:02d} -> {m2:02d}:{s2:02d}] {text}\n")
    print(f"[✓] 转录完成: {len(lines)} 段 → {out_path}")
    wav.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
