"""视频脚本模板：三种视频类型的结构定义"""

SHORT_QUOTE_TEMPLATE = {
    "type": "short_quote",
    "max_duration": 60,
    "sections": [
        {"name": "intro", "duration": 3, "text": "[每天一个顶级文笔] 今天分享的是《{title}》", "visual": "fixed_bg"},
        {"name": "cover_flash", "duration": 2, "text": "", "visual": "cover_slideshow"},
        {"name": "body", "duration": 45, "text": "{quote}", "visual": "image_carousel", "images_per_section": 8},
        {"name": "outro", "duration": 2, "text": "", "visual": "fade_out"},
    ],
    "tts_speed": 0.85,
}

LONG_READING_TEMPLATE = {
    "type": "long_reading",
    "max_duration": 1500,
    "sections": [
        {"name": "intro", "duration": 5, "text": "睡前听完一本书，今天读的是《{title}》", "visual": "fixed_bg"},
        {"name": "cover_flash", "duration": 3, "text": "", "visual": "cover_slideshow"},
        {"name": "body", "duration": 1400, "text": "{content}", "visual": "image_carousel", "images_per_section": 80, "structure": "flexible"},
        {"name": "outro", "duration": 5, "text": "{closing_thought}", "visual": "fade_out"},
    ],
    "tts_speed": 0.75,
}

ESSAY_WRITING_TEMPLATE = {
    "type": "essay_writing",
    "max_duration": 70,
    "sections": [
        {"name": "intro", "duration": 3, "text": "如何在作文里写{topic}？上课！", "visual": "fixed_bg"},
        {"name": "body", "duration": 55, "text": "{angles_and_examples}", "visual": "image_carousel", "images_per_section": 10},
        {"name": "outro", "duration": 3, "text": "{summary}", "visual": "fade_out"},
    ],
    "tts_speed": 0.85,
}

LONG_READING_STRUCTURES = {
    "novel": {"name": "情感沉浸式", "prompt": "以情感线索串联全书，用 3-5 个情感段落展开，每个段落配一句金句", "sections": 4},
    "nonfiction": {"name": "精读式", "prompt": "按章节结构提炼核心内容，每章 1-2 个要点，穿插金句", "sections": 5},
    "philosophy": {"name": "主题漫谈式", "prompt": "围绕 3-5 个核心主题展开，每个主题深度解读 + 相关金句", "sections": 4},
    "default": {"name": "综合式", "prompt": "先介绍书籍背景，再提炼 3-5 个核心观点，最后总结感悟", "sections": 4},
}


def get_template(video_type: str) -> dict:
    templates = {
        "short_quote": SHORT_QUOTE_TEMPLATE,
        "long_reading": LONG_READING_TEMPLATE,
        "essay_writing": ESSAY_WRITING_TEMPLATE,
    }
    return templates.get(video_type, SHORT_QUOTE_TEMPLATE)


def get_long_reading_structure(category: str) -> dict:
    category_lower = (category or "").lower()
    if any(w in category_lower for w in ["小说", "文学", "novel", "fiction"]):
        return LONG_READING_STRUCTURES["novel"]
    if any(w in category_lower for w in ["哲学", "心理", "philosophy", "psychology"]):
        return LONG_READING_STRUCTURES["philosophy"]
    if any(w in category_lower for w in ["商业", "科技", "科学", "历史", "business", "science"]):
        return LONG_READING_STRUCTURES["nonfiction"]
    return LONG_READING_STRUCTURES["default"]