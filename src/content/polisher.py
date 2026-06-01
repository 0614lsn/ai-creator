"""LLM 脚本润色：调用 kimi-k2.6 将书评素材转化为视频脚本"""
import json
from src.media.client import QwenClient
from src.content.templates import get_long_reading_structure


class ScriptPolisher:
    """脚本润色器：输入书评素材 → 输出视频脚本"""

    def __init__(self):
        self.client = QwenClient()

    def polish_short_quote(self, book: dict) -> dict:
        highlights = self._collect_highlights(book)
        prompt = f"""你是短视频文案专家。请根据以下书籍信息，生成一段 30-50 秒的短视频脚本。

书名：《{book['title']}》
作者：{book['author']}
书评金句素材：
{highlights}

要求：
1. 片头固定句：[每天一个顶级文笔] 今天分享的是《{book['title']}》
2. 主体：选一句最有感染力的金句，可以稍作润色使其更口语化
3. 整体字数控制在 80-120 字
4. 语言风格：温暖治愈，像深夜电台

请以 JSON 格式返回：
{{"title": "视频标题", "intro": "片头文字", "quote": "主体金句", "image_prompts": ["生图提示词1", "生图提示词2"...]}}"""

        response = self.client.chat(
            model="kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024, temperature=0.8
        )
        return self._parse_response(response, book)

    def polish_long_reading(self, book: dict) -> dict:
        highlights = self._collect_highlights(book)
        reviews_text = self._collect_reviews(book)
        structure = get_long_reading_structure(book.get("category", ""))

        prompt = f"""你是读书博主。请根据以下书籍信息，生成一段 15-20 分钟的深度阅读视频脚本。

书名：《{book['title']}》
作者：{book['author']}
结构策略：{structure['name']} — {structure['prompt']}
书评内容：{reviews_text}
金句素材：{highlights}

要求：
1. 片头：睡前听完一本书，今天读的是《{book['title']}》
2. 主体：按照{structure['name']}策略，分为 {structure['sections']} 个段落
3. 每个段落：一个小标题 + 解读 + 至少一句金句
4. 片尾：一句收尾感悟
5. 总字数控制在 2000-3000 字
6. 语言风格：温暖治愈，娓娓道来，适合睡前收听

请以 JSON 格式返回：
{{"title": "{book['title']} — 睡前阅读", "sections": [{{"heading": "段落标题", "content": "段落文字", "image_prompt": "配图提示词"}}], "closing": "片尾感悟"}}"""

        response = self.client.chat(
            model="kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096, temperature=0.8
        )
        return self._parse_response(response, book)

    def polish_essay_writing(self, book: dict) -> dict:
        highlights = self._collect_highlights(book)
        prompt = f"""你是作文教学博主。请根据以下书籍的金句，生成一段 50-60 秒的作文素材短视频脚本。

书名：《{book['title']}》
金句素材：{highlights}

要求：
1. 选一个适合中学生作文的主题
2. 片头：如何在作文里写{{topic}}？上课！
3. 主体：3-4 个写作角度，每个角度配一个书中的例句
4. 片尾：一句总结
5. 语言风格：活泼但不轻浮

请以 JSON 格式返回：
{{"topic": "作文主题", "angles": [{{"name": "角度名", "example": "书中例句", "image_prompt": "配图提示词"}}], "summary": "总结"}}"""

        response = self.client.chat(
            model="kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024, temperature=0.8
        )
        return self._parse_response(response, book)

    def _collect_highlights(self, book: dict) -> str:
        highlights = []
        for review in book.get("reviews", []):
            if review.get("highlights"):
                highlights.append(review["highlights"])
        return "\n---\n".join(highlights[:5])

    def _collect_reviews(self, book: dict) -> str:
        reviews = []
        for review in book.get("reviews", []):
            if review.get("content"):
                reviews.append(review["content"][:1000])
        return "\n---\n".join(reviews[:3])

    def _parse_response(self, response: str, book: dict) -> dict:
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            return {"title": book["title"], "raw": response, "error": "JSON parse failed"}