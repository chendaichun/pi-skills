#!/usr/bin/env python3
"""单组图调用多模态模型识别。用法: worker.py <group图> <输出json>"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

from config import API_URL, API_KEY, MODEL, MAX_TOKENS, MAX_RETRY, RETRY_TIMEOUT

SYSTEM_PROMPT = (
    "你是一个视频画面理解助手。我给你一张视频的截图帧（单帧）。请仔细观察图中内容，用中文描述："
    "1) 画面里有什么（人物/文字/界面/场景/布局） 2) 如果有屏幕/PPT/文档，尽量读出上面的关键文字、标题、代码片段。"
    "3) 发生了什么动作或变化。如果画面是代码/技术内容，重点提取可辨认的代码、界面元素、按钮文字、章节标题等。"
    "4) 如果有字幕条，读取底部字幕。请如实描述，看不清就说不清，不要编造。\n"
    "输出格式：一段简洁描述（100-250字），不要用列表符号。"
)


def call_qwen(image_b64: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "请描述这张图片的内容。"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
            ]},
        ],
        "max_tokens": MAX_TOKENS,
    }
    data = json.dumps(payload).encode()
    last_err = None
    for attempt in range(MAX_RETRY):
        req = urllib.request.Request(
            API_URL, data=data,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY})
        try:
            resp = urllib.request.urlopen(req, timeout=RETRY_TIMEOUT)
            out = json.loads(resp.read())
            msg = out["choices"][0]["message"]
            text = msg.get("content") or ""
            # 兜底：若 content 为空/未输出，回退到 reasoning_content
            if not text.strip():
                text = msg.get("reasoning_content") or ""
            if text.strip():
                return text
            last_err = "模型返回空输出"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < MAX_RETRY - 1:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"重试{MAX_RETRY}次仍失败: {last_err}")


def main():
    img_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    img_b64 = base64.b64encode(img_path.read_bytes()).decode()
    try:
        text = call_qwen(img_b64)
        result = {"file": str(img_path), "ok": True, "text": text, "error": None}
    except Exception as e:
        result = {"file": str(img_path), "ok": False, "text": None, "error": str(e)}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{'✓' if result['ok'] else '✗'}] {result['file']} -> {out_path.name}", flush=True)


if __name__ == "__main__":
    main()
