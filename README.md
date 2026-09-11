# pi-skills

我的 [pi](https://github.com/earendil-works/pi) agent 技能集合，本地目录 `~/.pi/agent/skills/`。

## 技能列表

| 技能 | 说明 |
| --- | --- |
| [`watch-video`](./watch-video/) | 看懂 B 站/本地视频，产出图文笔记（抽帧 → Agent 读图 → 语音转写 → 写文章 → 笔记库网页） |
| [`frontier-radar`](./frontier-radar/) | 前沿论文雷达：隔离代理抓 arXiv/会议，主题打分，生成每日 digest |

## 使用

把仓库 clone 或软链到 `~/.pi/agent/skills/`：

```bash
git clone git@github.com:chendaichun/pi-skills.git ~/pi-skills
ln -s ~/pi-skills/watch-video ~/.pi/agent/skills/watch-video
```

## 密钥 / 私密配置

**不要提交任何密钥。** 各技能的密钥统一放在对应 `scripts/secrets.py`（已被 `.gitignore` 忽略），
模板见 `scripts/secrets.example.py`。也支持环境变量覆盖。

```bash
cp watch-video/scripts/secrets.example.py watch-video/scripts/secrets.py
# 编辑填入自己的 key
```
