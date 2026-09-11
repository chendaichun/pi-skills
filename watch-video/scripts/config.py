#!/usr/bin/env python3
"""watch-video 技能的统一配置。所有路径/参数集中在 README 和此处。"""
import os
from pathlib import Path

# ---------- 私密配置加载 ----------
# 优先级：环境变量 > scripts/secrets.py（gitignored）> 代码内默认值
_SECRETS = {}
_secrets_path = Path(__file__).with_name("secrets.py")
if _secrets_path.exists():
    exec(compile(_secrets_path.read_text(encoding="utf-8"), str(_secrets_path), "exec"), _SECRETS)


def _conf(name, default=""):
    """先查环境变量，再查 secrets.py，最后用默认值。"""
    return os.environ.get(name) or _SECRETS.get(name, default)


# ---------- 基础路径 ----------
HOME = Path.home()
# 工作目录：可被环境变量 WATCH_WORKDIR 覆盖（便于不同项目隔离）
WORKDIR = Path(os.environ.get("WATCH_WORKDIR", HOME / "eye-work"))

FRAMES = WORKDIR / "frames"          # 原图（供报告使用）
FRAMES_SMALL = WORKDIR / "frames_small"  # 缩略图（供 Agent 用 read 看，省 token）
SMALL_WIDTH = int(os.environ.get("WATCH_SMALL_WIDTH", "800"))
GROUPS = WORKDIR / "groups"
RESULTS = WORKDIR / "results"       # API 模式识别结果
OUT = WORKDIR / "out"
# 笔记库：所有视频笔记统一存这里（不分类，按需再分）
REPORT = Path(os.environ.get("WATCH_NOTES_DIR", HOME / "video-notes"))

# ---------- 眼睛模式 ----------
# "agent" : Agent 用 read 工具亲自看缩略图（推荐，质量高，省 API）
# "api"   : 调外部多模态 API（无人值守批量）
EYE_MODE = os.environ.get("WATCH_EYE_MODE", "agent")

# ---------- 模型 API（USTC qwen3.8-chat，多模态） ----------
# 密钥请放到 scripts/secrets.py（参考 secrets.example.py），不要写进代码
API_URL = _conf("WATCH_API_URL", "https://api.llm.ustc.edu.cn/v1/chat/completions")
API_KEY = _conf("WATCH_API_KEY")
# 固定 qwen3.8-chat：实测最稳（content 正常返回；qwen3.7 思考模式有 bug 乱码，弃用）
MODEL = _conf("WATCH_MODEL", "qwen3.8-chat")
MAX_TOKENS = 2000
MAX_RETRY = 3
RETRY_TIMEOUT = 100

# ---------- 画面识别参数 ----------
FRAME_INTERVAL = float(os.environ.get("WATCH_FRAME_INTERVAL", "1"))  # 每 N 秒采样一帧(1s高密度)
FRAMES_PER_GROUP = 4      # 每组几张拼图
COLS = 2                  # 拼图列数
PARALLEL = int(os.environ.get("WATCH_PARALLEL", "8"))  # 并行 worker 数（控制调用密度防限流）
# 长视频总帧数上限（防止爆 context）。0 = 按视频时长自适应（见 frames._auto_sampling）
MAX_FRAMES = int(os.environ.get("WATCH_MAX_FRAMES", "0"))
