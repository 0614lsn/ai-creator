# AI 读书视频自动化生产 Agent

自动生成 AI 读书类视频，模仿 B站 up 主"七页读书吧"的内容风格。

## 视频类型

| 类型 | 时长 | 频率 |
|------|------|------|
| 金句短视频 | 30-60s | 每天 1 支 |
| 睡前阅读长视频 | 10-25min | 每周 1 支 |
| 作文素材短视频 | 30-70s | 每周 2-3 支 |

## 快速开始

```bash
# 安装依赖
uv sync

# 初始化数据库
uv run python -c "from src.crawler.base import BaseCrawler; BaseCrawler()"

# 爬取书评
uv run python src/orchestrator.py crawl

# 生成短视频
uv run python src/orchestrator.py short

# 审核短视频
uv run python src/orchestrator.py review-short

# 安装定时任务
uv run python src/orchestrator.py install-cron
```

## 模型选型

| 用途 | 模型 |
|------|------|
| 文案润色 + 质量评估 | kimi-k2.6 |
| AI 生图 | wan2.6-t2i |
| TTS + 视觉理解 | qwen3.5-omni-plus |

## 项目结构

```
src/
├── orchestrator.py    # 总控管线
├── config.py          # 全局配置
├── crawler/           # 爬虫模块（豆瓣 + 微信读书）
├── content/           # 内容生成（选书 + 润色 + 模板）
├── media/             # 多模态工具（生图 + TTS + 视觉）
├── video/             # 视频合成（片头 + 字幕 + 合成）
├── review/            # 质量审核（五维度评分）
└── scheduler/         # 调度管理（cron + 邮件告警）
```