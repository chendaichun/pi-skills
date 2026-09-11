---
name: watch-video
description: "看懂 B 站视频或本地视频并产出图文笔记。当用户要求「看」某段视频、了解视频内容/画面、总结视频、或把视频转成图文笔记时使用。流程：下载 → 抽关键帧 → Agent 亲自读图（眼睛）→ faster-whisper 语音转写（耳朵）→ Agent 撰写推文风格文章（大脑）→ 生成笔记库网页供选择阅读。"
metadata:
  author: dyl
  version: 0.2.0
  requires: ffmpeg, yt-dlp, python3+faster-whisper
---

# watch-video — Agent 的眼睛 + 耳朵 + 大脑

把视频变成**图文并茂的笔记**。核心变化（v0.2）：**Agent 自己就能看图**（当前模型 `deepseek-flash` 支持多模态），
不再依赖外部视觉 API。你（Agent）是眼睛也是大脑：亲自读关键帧理解画面，亲自执笔写成文章。

## 职责分工

```
脚本(机械)  ：下载 → 抽关键帧(+缩略图) → 语音转写 → 渲染笔记网页 → 起服务器
Agent(智能) ：读缩略图理解画面 → 综合画面+语音撰写文章 → 判断取舍与配图
```

## 完整工作流

设 `WORKDIR=${WATCH_WORKDIR:-$HOME/eye-work}`，脚本在 `scripts/`。

### 1) 取视频
```bash
# B站链接（需 yt-dlp）
yt-dlp --no-warnings -f "bv*[height<=1080]+ba/b[height<=1080]" -o "$WORKDIR/source.%(ext)s" "<URL>"
# 本地文件直接用
```

### 2) 抽关键帧 + 缩略图（脚本）
```bash
cd ~/.pi/agent/skills/watch-video/scripts
WATCH_WORKDIR=$WORKDIR python3 frames.py "$WORKDIR/source.mp4"
# 可选第2参: 采样间隔秒(默认1), 第3参: scene阈值(默认自适应)
```
产出：`frames/k*.png`(原图) + `frames_small/k*.jpg`(800px缩略图) + `groups/manifest.json`(每帧时间)。

### 3) 👁 读图（这是你 Agent 的核心工作）
用 `read` 工具**逐个读取 `frames_small/k*.jpg`**，理解每帧画面。要点：
- **并行读取**：一次消息里发多个 read 调用，提高效率。
- **读到就记**：每读完一批，立即把「时间 + 画面要点」追加写入 `$WORKDIR/eyes.md`，避免 context 堆积。
- **格式**：`## [00:12] 一句话画面要点`，细节（字幕原文/PPT标题/代码）写在其后。
- **长视频**：分批读（如每批 8 张），每批读完写文件；context 紧张时只精读信息量大的帧（PPT/字幕卡/代码），
  口头播报帧可合并成一句。
- **诚实**：看不清就写"画面模糊/无关键信息"，不要编造。

读取示例（一次读多张）：
```
read frames_small/k000000.jpg
read frames_small/k000001.jpg
```

### 4) 👂 语音转写（脚本）
```bash
WATCH_WORKDIR=$WORKDIR python3 transcribe_file.py "$WORKDIR/source.mp4" "$WORKDIR/transcript.txt"
# 第三可选参数: 语言 zh/en/ja, 默认 zh
```
产出：`transcript.txt`，格式 `[mm:ss -> mm:ss] 文本`。

### 5) 🩹 转录纠错（ASR correction，写文章前必做）
语音转写对**英文技术词**错得很多（音译/近音错字），必须系统纠错，不能带着错写文章：

1. **通读 `transcript.txt`**，把可疑词全挑出来。典型系统性错字：`HPM→HBM`、`现成/县城→线程`、`Colonel/carnal/Kudler→kernel`、
   `举证惩罚/麦帽/MAML→矩阵乘法`、`航球盒→行求和`、`GLU/Killow→GeLU`、`Tryton/trident→Triton`、`计存器→寄存器`、
   `磊家器→累加器`、`研码→掩码`、`不符→stride`、`规议化→归一化`、`Bank Convux→bank conflict`、
   `Memorial Lessing→memory coalescing`、`荣誉读取→冗余读取`、`平净→瓶颈`、`算数强度→算术强度`。
2. **数字必须对照幻灯片/代码**（ASR 最容易把数字读错）——例如把 `18.75%` 说成 `8%`、把 `128 字节` 说成 `228 字节`、
   把 `65536` 说成 `65 百`。以画面为准，不以语音为准。
3. 把纠错结果写成 `$WORKDIR/glossary.md`（**错字 → 正确写法** 的对照表，含数字类）。这张表就是后面写文章的术语锚点。
4. 无法证实的专有名词（讲师姓名、课程编号等）**不臆断**，宁可写"主讲教授"。

### 6) 🗂 写作规划（写文章前先定，保证前后一致）
先写 `$WORKDIR/outline.md`，再动笔。内容至少包括：
- **统一术语表**：每个关键概念定一个写法（首次"中文（English）"，其后只用中文），全文不得一处一个译法。
- **体例约定**：章节标题格式、代码块、数字/单位、引语、图注写法。
- **章节结构**：按逻辑列出 `##` 小节顺序。
- **逻辑呼应清单**：导读承诺的内容必须在小节里逐一兑现；结尾回收导读。

写作时严格照 `outline.md` 执行；写完做一次自检（用词一致性、数字、图注、呼应）。

### 7) ✍ 撰写文章（你是大脑）
读取 `eyes.md`（画面）+ `transcript.txt`（语音）+ `glossary.md`（纠错术语）+ `outline.md`（大纲），
**消化后自己写**一篇微信推文风格的文章，写入 `$WORKDIR/article/article.md`。要求：
- **开篇导读**：类似论文摘要，一段话讲清"这视频讲了什么、逻辑主线、看点是什么"。
- **分小节**：用 `## 小标题` 组织逻辑，不是流水账；小节之间用平行结构。
- **图文配合**：在合适位置插入图片指令 `![图注](images/k000000.png)`（文件名对应帧）。
- **不要粘贴**：不要直接复述画面识别结果或转写原文，要用自己的话重新组织、提炼、解释。
- **术语一致**：严格照 `glossary.md` 用词，同一概念全文一个写法。
- **保留视频风味（重要）**：笔记不是干巴巴的摘要，要有“现场感”——保留讲师原话/口头禅/吐槽（用 `>` 或引号）、
  师生问答（重要异地穿插、其余集中成“现场问答选”一节）、白板/助教/笑声等真实细节、以及“那我们先聊聊…”这类真实现场语序。
  **不删信息**：宁可写长，也不要把例子、走查、数字、旁支说明压缩掉；压缩的是口水词，不是内容。
- **渲染器语法**：支持 `#/##/###`、`>` 引用、`-` 列表、`**粗体**`、``` 代码块、`![图注](images/xx.png)`；
  不支持表格/嵌套列表，避免花哨语法。
- 标题、术语以画面为准；识别小错用 `glossary.md` 纠正。

同时写元数据 `$WORKDIR/note-meta.json`：
```json
{"title":"文章标题","subtitle":"一句话副标题","author":"watch-video","date":"2026-09-11","source":"B站｜BVxxxx"}
```

### 8) 渲染笔记 + 主页（脚本）
```bash
WATCH_WORKDIR=$WORKDIR python3 report.py <note-id> "$WORKDIR/note-meta.json" "$WORKDIR/article/article.md"
# note-id 自定，如 xinhua-fire-0910；会同时刷新 report/index.html 主页
```

### 9) 预览（脚本 / 常驻服务）
```bash
# 方式一：临时前台
WATCH_WORKDIR=$WORKDIR python3 serve.py --port 8000
# 方式二：常驻服务（已配置 systemd，推荐）
systemctl --user status video-notes      # 查看状态
systemctl --user restart video-notes     # 重启
```
浏览器打开 `http://<局域网IP>:8000`。主页列出**所有历史笔记**（统一库 `~/video-notes/`），点进去看。

## 笔记库（统一存放，不分类）

所有视频笔记都进同一个文件夹 `~/video-notes/`（可用 `WATCH_NOTES_DIR` 改）：

```
~/video-notes/
├── index.html          # 📚 主页：所有笔记列表（历史累积，供选择）
├── serve.log           # 常驻服务日志
├── <note-id>/          # 每篇笔记一个目录
│   ├── index.html
│   ├── meta.json
│   └── images/
└── ...
```

工作目录 `$WORKDIR`（默认 `~/eye-work/`）只放**中间产物**（原视频/帧/转录/文章），笔记成品统一输出到 `~/video-notes/`。

常驻服务由 systemd user 管理（`~/.config/systemd/user/video-notes.service`），已 `enable` +
`loginctl enable-linger dyl`，**开机自启、崩溃自动重拉、注销后仍在**。

## 笔记库结构

```
$WORKDIR/
├── source.mp4
├── frames/          # 原图（报告用）
├── frames_small/    # 缩略图（Agent 读图用）
├── groups/manifest.json
├── eyes.md          # 你读图后的画面笔记
├── transcript.txt   # 耳朵转写
├── glossary.md      # 转录纠错表（错字 → 正确写法）
├── outline.md       # 写作大纲 + 统一术语表
├── article/article.md  # 你撰写的文章
├── note-meta.json
└── report/
    ├── index.html   # 📚 笔记库主页（多篇列表，供选择）
    └── <note-id>/
        ├── index.html   # 单篇笔记
        ├── meta.json
        └── images/      # 该笔记配图
```

## 关键经验 / 坑

- **先规划再写**：写文章前必须先出 `outline.md`（术语表 + 体例 + 章节结构），写完自检一致性。
- **转录必纠错**：ASR 对英文技术词和数字错得很多，写文章前必做 `glossary.md` 纠错，数字以画面为准。
- **术语要统一**：同一概念全文一个写法，首次"中文（English）"，其后只用中文。
- **笔记统一库**：所有笔记输出到 `~/video-notes/`（`WATCH_NOTES_DIR` 可改），历史累积，主页自动列出。
- **眼睛用 Agent 自己**：`read frames_small/*.jpg`。800px 缩略图对字幕/PPT/代码已足够清晰，比原图省 token。
- **API 模式（可选）**：如需无人值守批量，可设 `WATCH_EYE_MODE=api`，用 `worker.py`+`scheduler.py`
  调外部多模态 API（默认 qwen3.8-chat；qwen3.7-plus 思考模式有 bug 会返回乱码，别用）。
- **API 密钥配置**：不要把 key 写进 `config.py`。复制 `scripts/secrets.example.py` 为
  `scripts/secrets.py` 并填入 `WATCH_API_KEY`（该文件已被 gitignore），或用环境变量 `WATCH_API_KEY`。
- **抽帧策略**：scene 检测（自适应阈值：<60s=0.15, <5min=0.25, <30min=0.32, 更长=0.4）
  + 固定间隔兜底。新闻/讲课这类"画面几乎不动只变字幕"的视频，scene 抓不到，靠固定间隔。
- **并行数 8**：API 模式并发别超 8，密度过高会被限流。
- **B 站下载**：普通投稿免费，1080P/番剧可能要 Cookie（`yt-dlp --cookies-from-browser`）。
- **服务器后台启动**：用 `nohup ... &`，`setsid` 在本环境易被回收。
