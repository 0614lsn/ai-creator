"""脚本生成：kimi-k2.6 产出金句文案 + 分镜（HappyHorse prompt）"""
import json
import time
from openai import OpenAI

from src.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, TEXT_MODEL

_client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

_SCRIPT_PROMPT = """你是 B站读书账号"每天一个顶级文笔"系列的金牌编导。该系列模仿 up 主"七页读书吧"：\
30-60 秒的读书短视频，温暖治愈的男声旁白朗读书中金句，配电影质感的唯美空镜画面，深夜电台氛围。

请为《{title}》（{author}）创作一支短视频脚本。

【文案要求】
1. 共 6-7 句旁白，每句 18-40 个汉字，总计 140-220 字（成片 35-55 秒）
2. 第 1 句为片头，必须包含"今天分享的是"五个字！二选一：
   「每天一个顶级文笔。今天分享的是{author_short}的《{title}》」，
   或「一句抓人的钩子（点出本书主题的共鸣句）。今天分享的是《{title}》」
3. 中间 4-5 句是这本书中真实存在、广为流传的金句原文（可极轻微润色使其口语顺畅，禁止编造；优先选有画面感、稍长的句子，太短的两个短句可并为一句旁白）
4. 最后 1 句是一句温柔的点题收尾（你来写，呼应金句主题）
5. 每句旁白配一行简洁优美的英文翻译（字幕用）

【画面要求】
6. 先确定一个贯穿全片的画面风格 style：电影感实拍质感，描述清楚色调/光线/氛围/镜头语言，30-60 字
7. 为每句旁白写一个文生视频 prompt（video_prompt）：
   - 必须以 style 原文开头，保证全片风格统一
   - 然后描述本镜头的具体画面：唯美空镜、自然风光、人物剪影或背影、生活化意境片段，与该句旁白的情绪呼应
   - 镜头要"动"起来：描述缓慢推拉/平移/光影变化等运镜
   - 竖屏构图（3:4），主体居中偏下，上方留出天空/留白
   - 画面中严禁出现任何文字、字幕、书本特写文字、logo
   - 严禁出现清晰人脸（只允许剪影、背影、远景）
   - 每个 video_prompt 控制在 80-150 字

【片头素材】
8. cover_prompt：本期书的"标题卡"底图描述（一张呼应全书主题的竖版意境图，约 50 字）
9. intro_cards：另选 3 本气质相近的经典书，作为片头快闪标题卡，每本给 book/author/image_prompt（意境图描述，约 40 字）

【输出格式】严格输出 JSON，不要输出任何其他内容：
{{
  "title": "B站视频标题（吸引人，含书名）",
  "book": "{title}",
  "author": "{author}",
  "style": "全局画面风格描述",
  "cover_prompt": "本期标题卡底图描述",
  "intro_cards": [
    {{"book": "书名", "author": "作者", "image_prompt": "意境图描述"}}
  ],
  "shots": [
    {{"narration": "旁白句", "narration_en": "English subtitle", "video_prompt": "style原文 + 本镜头画面描述"}}
  ]
}}"""


def generate_script(title: str, author: str, hint: str = "") -> dict:
    """生成完整视频脚本（旁白 + 双语字幕 + 分镜 prompt）"""
    author_short = author.split("/")[0].strip()
    prompt = _SCRIPT_PROMPT.format(title=title, author=author, author_short=author_short)
    if hint:
        prompt += f"\n\n【补充素材】可优先参考这些金句：\n{hint}"

    for attempt in range(3):
        resp = _client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.8,
        )
        text = resp.choices[0].message.content or ""
        script = _parse_json(text)
        if script and _validate(script):
            return script
        print(f"  脚本格式校验失败，重试 {attempt + 1}/3")
        time.sleep(2)
    raise RuntimeError("脚本生成失败：LLM 输出无法解析为合法分镜结构")


def _parse_json(text: str) -> dict | None:
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _validate(script: dict) -> bool:
    shots = script.get("shots", [])
    if not (4 <= len(shots) <= 7):
        return False
    if "今天分享的是" not in shots[0].get("narration", ""):
        return False  # 片头句是该系列的固定口播
    for shot in shots:
        if not shot.get("narration") or not shot.get("video_prompt"):
            return False
        if len(shot["narration"]) > 45:  # 过长会超出单镜 15s 上限
            return False
    return True
