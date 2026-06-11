# data/ — 运行时数据

除本文件与 `up_transcripts.json` 外全部 git-ignore，由管线运行时自动创建。

| 路径 | 内容 | 来源 |
|------|------|------|
| `scripts/` | 每次生成的脚本 JSON（旁白/双语字幕/分镜 prompt/实测时长/片段路径） | `llm.py` 产出，TTS 与视频生成后回写 |
| `audio/` | 逐句旁白 wav（已调速调音、修剪静音） | `tts.py` |
| `clips/` | HappyHorse 视频片段 + 片头 mp4 | `videogen.py` / `intro.py` |
| `output/` | 最终成片 `{时间戳}_{书名}_{分辨率}.mp4` | `assemble.py` |
| `history.json` | 已做过的书与产出记录（选书去重用） | `pipeline.py` |
| `up_transcripts.json` | UP 主原视频转写素材（书名/作者/全文/语速与句尾分析），`--from-up` 参数的数据源 | 对 B站视频音轨的 omni 转写 |

## 补充 up_transcripts.json 素材

B站有风控，通用下载器常拿不到流。可行方式（本项目实际采用）：

1. 浏览器打开视频页，从 `window.__playinfo__.data.dash.audio[0].baseUrl` 取音频流地址
2. `curl -H "Referer: https://www.bilibili.com/" -A "Mozilla/5.0" -o xxx.m4s "<url>"`
3. 用 qwen3.5-omni-plus 转写并分析（语速、句尾处理、人声/BGM 响度比），
   按现有 JSON 结构补充字段即可
