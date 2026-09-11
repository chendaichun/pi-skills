#!/usr/bin/env python3
"""frontier-radar 统一配置：路径 / 代理 / 主题词 / 大厂机构 / 会议源。

所有可调项都可以用环境变量覆盖，方便换节点、换库位置。
"""
import os
from pathlib import Path

HOME = Path.home()

# ---------- 隔离代理（mihomo，只给本 skill 用） ----------
RUNTIME = Path(os.environ.get("RADAR_RUNTIME", HOME / ".local/share/frontier-radar"))
MIHOMO_BIN = RUNTIME / "bin" / "mihomo"
MIHOMO_CONF_DIR = RUNTIME / "config"
SUBSCRIPTION_URL_FILE = RUNTIME / "subscription_url.txt"
SUBSCRIPTIONS_DIR = RUNTIME / "subscriptions"
PROXY_PORT = int(os.environ.get("RADAR_PROXY_PORT", "7899"))
CTRL_PORT = int(os.environ.get("RADAR_CTRL_PORT", "9099"))
# 脚本里所有出网请求都带这个代理；设为空字符串可强制直连
PROXY = os.environ.get("RADAR_PROXY", f"http://127.0.0.1:{PROXY_PORT}")

# ---------- 笔记库（放进 watch-video 已服务的目录 => 复用同一个 web 服务器） ----------
NOTES = Path(os.environ.get("RADAR_NOTES_DIR", HOME / "video-notes" / "radar"))  # 由 8000 端口服务
WORKDIR = Path(os.environ.get("RADAR_WORKDIR", HOME / "frontier-work"))         # 中间产物
DATA = WORKDIR / "data"          # 每日抓取的原始 JSON
PAPERS = WORKDIR / "papers"      # 深读论文的全文/文本
DIGEST = WORKDIR / "digest"      # Agent 撰写的 markdown

UA = os.environ.get("RADAR_UA", "frontier-radar/0.1 (personal research radar)")

# ---------- arxiv 关注分类 ----------
ARXIV_CATS = [
    "cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.DC", "cs.SE", "cs.AR", "cs.NE",
]

# ---------- 主题词表：命中越多分越高 ----------
TOPICS = {
    "模型/训练": [
        "pretraining", "pre-training", "post-training", "foundation model",
        "large language model", "llm", "mixture of experts", "moe",
        "transformer", "attention", "long context", "long-context",
        "scaling law", "rlhf", "rlaif", "reinforcement learning from human",
        "rlvr", "reasoning", "chain of thought", "chain-of-thought",
        "test-time", "test time compute", "distillation", "fine-tuning",
        "sft", "instruction tuning", "alignment", "multimodal", "vision language",
    ],
    "Infra/推理部署": [
        "inference", "serving", "throughput", "latency", "kv cache", "kv-cache",
        "paged attention", "quantization", "quantized", "fp8", "int4", "int8",
        "kernel", "cuda", "triton", "tilelang", "flash attention", "speculative decoding",
        "speculative", "distributed training", "tensor parallel", "pipeline parallel",
        "data parallel", "expert parallel", "sequence parallel", "parallelism",
        "scheduling", "cluster", "gpu", "rdma", "nvlink", "interconnect",
        "checkpoint", "fault tolerance", "vllm", "sglang", "tensorrt",
        "prefill", "decode", "batch", "memory bandwidth", "hbm", "roofline",
        "compiler", "graph optimization", "disaggregated", "pd分离",
    ],
    "评测/安全": [
        "benchmark", "evaluation", "eval", "safety", "jailbreak", "hallucination",
        "red team", "interpretability", "mechanistic interpretability",
    ],
}

# ---------- 大厂/知名机构（作者机构或摘要中出现即加权） ----------
ORGS = [
    "OpenAI", "Anthropic", "Google DeepMind", "DeepMind", "Google Research",
    "Meta AI", "Meta Superintelligence", "FAIR", "Microsoft Research", "MSRA",
    "NVIDIA", "DeepSeek", "Alibaba", "Qwen", "Tongyi", "ByteDance", "Seed",
    "Moonshot", "Kimi", "Zhipu", "GLM", "MiniMax", "Baidu", "ERNIE", "Tencent",
    "Hunyuan", "Mistral", "xAI", "Apple", "Amazon", "Huawei", "Noah's Ark",
    "Shanghai AI Lab", "InternLM", "OpenGVLab", "Skywork", "01.AI", "Yi",
    "Tsinghua", "Peking University", "Peking", "USTC", "Zhejiang University",
    "SJTU", "Fudan", "StepFun", "Ant Group", "Tencent Hunyuan",
]
# 这些词命中，强力优先（大厂旗舰模型/报告）
HEADLINE_HINTS = [
    "technical report", "we introduce", "we present", "state-of-the-art",
    "frontier", "flagship",
]

# ---------- 会议论文源（open access 官方 proceedings / anthology） ----------
# 每个源给出：抓取列表页解析规则由 fetch.py 处理
CONFERENCES = {
    "neurips": "https://proceedings.neurips.cc/",
    "icml": "https://proceedings.mlr.press/",
    "acl": "https://aclanthology.org/events/",
    "cvf": "https://openaccess.thecvf.com/",
}
