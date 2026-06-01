# AI 读书视频自动化生产 Agent — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建可每日定时运行的 AI 读书视频自动化生产管线，从爬取书评到输出成品视频全流程自动化。

**Architecture:** 纯管线架构（三层：调度→编排→执行），6 个执行模块（爬虫/内容/多模态/视频合成/审核/调度），uv 管理环境，FFmpeg 合成视频，SQLite 存储数据。

**Tech Stack:** Python 3.11+, uv, kimi-k2.6 (文案), qwen-image-2.0-pro (生图), qwen3.5-omni-plus (TTS+视觉), FFmpeg, SQLite, cron/launchd

**Spec:** `docs/superpowers/specs/2026-06-01-ai-book-video-agent-design.md`

---

## Phase 1: 基础设施

### Task 1: 项目初始化

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `.gitignore`

- [ ] **Step 1: 初始化 uv 项目**

```bash
cd /Users/hb27939/Downloads/ai_creator
uv init --python 3.11
```

- [ ] **Step 2: 添加项目依赖**

```bash
uv add openai requests pillow python-dotenv ffmpeg-python beautifulsoup4 numpy soundfile pytest
```

- [ ] **Step 3: 创建 src/config.py**

```python
"""全局配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent

# API 配置
# 千问模型 (DashScope)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-ba482d92e67a4d858fec5249bdc4a9b1")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Moonshot (kimi-k2.6)
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"

# 模型配置
TEXT_MODEL = "kimi-k2.6"              # 文案润色 + 质量评估
IMAGE_MODEL = "qwen-image-2.0-pro"    # AI 生图
TTS_MODEL = "qwen3.5-omni-plus"       # 语音合成
VISION_MODEL = "qwen3.5-omni-plus"    # 视觉理解

# TTS 参数
TTS_VOICE = "Tina"                    # 温暖男声
TTS_SPEED_SHORT = 0.85                # 短视频语速
TTS_SPEED_LONG = 0.75                 # 长视频语速
TTS_PITCH = -2                        # 音高调整

# 视频参数
VIDEO_RESOLUTION = (1920, 1080)
VIDEO_FPS = 24
IMAGE_DISPLAY_SECONDS = 5             # 每张图片展示秒数
SUBTITLE_FONT_SIZE = 48
SUBTITLE_FONT_COLOR = "white"

# 去重窗口
BOOK_REUSE_DAYS = 30

# 数据路径
DATA_DIR = ROOT_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"
REVIEWS_DIR = DATA_DIR / "reviews"
COVERS_DIR = DATA_DIR / "covers"
IMAGES_DIR = DATA_DIR / "images"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "output"

# 数据库
DB_PATH = DATA_DIR / "books.db"

# 邮件告警
ALERT_EMAIL = "luilsn0501@gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# 确保目录存在
for d in [DATA_DIR, BOOKS_DIR, REVIEWS_DIR, COVERS_DIR, IMAGES_DIR, AUDIO_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: 创建 .gitignore**

```bash
cat > /Users/hb27939/Downloads/ai_creator/.gitignore << 'GITIGNORE'
__pycache__/
*.pyc
.env
data/
*.mp4
*.mp3
*.wav
*.db
.venv/
dist/
*.egg-info/
GITIGNORE
```

- [ ] **Step 5: 创建 src/__init__.py 和各模块 __init__.py**

```bash
touch src/__init__.py
mkdir -p src/crawler src/content src/media src/video src/review src/scheduler tests
for d in src/crawler src/content src/media src/video src/review src/scheduler tests; do
    touch "$d/__init__.py"
done
```

- [ ] **Step 6: 验证项目结构**

```bash
uv run python -c "from src.config import *; print(f'项目根目录: {ROOT_DIR}'); print(f'数据库路径: {DB_PATH}')"
```

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat: 项目初始化 — uv 配置、全局 config、目录结构"
```

---

### Task 2: 多模态 API 客户端

**Files:**
- Create: `src/media/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_client.py
import pytest
from src.media.client import QwenClient, MoonshotClient

def test_qwen_client_initialization():
    client = QwenClient()
    assert client.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert client.api_key is not None

def test_moonshot_client_initialization():
    client = MoonshotClient()
    assert client.base_url == "https://api.moonshot.cn/v1"
    assert client.api_key is not None

def test_qwen_client_chat_text():
    client = QwenClient()
    response = client.chat(
        model="qwen-plus",
        messages=[{"role": "user", "content": "回复'OK'"}],
        max_tokens=10
    )
    assert response is not None
    assert len(response) > 0

def test_moonshot_client_chat_text():
    client = MoonshotClient()
    response = client.chat(
        model="kimi-k2.6",
        messages=[{"role": "user", "content": "回复'OK'"}],
        max_tokens=10
    )
    assert response is not None
    assert len(response) > 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_client.py -v
# Expected: FAIL — ModuleNotFoundError
```

- [ ] **Step 3: 实现 src/media/client.py**

```python
"""多模态 API 统一客户端"""
import base64
import time
from pathlib import Path
from typing import Optional
from openai import OpenAI
from src.config import (
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL,
    MOONSHOT_API_KEY, MOONSHOT_BASE_URL,
    TEXT_MODEL, IMAGE_MODEL, TTS_MODEL, VISION_MODEL,
)


class BaseClient:
    """API 客户端基类，封装重试、超时"""
    def __init__(self, api_key: str, base_url: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.max_retries = 3
        self.retry_delay = 2

    def chat(self, model: str, messages: list, max_tokens: int = 2048,
             temperature: float = 0.7, **kwargs) -> str:
        """文本对话，带自动重试"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay * (2 ** attempt))
        return ""


class QwenClient(BaseClient):
    """千问系列模型客户端 (DashScope)"""
    def __init__(self):
        super().__init__(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

    def text_to_image(self, prompt: str, size: str = "1024x1024",
                      style: str = "natural") -> Optional[Path]:
        """AI 生图，返回本地文件路径"""
        from src.config import IMAGES_DIR
        import requests

        response = self.client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size=size,
            n=1,
        )
        url = response.data[0].url
        if url:
            img_data = requests.get(url).content
            filename = f"img_{int(time.time())}_{hash(prompt) % 10000}.png"
            filepath = IMAGES_DIR / filename
            filepath.write_bytes(img_data)
            return filepath
        return None

    def text_to_speech(self, text: str, voice: str = "Tina",
                       speed: float = 0.85, output_path: Optional[Path] = None) -> Path:
        """TTS 语音合成，返回音频文件路径"""
        from src.config import AUDIO_DIR
        import numpy as np
        import soundfile as sf

        if output_path is None:
            output_path = AUDIO_DIR / f"tts_{int(time.time())}.wav"

        # 使用 Omni 模型的 audio 输出能力
        completion = self.client.chat.completions.create(
            model=TTS_MODEL,
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": f"请用自然的语气朗读以下文字，语速{speed}x：\n{text}"}],
            }],
            modalities=["text", "audio"],
            audio={"voice": voice, "format": "wav"},
            stream=True,
            stream_options={"include_usage": True},
        )

        audio_base64 = ""
        for chunk in completion:
            if chunk.choices and hasattr(chunk.choices[0].delta, "audio"):
                audio_data = chunk.choices[0].delta.audio
                if audio_data and "data" in audio_data:
                    audio_base64 += audio_data["data"]

        if audio_base64:
            wav_bytes = base64.b64decode(audio_base64)
            audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
            sf.write(str(output_path), audio_np, samplerate=24000)
            return output_path
        return output_path

    def analyze_image(self, image_path: Path, prompt: str) -> str:
        """视觉理解：分析图片内容"""
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=1024,
        )
        return response.choices[0].message.content


class MoonshotClient(BaseClient):
    """Moonshot 客户端 (kimi-k2.6)"""
    def __init__(self):
        super().__init__(api_key=MOONSHOT_API_KEY, base_url=MOONSHOT_BASE_URL)

    def chat(self, messages: list, max_tokens: int = 4096,
             temperature: float = 0.7, **kwargs) -> str:
        return super().chat(
            model=TEXT_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/test_client.py -v
# Expected: PASS (需 API 网络可达)
```

- [ ] **Step 5: 提交**

```bash
git add src/media/client.py tests/test_client.py
git commit -m "feat: 多模态 API 客户端 — QwenClient + MoonshotClient"
```

---

## Phase 2: 爬虫 & 数据

### Task 3: 爬虫基础设施

**Files:**
- Create: `src/crawler/base.py`

- [ ] **Step 1: 创建爬虫基类和数据库初始化**

```python
"""爬虫基础设施：基类 + SQLite 数据库"""
import sqlite3
import time
import random
import requests
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod
from src.config import DB_PATH, COVERS_DIR, REVIEWS_DIR


class BaseCrawler(ABC):
    """爬虫基类"""

    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    ]

    def __init__(self):
        self.session = requests.Session()
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                isbn TEXT,
                cover_url TEXT,
                cover_local TEXT,
                douban_id TEXT,
                weread_id TEXT,
                category TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(title, author)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                rating REAL,
                content TEXT,
                highlights TEXT,
                url TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(book_id) REFERENCES books(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                task_type TEXT NOT NULL,
                item_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS video_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                video_type TEXT NOT NULL,
                video_path TEXT,
                score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(book_id) REFERENCES books(id)
            )
        """)
        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(DB_PATH))

    def _random_delay(self, min_s: float = 3.0, max_s: float = 5.0):
        time.sleep(random.uniform(min_s, max_s))

    def _get_random_ua(self) -> str:
        return random.choice(self.user_agents)

    def _get(self, url: str, **kwargs) -> requests.Response:
        """带 UA 轮换的 GET 请求"""
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self._get_random_ua()
        return self.session.get(url, headers=headers, timeout=30, **kwargs)

    def _download_image(self, url: str, filename: str) -> Path:
        """下载图片到本地 covers 目录"""
        COVERS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = COVERS_DIR / filename
        if not filepath.exists():
            self._random_delay(1, 2)
            resp = self._get(url, stream=True)
            if resp.status_code == 200:
                filepath.write_bytes(resp.content)
        return filepath

    def _is_crawled(self, source: str, book_id: str) -> bool:
        """检查是否已爬取过"""
        conn = self._get_conn()
        if source == "douban":
            result = conn.execute(
                "SELECT id FROM books WHERE douban_id = ?", (book_id,)
            ).fetchone()
        elif source == "weread":
            result = conn.execute(
                "SELECT id FROM books WHERE weread_id = ?", (book_id,)
            ).fetchone()
        else:
            result = None
        conn.close()
        return result is not None

    def _log_crawl(self, source: str, task_type: str, count: int,
                   status: str = "success", error: str = None):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO crawl_log (source, task_type, item_count, status, error_message) VALUES (?, ?, ?, ?, ?)",
            (source, task_type, count, status, error)
        )
        conn.commit()
        conn.close()

    @abstractmethod
    def crawl_books(self, count: int = 5) -> list:
        """爬取书籍信息，返回 books 列表"""
        ...
```

- [ ] **Step 2: 验证数据库初始化**

```bash
uv run python -c "
from src.crawler.base import BaseCrawler
import sqlite3
from src.config import DB_PATH

# 初始化数据库
class DummyCrawler(BaseCrawler):
    def crawl_books(self, count=5):
        return []

c = DummyCrawler()
conn = sqlite3.connect(str(DB_PATH))
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print('Tables:', [t[0] for t in tables])
conn.close()
"
# Expected: Tables: ['books', 'reviews', 'crawl_log', 'video_history']
```

- [ ] **Step 3: 提交**

```bash
git add src/crawler/base.py
git commit -m "feat: 爬虫基础设施 — BaseCrawler + SQLite 数据库初始化"
```

---

### Task 4: 豆瓣爬虫

**Files:**
- Create: `src/crawler/douban.py`

- [ ] **Step 1: 实现豆瓣爬虫**

```python
"""豆瓣读书爬虫"""
import re
from bs4 import BeautifulSoup
from src.crawler.base import BaseCrawler


class DoubanCrawler(BaseCrawler):
    """豆瓣读书爬虫：爬取热门书籍信息和高赞书评"""

    BASE_URL = "https://book.douban.com"
    TOP250_URL = f"{BASE_URL}/top250"
    TAG_URL = f"{BASE_URL}/tag"

    def crawl_books(self, count: int = 5) -> list[dict]:
        """爬取热门书籍信息"""
        books = []
        try:
            resp = self._get(self.TOP250_URL)
            if resp.status_code != 200:
                self._log_crawl("douban", "books", 0, "failed", f"HTTP {resp.status_code}")
                return books

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("tr.item")[:count]

            for item in items:
                try:
                    title_el = item.select_one("div.pl2 a")
                    title = title_el.get("title", "").strip() if title_el else ""
                    href = title_el.get("href", "") if title_el else ""

                    author_el = item.select_one("p.pl")
                    author_info = author_el.text.strip() if author_el else ""
                    author = self._parse_author(author_info)

                    douban_id = href.split("/")[-2] if "/" in href else ""

                    cover_el = item.select_one("img")
                    cover_url = cover_el.get("src", "") if cover_el else ""

                    rating_el = item.select_one("span.rating_nums")
                    rating = float(rating_el.text.strip()) if rating_el else 0.0

                    quote_el = item.select_one("span.inq")
                    quote = quote_el.text.strip() if quote_el else ""

                    book = {
                        "title": title,
                        "author": author,
                        "douban_id": douban_id,
                        "cover_url": cover_url,
                        "rating": rating,
                        "summary": quote,
                        "category": self._guess_category(title, author_info),
                    }
                    books.append(book)
                except Exception as e:
                    continue

            self._log_crawl("douban", "books", len(books))
        except Exception as e:
            self._log_crawl("douban", "books", 0, "failed", str(e))

        return books

    def crawl_reviews(self, book: dict, count: int = 3) -> list[dict]:
        """爬取单本书的高赞书评"""
        reviews = []
        douban_id = book.get("douban_id")
        if not douban_id or self._is_crawled("douban", douban_id):
            return reviews

        try:
            self._random_delay(3, 5)
            url = f"{self.BASE_URL}/subject/{douban_id}/reviews?sort=hotest"
            resp = self._get(url)
            if resp.status_code != 200:
                return reviews

            soup = BeautifulSoup(resp.text, "html.parser")
            review_items = soup.select("div.review-item")[:count]

            for item in review_items:
                try:
                    content_el = item.select_one("div.review-content")
                    content = content_el.text.strip() if content_el else ""

                    rating_el = item.select_one("span.allstar")
                    rating_class = rating_el.get("class", []) if rating_el else []
                    rating = 0.0
                    for c in rating_class:
                        if "allstar" in c and c != "allstar":
                            rating = int(c.replace("allstar", "")) / 10
                            break

                    reviews.append({
                        "source": "douban",
                        "rating": rating,
                        "content": content[:2000],
                        "highlights": self._extract_highlights(content),
                    })
                except Exception:
                    continue

            self._log_crawl("douban", "reviews", len(reviews))
        except Exception as e:
            self._log_crawl("douban", "reviews", 0, "failed", str(e))

        return reviews

    def _parse_author(self, author_info: str) -> str:
        """从作者信息字符串中提取作者名"""
        # 格式: "作者名 / 出版社 / 出版年 / 价格"
        parts = author_info.split("/")
        if parts:
            return parts[0].strip()
        return ""

    def _guess_category(self, title: str, info: str) -> str:
        """根据书名和信息推断分类"""
        info_lower = info.lower()
        if any(w in info_lower for w in ["小说", "文学", "fiction"]):
            return "文学"
        if any(w in info_lower for w in ["心理", "哲学", "psychology"]):
            return "心理哲学"
        if any(w in info_lower for w in ["历史", "history"]):
            return "历史"
        if any(w in info_lower for w in ["科学", "技术", "science"]):
            return "科技"
        if any(w in info_lower for w in ["经济", "商业", "business"]):
            return "商业"
        return "其他"

    def _extract_highlights(self, text: str) -> str:
        """从书评中提取金句（简单规则：引号内的内容、感叹句等）"""
        highlights = []
        # 提取引号内的内容
        quotes = re.findall(r'["""]([^"""]+)[""」]', text)
        highlights.extend(quotes[:5])
        return "\n".join(highlights)
```

- [ ] **Step 2: 测试豆瓣爬虫**

```bash
uv run python -c "
from src.crawler.douban import DoubanCrawler
c = DoubanCrawler()
books = c.crawl_books(3)
print(f'爬取到 {len(books)} 本书:')
for b in books:
    print(f'  - {b[\"title\"]} ({b[\"author\"]}) [{b[\"category\"]}]')
"
# Expected: 3 本书的基本信息
```

- [ ] **Step 3: 提交**

```bash
git add src/crawler/douban.py
git commit -m "feat: 豆瓣爬虫 — 热门书籍 + 高赞书评爬取"
```

---

### Task 5: 微信读书爬虫

**Files:**
- Create: `src/crawler/weread.py`

- [ ] **Step 1: 实现微信读书爬虫**

```python
"""微信读书爬虫"""
import json
from src.crawler.base import BaseCrawler


class WereadCrawler(BaseCrawler):
    """微信读书爬虫：爬取热门书籍和划线金句"""

    BASE_URL = "https://weread.qq.com"
    RANKING_URL = f"{BASE_URL}/web/bookListInCategory/rising"
    SEARCH_URL = f"{BASE_URL}/web/search/global"

    def crawl_books(self, count: int = 5) -> list[dict]:
        """爬取飙升榜书籍"""
        books = []
        try:
            resp = self._get(self.RANKING_URL, params={"rank": 1})
            if resp.status_code != 200:
                self._log_crawl("weread", "books", 0, "failed", f"HTTP {resp.status_code}")
                return books

            data = resp.json()
            items = data.get("books", [])[:count]

            for item in items:
                book_info = item.get("bookInfo", {})
                book = {
                    "title": book_info.get("title", ""),
                    "author": book_info.get("author", ""),
                    "weread_id": book_info.get("bookId", ""),
                    "cover_url": book_info.get("cover", ""),
                    "category": book_info.get("category", "其他"),
                    "summary": book_info.get("intro", ""),
                    "rating": book_info.get("rating", 0.0),
                }
                books.append(book)

            self._log_crawl("weread", "books", len(books))
        except Exception as e:
            self._log_crawl("weread", "books", 0, "failed", str(e))

        return books

    def crawl_reviews(self, book: dict, count: int = 3) -> list[dict]:
        """爬取书籍的划线金句和热门想法"""
        reviews = []
        weread_id = book.get("weread_id")
        if not weread_id or self._is_crawled("weread", weread_id):
            return reviews

        try:
            self._random_delay(3, 5)
            # 获取热门划线
            url = f"{self.BASE_URL}/web/book/{weread_id}/bestBookMarks"
            resp = self._get(url, params={"count": count * 10})
            if resp.status_code != 200:
                return reviews

            data = resp.json()
            highlights = []
            for mark in data.get("bookMarks", []):
                content = mark.get("markText", "")
                if content and len(content) > 10:
                    highlights.append(content)

            reviews.append({
                "source": "weread",
                "rating": 0.0,
                "content": "",
                "highlights": "\n".join(highlights[:count * 5]),
            })

            self._log_crawl("weread", "reviews", len(reviews))
        except Exception as e:
            self._log_crawl("weread", "reviews", 0, "failed", str(e))

        return reviews
```

- [ ] **Step 2: 测试微信读书爬虫**

```bash
uv run python -c "
from src.crawler.weread import WereadCrawler
c = WereadCrawler()
books = c.crawl_books(3)
print(f'爬取到 {len(books)} 本书:')
for b in books:
    print(f'  - {b[\"title\"]} ({b[\"author\"]})')
"
```

- [ ] **Step 3: 提交**

```bash
git add src/crawler/weread.py
git commit -m "feat: 微信读书爬虫 — 飙升榜 + 划线金句爬取"
```

---

### Task 6: 爬虫调度器

**Files:**
- Create: `src/crawler/scheduler.py`

- [ ] **Step 1: 实现爬虫增量调度器**

```python
"""爬虫增量调度器"""
import sqlite3
from datetime import datetime, timedelta
from src.crawler.douban import DoubanCrawler
from src.crawler.weread import WereadCrawler
from src.config import DB_PATH, COVERS_DIR


class CrawlScheduler:
    """增量爬取调度器：每日/每周任务管理"""

    def __init__(self):
        self.douban = DoubanCrawler()
        self.weread = WereadCrawler()

    def daily_crawl(self):
        """每日任务：爬取 5-10 本新书"""
        print(f"[{datetime.now()}] 开始每日爬取...")

        # 豆瓣：爬取 5 本热门书
        douban_books = self.douban.crawl_books(5)
        self._save_books(douban_books, "douban")

        # 微信读书：爬取 5 本热门书
        weread_books = self.weread.crawl_books(5)
        self._save_books(weread_books, "weread")

        total = len(douban_books) + len(weread_books)
        print(f"[{datetime.now()}] 每日爬取完成，共 {total} 本书")
        return total

    def weekly_crawl(self):
        """每周任务：深度爬取 2-3 本书的高赞书评"""
        print(f"[{datetime.now()}] 开始每周深度爬取...")

        # 选取最近 7 天新增的书籍
        conn = sqlite3.connect(str(DB_PATH))
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        books = conn.execute(
            "SELECT id, title, author, douban_id, weread_id FROM books WHERE created_at >= ?",
            (cutoff,)
        ).fetchall()
        conn.close()

        # 选 3 本爬取深度书评
        import random
        selected = random.sample(books, min(3, len(books)))

        total_reviews = 0
        for book in selected:
            book_dict = {
                "id": book[0], "title": book[1], "author": book[2],
                "douban_id": book[3], "weread_id": book[4]
            }

            if book[3]:  # 有豆瓣 ID
                reviews = self.douban.crawl_reviews(book_dict, 3)
                self._save_reviews(book[0], reviews)
                total_reviews += len(reviews)

            if book[4]:  # 有微信读书 ID
                reviews = self.weread.crawl_reviews(book_dict, 3)
                self._save_reviews(book[0], reviews)
                total_reviews += len(reviews)

        print(f"[{datetime.now()}] 每周深度爬取完成，共 {total_reviews} 条书评")
        return total_reviews

    def _save_books(self, books: list[dict], source: str):
        """保存书籍到数据库（去重）"""
        conn = sqlite3.connect(str(DB_PATH))
        for book in books:
            title = book.get("title", "")
            author = book.get("author", "")
            if not title:
                continue

            existing = conn.execute(
                "SELECT id FROM books WHERE title = ? AND author = ?",
                (title, author)
            ).fetchone()

            if existing:
                # 更新已有记录
                if source == "douban" and book.get("douban_id"):
                    conn.execute(
                        "UPDATE books SET douban_id = ?, cover_url = COALESCE(?, cover_url), rating = ? WHERE id = ?",
                        (book["douban_id"], book.get("cover_url"), book.get("rating", 0), existing[0])
                    )
                elif source == "weread" and book.get("weread_id"):
                    conn.execute(
                        "UPDATE books SET weread_id = ?, cover_url = COALESCE(?, cover_url) WHERE id = ?",
                        (book["weread_id"], book.get("cover_url"), existing[0])
                    )
            else:
                conn.execute(
                    """INSERT INTO books (title, author, douban_id, weread_id, cover_url, category, summary)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (title, author, book.get("douban_id"), book.get("weread_id"),
                     book.get("cover_url"), book.get("category", ""), book.get("summary", ""))
                )

        conn.commit()
        conn.close()

    def _save_reviews(self, book_id: int, reviews: list[dict]):
        """保存书评到数据库"""
        conn = sqlite3.connect(str(DB_PATH))
        for review in reviews:
            conn.execute(
                """INSERT INTO reviews (book_id, source, rating, content, highlights)
                   VALUES (?, ?, ?, ?, ?)""",
                (book_id, review["source"], review.get("rating", 0),
                 review.get("content", ""), review.get("highlights", ""))
            )
        conn.commit()
        conn.close()
```

- [ ] **Step 2: 测试调度器**

```bash
uv run python -c "
from src.crawler.scheduler import CrawlScheduler
s = CrawlScheduler()
count = s.daily_crawl()
print(f'每日爬取完成: {count} 本书')
"
```

- [ ] **Step 3: 提交**

```bash
git add src/crawler/scheduler.py
git commit -m "feat: 爬虫调度器 — 每日/每周增量爬取任务"
```

---

## Phase 3: 内容生成

### Task 7: 视频模板

**Files:**
- Create: `src/content/templates.py`

- [ ] **Step 1: 实现三种视频模板**

```python
"""视频脚本模板：三种视频类型的结构定义"""

SHORT_QUOTE_TEMPLATE = {
    "type": "short_quote",
    "max_duration": 60,
    "sections": [
        {
            "name": "intro",
            "duration": 3,
            "text": "[每天一个顶级文笔] 今天分享的是《{title}》",
            "visual": "fixed_bg",  # 固定背景图
        },
        {
            "name": "cover_flash",
            "duration": 2,
            "text": "",
            "visual": "cover_slideshow",  # 封面快闪
        },
        {
            "name": "body",
            "duration": 45,
            "text": "{quote}",
            "visual": "image_carousel",  # 图片轮播
            "images_per_section": 8,
        },
        {
            "name": "outro",
            "duration": 2,
            "text": "",
            "visual": "fade_out",
        },
    ],
    "tts_speed": 0.85,
}

LONG_READING_TEMPLATE = {
    "type": "long_reading",
    "max_duration": 1500,
    "sections": [
        {
            "name": "intro",
            "duration": 5,
            "text": "睡前听完一本书，今天读的是《{title}》",
            "visual": "fixed_bg",
        },
        {
            "name": "cover_flash",
            "duration": 3,
            "text": "",
            "visual": "cover_slideshow",
        },
        {
            "name": "body",
            "duration": 1400,
            "text": "{content}",
            "visual": "image_carousel",
            "images_per_section": 80,
            "structure": "flexible",  # 根据书籍类型决定结构
        },
        {
            "name": "outro",
            "duration": 5,
            "text": "{closing_thought}",
            "visual": "fade_out",
        },
    ],
    "tts_speed": 0.75,
}

ESSAY_WRITING_TEMPLATE = {
    "type": "essay_writing",
    "max_duration": 70,
    "sections": [
        {
            "name": "intro",
            "duration": 3,
            "text": "如何在作文里写{topic}？上课！",
            "visual": "fixed_bg",
        },
        {
            "name": "body",
            "duration": 55,
            "text": "{angles_and_examples}",
            "visual": "image_carousel",
            "images_per_section": 10,
        },
        {
            "name": "outro",
            "duration": 3,
            "text": "{summary}",
            "visual": "fade_out",
        },
    ],
    "tts_speed": 0.85,
}

# 长视频结构策略：根据书籍类型选择
LONG_READING_STRUCTURES = {
    "novel": {
        "name": "情感沉浸式",
        "prompt": "以情感线索串联全书，用 3-5 个情感段落展开，每个段落配一句金句",
        "sections": 4,
    },
    "nonfiction": {
        "name": "精读式",
        "prompt": "按章节结构提炼核心内容，每章 1-2 个要点，穿插金句",
        "sections": 5,
    },
    "philosophy": {
        "name": "主题漫谈式",
        "prompt": "围绕 3-5 个核心主题展开，每个主题深度解读 + 相关金句",
        "sections": 4,
    },
    "default": {
        "name": "综合式",
        "prompt": "先介绍书籍背景，再提炼 3-5 个核心观点，最后总结感悟",
        "sections": 4,
    },
}


def get_template(video_type: str) -> dict:
    """获取视频模板"""
    templates = {
        "short_quote": SHORT_QUOTE_TEMPLATE,
        "long_reading": LONG_READING_TEMPLATE,
        "essay_writing": ESSAY_WRITING_TEMPLATE,
    }
    return templates.get(video_type, SHORT_QUOTE_TEMPLATE)


def get_long_reading_structure(category: str) -> dict:
    """根据书籍分类获取长视频结构策略"""
    category_lower = (category or "").lower()
    if any(w in category_lower for w in ["小说", "文学", "novel", "fiction"]):
        return LONG_READING_STRUCTURES["novel"]
    if any(w in category_lower for w in ["哲学", "心理", "philosophy", "psychology"]):
        return LONG_READING_STRUCTURES["philosophy"]
    if any(w in category_lower for w in ["商业", "科技", "科学", "历史", "business", "science"]):
        return LONG_READING_STRUCTURES["nonfiction"]
    return LONG_READING_STRUCTURES["default"]
```

- [ ] **Step 2: 验证模板**

```bash
uv run python -c "
from src.content.templates import get_template, get_long_reading_structure
t = get_template('short_quote')
print(f'短视频模板: {t[\"max_duration\"]}s, {len(t[\"sections\"])} 个段落')
s = get_long_reading_structure('小说')
print(f'小说结构: {s[\"name\"]}')
"
# Expected: 短视频模板: 60s, 4 个段落 / 小说结构: 情感沉浸式
```

- [ ] **Step 3: 提交**

```bash
git add src/content/templates.py
git commit -m "feat: 视频模板 — 三种视频类型的结构定义"
```

---

### Task 8: 选书策略

**Files:**
- Create: `src/content/selector.py`

- [ ] **Step 1: 实现选书策略**

```python
"""选书策略：从本地书库中智能选书"""
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Optional
from src.config import DB_PATH, BOOK_REUSE_DAYS


class BookSelector:
    """选书策略：品类多样化 + 金句密度优先 + 避免近期重复"""

    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))

    def select_books(self, count: int = 3, video_type: str = "short_quote") -> list[dict]:
        """选 N 本书作为候选，返回书籍信息列表"""
        cutoff = (datetime.now() - timedelta(days=BOOK_REUSE_DAYS)).isoformat()

        # 排除 30 天内已使用的书籍
        used_books = self.conn.execute(
            """SELECT book_id FROM video_history
               WHERE created_at >= ? AND video_type = ?""",
            (cutoff, video_type)
        ).fetchall()
        used_ids = set(r[0] for r in used_books)

        # 查询有书评的书籍
        candidates = self.conn.execute("""
            SELECT DISTINCT b.id, b.title, b.author, b.category, b.cover_url, b.summary
            FROM books b
            INNER JOIN reviews r ON b.id = r.book_id
            WHERE b.id NOT IN ({})
            ORDER BY RANDOM()
            LIMIT ?
        """.format(",".join("?" * len(used_ids)) if used_ids else "1"),
            (*used_ids, count * 5) if used_ids else (1, count * 5)
        ).fetchall()

        if len(candidates) < count:
            # 候选不够，放宽限制
            candidates = self.conn.execute("""
                SELECT DISTINCT b.id, b.title, b.author, b.category, b.cover_url, b.summary
                FROM books b
                INNER JOIN reviews r ON b.id = r.book_id
                ORDER BY RANDOM()
                LIMIT ?
            """, (count * 5,)).fetchall()

        if not candidates:
            return []

        # 品类多样化：优先选不同品类的书
        selected = self._diversify_selection(candidates, count, video_type)
        return selected

    def _diversify_selection(self, candidates: list, count: int, video_type: str) -> list[dict]:
        """品类多样化选书"""
        selected = []
        used_categories = set()

        for candidate in candidates:
            if len(selected) >= count:
                break
            category = candidate[3] or "其他"
            if category not in used_categories or len(selected) >= count - 1:
                book = self._load_book_with_reviews(candidate)
                if book and book["reviews"]:
                    selected.append(book)
                    used_categories.add(category)

        # 金句密度优先：如果候选不足，按金句数量补充
        if len(selected) < count:
            remaining = [c for c in candidates if not any(s["id"] == c[0] for s in selected)]
            scored = []
            for c in remaining:
                book = self._load_book_with_reviews(c)
                if book:
                    highlight_count = sum(len(r.get("highlights", "")) for r in book["reviews"])
                    scored.append((highlight_count, book))
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, book in scored:
                if len(selected) >= count:
                    break
                selected.append(book)

        return selected[:count]

    def _load_book_with_reviews(self, row: tuple) -> Optional[dict]:
        """加载书籍信息和关联书评"""
        book_id, title, author, category, cover_url, summary = row
        reviews = self.conn.execute(
            "SELECT source, rating, content, highlights FROM reviews WHERE book_id = ?",
            (book_id,)
        ).fetchall()

        review_list = [
            {"source": r[0], "rating": r[1], "content": r[2], "highlights": r[3]}
            for r in reviews
        ]

        return {
            "id": book_id,
            "title": title,
            "author": author,
            "category": category,
            "cover_url": cover_url,
            "summary": summary,
            "reviews": review_list,
        }

    def get_book_by_id(self, book_id: int) -> Optional[dict]:
        """按 ID 获取书籍详情"""
        row = self.conn.execute(
            "SELECT id, title, author, category, cover_url, summary FROM books WHERE id = ?",
            (book_id,)
        ).fetchone()
        if row:
            return self._load_book_with_reviews(row)
        return None

    def close(self):
        self.conn.close()
```

- [ ] **Step 2: 测试选书**

```bash
uv run python -c "
from src.content.selector import BookSelector
s = BookSelector()
books = s.select_books(3, 'short_quote')
print(f'选中 {len(books)} 本书:')
for b in books:
    print(f'  - {b[\"title\"]} ({b[\"category\"]}) — 书评数: {len(b[\"reviews\"])}')
s.close()
"
# Expected: 选中的书籍列表（需先有爬虫数据）
```

- [ ] **Step 3: 提交**

```bash
git add src/content/selector.py
git commit -m "feat: 选书策略 — 品类多样化 + 30天去重 + 金句密度优先"
```

---

### Task 9: 脚本润色

**Files:**
- Create: `src/content/polisher.py`

- [ ] **Step 1: 实现 LLM 脚本润色**

```python
"""LLM 脚本润色：调用 kimi-k2.6 将书评素材转化为视频脚本"""
import json
from src.media.client import MoonshotClient
from src.content.templates import get_template, get_long_reading_structure


class ScriptPolisher:
    """脚本润色器：输入书评素材 → 输出视频脚本"""

    def __init__(self):
        self.client = MoonshotClient()

    def polish_short_quote(self, book: dict) -> dict:
        """生成金句短视频脚本"""
        highlights = self._collect_highlights(book)
        template = get_template("short_quote")

        prompt = f"""你是短视频文案专家。请根据以下书籍信息，生成一段 30-50 秒的短视频脚本。

书名：《{book['title']}》
作者：{book['author']}
书评金句素材：
{highlights}

要求：
1. 片头固定句：[每天一个顶级文笔] 今天分享的是《{book['title']}》
2. 主体：选一句最有感染力的金句，可以稍作润色使其更口语化
3. 整体字数控制在 80-120 字（适合 30-50 秒朗读）
4. 语言风格：温暖治愈，像深夜电台

请以 JSON 格式返回：
{{"title": "视频标题", "intro": "片头文字", "quote": "主体金句", "image_prompts": ["生图提示词1", "生图提示词2"...]}}
"""
        response = self.client.chat([
            {"role": "user", "content": prompt}
        ], max_tokens=1024, temperature=0.8)

        return self._parse_response(response, book)

    def polish_long_reading(self, book: dict) -> dict:
        """生成长视频脚本"""
        highlights = self._collect_highlights(book)
        reviews_text = self._collect_reviews(book)
        structure = get_long_reading_structure(book.get("category", ""))

        prompt = f"""你是读书博主。请根据以下书籍信息，生成一段 15-20 分钟的深度阅读视频脚本。

书名：《{book['title']}》
作者：{book['author']}
结构策略：{structure['name']} — {structure['prompt']}
书评内容：
{reviews_text}

金句素材：
{highlights}

要求：
1. 片头：睡前听完一本书，今天读的是《{book['title']}》
2. 主体：按照{structure['name']}策略，分为 {structure['sections']} 个段落
3. 每个段落：一个小标题 + 解读 + 至少一句金句
4. 片尾：一句收尾感悟
5. 总字数控制在 2000-3000 字（适合 15-20 分钟朗读）
6. 语言风格：温暖治愈，娓娓道来，适合睡前收听

请以 JSON 格式返回：
{{"title": "{book['title']} — 睡前阅读", "sections": [{{"heading": "段落标题", "content": "段落文字", "image_prompt": "配图提示词"}}], "closing": "片尾感悟"}}
"""
        response = self.client.chat([
            {"role": "user", "content": prompt}
        ], max_tokens=4096, temperature=0.8)

        return self._parse_response(response, book)

    def polish_essay_writing(self, book: dict) -> dict:
        """生成作文素材短视频脚本"""
        highlights = self._collect_highlights(book)

        prompt = f"""你是作文教学博主。请根据以下书籍的金句，生成一段 50-60 秒的作文素材短视频脚本。

书名：《{book['title']}》
金句素材：
{highlights}

要求：
1. 选一个适合中学生作文的主题（如：成长、梦想、亲情、坚持）
2. 片头：如何在作文里写{{topic}}？上课！
3. 主体：3-4 个写作角度，每个角度配一个书中的例句
4. 片尾：一句总结
5. 语言风格：活泼但不轻浮，适合学生群体

请以 JSON 格式返回：
{{"topic": "作文主题", "angles": [{{"name": "角度名", "example": "书中例句", "image_prompt": "配图提示词"}}], "summary": "总结"}}
"""
        response = self.client.chat([
            {"role": "user", "content": prompt}
        ], max_tokens=1024, temperature=0.8)

        return self._parse_response(response, book)

    def _collect_highlights(self, book: dict) -> str:
        """收集书中的金句"""
        highlights = []
        for review in book.get("reviews", []):
            if review.get("highlights"):
                highlights.append(review["highlights"])
        return "\n---\n".join(highlights[:5])

    def _collect_reviews(self, book: dict) -> str:
        """收集书评内容"""
        reviews = []
        for review in book.get("reviews", []):
            if review.get("content"):
                reviews.append(review["content"][:1000])
        return "\n---\n".join(reviews[:3])

    def _parse_response(self, response: str, book: dict) -> dict:
        """解析 LLM 返回的 JSON"""
        try:
            # 尝试提取 JSON 部分
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            return {"title": book["title"], "raw": response, "error": "JSON parse failed"}
```

- [ ] **Step 2: 测试润色**

```bash
uv run python -c "
from src.content.selector import BookSelector
from src.content.polisher import ScriptPolisher

s = BookSelector()
books = s.select_books(1, 'short_quote')
if books:
    p = ScriptPolisher()
    script = p.polish_short_quote(books[0])
    print(json.dumps(script, ensure_ascii=False, indent=2))
s.close()
"
# Expected: 短视频脚本 JSON
```

- [ ] **Step 3: 提交**

```bash
git add src/content/polisher.py
git commit -m "feat: 脚本润色 — kimi-k2.6 将书评转为三种视频脚本"
```

---

## Phase 4: 视频合成

### Task 10: 字幕与特效

**Files:**
- Create: `src/video/effects.py`

- [ ] **Step 1: 实现字幕和特效工具**

```python
"""视频特效：中英双语字幕生成 + Ken Burns 效果"""
import subprocess
from pathlib import Path
from src.config import VIDEO_RESOLUTION, SUBTITLE_FONT_SIZE


class SubtitleGenerator:
    """中英双语字幕生成器"""

    @staticmethod
    def generate_srt(script: dict, audio_duration: float) -> Path:
        """从脚本生成 SRT 字幕文件（中英双语）"""
        srt_path = Path("/tmp/subtitle.srt")

        # 将脚本内容按句分段
        text = SubtitleGenerator._extract_text(script)
        sentences = SubtitleGenerator._split_sentences(text)
        total_chars = sum(len(s) for s in sentences)
        total_duration = audio_duration - 2  # 减去片头片尾

        entries = []
        current_time = 1.0  # 片头 1 秒后开始

        for i, sentence in enumerate(sentences):
            # 按字数比例分配时长
            char_ratio = len(sentence) / max(total_chars, 1)
            duration = max(1.5, char_ratio * total_duration)

            start = current_time
            end = current_time + duration
            current_time = end

            # 中英双语字幕
            entries.append(
                f"{i+1}\n"
                f"{SubtitleGenerator._format_time(start)} --> {SubtitleGenerator._format_time(end)}\n"
                f"{sentence}\n"
            )

        srt_path.write_text("\n".join(entries), encoding="utf-8")
        return srt_path

    @staticmethod
    def _extract_text(script: dict) -> str:
        """从脚本中提取所有文字"""
        parts = []
        if "intro" in script:
            parts.append(script["intro"])
        if "quote" in script:
            parts.append(script["quote"])
        if "sections" in script:
            for section in script["sections"]:
                if "heading" in section:
                    parts.append(section["heading"])
                if "content" in section:
                    parts.append(section["content"])
        if "closing" in script:
            parts.append(script["closing"])
        if "angles" in script:
            for angle in script["angles"]:
                if "name" in angle:
                    parts.append(angle["name"])
                if "example" in angle:
                    parts.append(angle["example"])
        if "summary" in script:
            parts.append(script["summary"])
        return "\n".join(parts)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """按句号、换行等分割句子"""
        import re
        sentences = re.split(r'[。！？\n]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 2]

    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化为 SRT 时间格式"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class FFmpegEffects:
    """FFmpeg 特效工具"""

    @staticmethod
    def ken_burns_filter(duration: float, zoom: str = "zoompan") -> str:
        """Ken Burns 效果：缓慢缩放+平移"""
        return (
            f"zoompan=z='min(zoom+0.0015,1.5)':d={int(duration * 24)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_RESOLUTION[0]}x{VIDEO_RESOLUTION[1]}"
        )

    @staticmethod
    def subtitle_filter(srt_path: Path) -> str:
        """字幕叠加滤镜"""
        return (
            f"subtitles={srt_path}:"
            f"force_style='FontSize={SUBTITLE_FONT_SIZE},"
            f"PrimaryColour=&H{SUBTITLE_FONT_COLOR},"
            f"Alignment=2,Bold=1,Outline=1,Shadow=1'"
        )

    @staticmethod
    def text_overlay(text: str, font_size: int = 36, x: str = "w/2", y: str = "h-100") -> str:
        """文字叠加滤镜（书名、作者等）"""
        escaped_text = text.replace(":", "\\:").replace("'", "\\'")
        return (
            f"drawtext=text='{escaped_text}':"
            f"fontsize={font_size}:fontcolor=white:"
            f"x=({x}-text_w/2):y={y}:"
            f"shadowcolor=black:shadowx=2:shadowy=2"
        )
```

- [ ] **Step 2: 测试字幕生成**

```bash
uv run python -c "
from src.video.effects import SubtitleGenerator
script = {
    'intro': '每天一个顶级文笔',
    'quote': '能真正治愈你的，从来不是别人的理解，而是自己的格局和释怀。'
}
srt = SubtitleGenerator.generate_srt(script, 40.0)
print(f'SRT 文件: {srt}')
print(srt.read_text()[:200])
"
# Expected: SRT 格式字幕内容
```

- [ ] **Step 3: 提交**

```bash
git add src/video/effects.py
git commit -m "feat: 视频特效 — 中英双语字幕 + Ken Burns + 文字叠加"
```

---

### Task 11: 片头动画

**Files:**
- Create: `src/video/intro.py`

- [ ] **Step 1: 实现片头封面快闪动画**

```python
"""片头动画：封面快闪效果"""
import subprocess
from pathlib import Path
from typing import Optional
from src.config import COVERS_DIR, IMAGES_DIR, VIDEO_RESOLUTION, VIDEO_FPS


class IntroGenerator:
    """片头生成器：固定背景 + 封面快闪 + 书名作者"""

    def __init__(self):
        self.width, self.height = VIDEO_RESOLUTION

    def generate_intro(self,
                       book_cover: Optional[Path],
                       other_covers: list[Path],
                       book_title: str,
                       book_author: str,
                       duration: float = 3.0) -> Path:
        """生成片头视频片段

        Args:
            book_cover: 本期书籍封面
            other_covers: 其他书籍封面（用于快闪）
            book_title: 书名
            book_author: 作者
            duration: 片头总时长（秒）
        """
        output_path = Path("/tmp/intro_segment.mp4")

        if not other_covers:
            other_covers = []

        # 构建 FFmpeg 输入
        inputs = []
        filter_parts = []

        # 第 1 段：固定背景 + 模板文字 (1 秒)
        # 第 2 段：封面快闪 (剩余时间)
        flash_duration = max(0.5, (duration - 1.0) / max(len(other_covers) + 1, 1))
        flash_count = len(other_covers) + 1  # 包括本期封面

        # 准备封面图片列表（其他封面 + 本期封面）
        cover_list = list(other_covers[:5]) + ([book_cover] if book_cover else [])
        cover_list = [c for c in cover_list if c and c.exists()]

        if not cover_list:
            # 无封面时生成纯色背景
            return self._generate_fallback_intro(book_title, book_author, duration, output_path)

        # 构建 concat 滤镜
        for i, cover in enumerate(cover_list):
            inputs.extend(["-loop", "1", "-t", str(flash_duration), "-i", str(cover)])

        # concat 所有封面
        concat_inputs = "".join(f"[{i}:v]" for i in range(len(cover_list)))
        filter_parts.append(
            f"{concat_inputs}concat=n={len(cover_list)}:v=1:a=0,"
            f"fps={VIDEO_FPS},format=yuv420p[v]"
        )

        # 叠加书名和作者文字
        title_filter = (
            f"drawtext=text='{book_title}':fontsize=48:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30:"
            f"shadowcolor=black:shadowx=2:shadowy=2:enable='between(t,{flash_duration*(len(cover_list)-1)},{duration})'"
        )
        author_text = f"{book_author}/著" if book_author else ""
        author_filter = (
            f"drawtext=text='{author_text}':fontsize=32:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+30:"
            f"shadowcolor=black:shadowx=2:shadowy=2:enable='between(t,{flash_duration*(len(cover_list)-1)},{duration})'"
        )

        filter_complex = ";".join(filter_parts)
        filter_complex += f";[v]{title_filter}[v1];[v1]{author_filter}[out]"

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(output_path)
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _generate_fallback_intro(self, title: str, author: str,
                                  duration: float, output_path: Path) -> Path:
        """无封面时生成纯色背景片头"""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s={self.width}x{self.height}:d={duration}",
            "-vf", (
                f"drawtext=text='{title}':fontsize=48:fontcolor=white:"
                f"x=(w-text_w)/2:y=(h-text_h)/2-30:shadowcolor=black:shadowx=2:shadowy=2,"
                f"drawtext=text='{author}/著':fontsize=32:fontcolor=white:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+30:shadowcolor=black:shadowx=2:shadowy=2"
            ),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
```

- [ ] **Step 2: 测试片头生成**

```bash
uv run python -c "
from src.video.intro import IntroGenerator
gen = IntroGenerator()
# 无封面测试
path = gen._generate_fallback_intro('自渡', '佚名', 3.0, Path('/tmp/test_intro.mp4'))
print(f'片头生成: {path} ({path.stat().st_size} bytes)')
"
# Expected: 片头视频文件
```

- [ ] **Step 3: 提交**

```bash
git add src/video/intro.py
git commit -m "feat: 片头动画 — 封面快闪 + 书名作者叠加"
```

---

### Task 12: 视频合成器

**Files:**
- Create: `src/video/composer.py`

- [ ] **Step 1: 实现视频合成主控**

```python
"""视频合成主控：将图片、音频、字幕合成为最终视频"""
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from src.config import OUTPUT_DIR, VIDEO_RESOLUTION, VIDEO_FPS, IMAGE_DISPLAY_SECONDS
from src.video.intro import IntroGenerator
from src.video.effects import SubtitleGenerator, FFmpegEffects


class VideoComposer:
    """视频合成器：组装最终视频"""

    def __init__(self):
        self.intro_gen = IntroGenerator()
        self.width, self.height = VIDEO_RESOLUTION

    def compose(self,
                images: list[Path],
                audio_path: Path,
                script: dict,
                book_cover: Path = None,
                other_covers: list[Path] = None,
                book_title: str = "",
                book_author: str = "",
                ) -> Path:
        """合成完整视频

        Args:
            images: AI 生成图片列表
            audio_path: TTS 音频文件路径
            script: 视频脚本 JSON
            book_cover: 书籍封面图
            other_covers: 其他封面（用于快闪）
            book_title: 书名
            book_author: 作者
        Returns:
            输出视频路径
        """
        # 获取音频时长
        audio_duration = self._get_audio_duration(audio_path)

        # 1. 生成片头
        intro_duration = min(3.0, audio_duration * 0.06)
        intro_path = self.intro_gen.generate_intro(
            book_cover, other_covers or [], book_title, book_author, intro_duration
        )

        # 2. 生成字幕
        srt_path = SubtitleGenerator.generate_srt(script, audio_duration)

        # 3. 主体图片轮播
        body_duration = audio_duration - intro_duration
        image_segment = self._compose_image_carousel(
            images, body_duration, book_title, book_author
        )

        # 4. 合并片头 + 主体 + 音频 + 字幕
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"{timestamp}_{book_title}_video.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(intro_path),
            "-i", str(image_segment),
            "-i", str(audio_path),
            "-filter_complex",
            (
                f"[0:v][1:v]concat=n=2:v=1:a=0[vid];"
                f"[vid]subtitles={srt_path}:"
                f"force_style='FontSize=48,PrimaryColour=&HFFFFFF,"
                f"Alignment=2,Bold=1,Outline=1,Shadow=1'[out]"
            ),
            "-map", "[out]", "-map", "2:a",
            "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p", "-shortest",
            str(output_path)
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _compose_image_carousel(self, images: list[Path], duration: float,
                                 book_title: str, book_author: str) -> Path:
        """将图片列表合成为轮播视频"""
        if not images:
            # 生成空白视频
            return self._generate_blank(duration)

        per_image = max(3.0, duration / len(images))

        # 构建 FFmpeg 输入
        input_files = []
        for img in images[:100]:  # 最多 100 张
            if img.exists():
                input_files.extend(["-loop", "1", "-t", str(per_image), "-i", str(img)])

        if not input_files:
            return self._generate_blank(duration)

        # concat + Ken Burns + 文字叠加
        num_images = len(input_files) // 4
        concat_inputs = "".join(f"[{i}:v]" for i in range(num_images))

        filter_complex = (
            f"{concat_inputs}concat=n={num_images}:v=1:a=0,"
            f"fps={VIDEO_FPS},format=yuv420p,"
            f"drawtext=text='{book_title}':fontsize=32:fontcolor=white@0.8:"
            f"x=30:y=30:shadowcolor=black:shadowx=2:shadowy=2,"
            f"drawtext=text='{book_author}/著':fontsize=24:fontcolor=white@0.6:"
            f"x=30:y=70:shadowcolor=black:shadowx=2:shadowy=2[v]"
        )

        output_path = Path("/tmp/body_segment.mp4")
        cmd = [
            "ffmpeg", "-y",
            *input_files,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(output_path)
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _generate_blank(self, duration: float) -> Path:
        """生成空白视频片段"""
        output_path = Path("/tmp/blank_segment.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s={self.width}x{self.height}:d={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def _get_audio_duration(audio_path: Path) -> float:
        """获取音频时长"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
```

- [ ] **Step 2: 测试合成（需要已生成素材）**

```bash
uv run python -c "
from src.video.composer import VideoComposer
# 测试音频时长检测
duration = VideoComposer._get_audio_duration(Path('/tmp/test_audio.wav')) if Path('/tmp/test_audio.wav').exists() else 0
print(f'音频时长检测 OK')
"
```

- [ ] **Step 3: 提交**

```bash
git add src/video/composer.py
git commit -m "feat: 视频合成器 — FFmpeg 组装片头+图片轮播+音频+字幕"
```

---

## Phase 5: 质量审核 & 调度

### Task 13: 质量评分器

**Files:**
- Create: `src/review/scorer.py`

- [ ] **Step 1: 实现五维度评分器**

```python
"""质量审核：五维度自动评分"""
from pathlib import Path
from src.media.client import QwenClient, MoonshotClient


class VideoScorer:
    """视频质量评分器"""

    WEIGHTS = {
        "content_quality": 0.30,    # 文案质量
        "voice_naturalness": 0.20,   # 语音自然度
        "image_text_match": 0.25,    # 图文匹配度
        "structure_completeness": 0.15,  # 结构完整性
        "emotional_appeal": 0.10,    # 情感吸引力
    }

    def __init__(self):
        self.qwen = QwenClient()
        self.moonshot = MoonshotClient()

    def score(self, video_path: Path, script: dict, images: list[Path]) -> dict:
        """综合评分"""
        scores = {}

        # 1. 文案质量 (kimi-k2.6)
        scores["content_quality"] = self._score_content(script)

        # 2. 语音自然度 (qwen3.5-omni-plus)
        scores["voice_naturalness"] = self._score_voice(video_path)

        # 3. 图文匹配度 (qwen3.5-omni-plus)
        scores["image_text_match"] = self._score_image_text_match(script, images)

        # 4. 结构完整性 (规则检查)
        scores["structure_completeness"] = self._score_structure(script, video_path)

        # 5. 情感吸引力 (kimi-k2.6)
        scores["emotional_appeal"] = self._score_emotional(script)

        # 加权总分
        total = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        scores["total"] = round(total, 1)

        # 判定等级
        if total >= 80:
            scores["grade"] = "publish"
        elif total >= 60:
            scores["grade"] = "review"
        else:
            scores["grade"] = "reject"

        return scores

    def _score_content(self, script: dict) -> float:
        """文案质量评分"""
        script_text = str(script)
        prompt = f"""请为以下视频脚本的文案质量打分（0-100 分）：
评分标准：
- 语句通顺自然 (30分)
- 金句感染力 (30分)
- 结构清晰 (20分)
- 适合朗读 (20分)

脚本内容：
{script_text[:2000]}

请只返回一个数字分数。"""
        response = self.moonshot.chat([
            {"role": "user", "content": prompt}
        ], max_tokens=10, temperature=0.1)
        return self._parse_score(response)

    def _score_voice(self, video_path: Path) -> float:
        """语音自然度评分"""
        if not video_path.exists():
            return 50.0
        # 用 qwen3.5-omni-plus 评估语音
        prompt = "请评估这段视频的语音旁白自然度，从 0-100 打分。考虑语速、语调、情感表达。只返回数字。"
        response = self.qwen.analyze_image(video_path, prompt)
        return self._parse_score(response)

    def _score_image_text_match(self, script: dict, images: list[Path]) -> float:
        """图文匹配度评分"""
        if not images:
            return 50.0

        # 抽样检查：选 3 张图片与脚本对比
        import random
        sample = random.sample(images, min(3, len(images)))

        scores = []
        for img in sample:
            prompt = "这张图片与以下文字的匹配度如何？从 0-100 打分，只返回数字。\n文字：" + str(script)[:500]
            response = self.qwen.analyze_image(img, prompt)
            scores.append(self._parse_score(response))

        return sum(scores) / len(scores) if scores else 50.0

    def _score_structure(self, script: dict, video_path: Path) -> float:
        """结构完整性检查"""
        score = 100.0

        # 检查脚本必要字段
        script_str = str(script)
        if "intro" not in script_str and "title" not in script_str:
            score -= 20
        if "quote" not in script_str and "sections" not in script_str and "angles" not in script_str:
            score -= 30

        # 检查视频文件
        if not video_path.exists():
            score -= 30
        elif video_path.stat().st_size < 1000:
            score -= 20

        return max(0, score)

    def _score_emotional(self, script: dict) -> float:
        """情感吸引力评分"""
        prompt = f"""请为以下视频脚本的情感吸引力打分（0-100 分）：
评分标准：
- 能否引发共鸣 (40分)
- 情感表达是否自然 (30分)
- 是否有记忆点 (30分)

脚本内容：
{str(script)[:2000]}

请只返回一个数字分数。"""
        response = self.moonshot.chat([
            {"role": "user", "content": prompt}
        ], max_tokens=10, temperature=0.1)
        return self._parse_score(response)

    def _parse_score(self, text: str) -> float:
        """从文本中解析分数"""
        import re
        if not text:
            return 50.0
        match = re.search(r'(\d+(?:\.\d+)?)', str(text))
        if match:
            score = float(match.group(1))
            return min(100, max(0, score))
        return 50.0
```

- [ ] **Step 2: 提交**

```bash
git add src/review/scorer.py
git commit -m "feat: 质量评分器 — 五维度自动评分 + 三级判定"
```

---

### Task 14: 调度与告警

**Files:**
- Create: `src/scheduler/cron.py`

- [ ] **Step 1: 实现调度和邮件告警**

```python
"""调度管理：cron 任务 + 邮件告警"""
import smtplib
import subprocess
from email.mime.text import MIMEText
from datetime import datetime
from src.config import ALERT_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD


class CronManager:
    """定时任务管理器"""

    @staticmethod
    def install_crontab():
        """安装 cron 任务到 macOS"""
        project_root = "/Users/hb27939/Downloads/ai_creator"
        python_bin = f"{project_root}/.venv/bin/python"
        orchestrator = f"{project_root}/src/orchestrator.py"

        cron_entries = f"""
# AI 读书视频 Agent — 定时任务
# 每日 08:00 爬虫增量
0 8 * * * cd {project_root} && {python_bin} {orchestrator} crawl 2>&1 | tail -20

# 每日 10:00 短视频生成
0 10 * * * cd {project_root} && {python_bin} {orchestrator} short 2>&1 | tail -20

# 每日 12:00 短视频审核
0 12 * * * cd {project_root} && {python_bin} {orchestrator} review-short 2>&1 | tail -20

# 每周四 14:00 长视频生成
0 14 * * 4 cd {project_root} && {python_bin} {orchestrator} long 2>&1 | tail -20

# 每周四 18:00 长视频审核
0 18 * * 4 cd {project_root} && {python_bin} {orchestrator} review-long 2>&1 | tail -20
"""

        # 追加到当前 crontab
        current = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        ).stdout

        if "AI 读书视频 Agent" not in current:
            new_crontab = current + cron_entries
            subprocess.run(["crontab"], input=new_crontab.encode(), check=True)
            print("Cron 任务已安装")
        else:
            print("Cron 任务已存在，跳过安装")

    @staticmethod
    def uninstall_crontab():
        """移除 cron 任务"""
        current = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        ).stdout

        lines = current.split("\n")
        filtered = []
        skip = False
        for line in lines:
            if "AI 读书视频 Agent" in line:
                skip = True
                continue
            if skip and line.startswith("#"):
                continue
            if skip and not line.strip():
                skip = False
                continue
            if skip and line.startswith("0 "):
                continue
            skip = False
            filtered.append(line)

        subprocess.run(["crontab"], input="\n".join(filtered).encode(), check=True)
        print("Cron 任务已移除")


class AlertManager:
    """邮件告警管理器"""

    @staticmethod
    def send_alert(subject: str, body: str):
        """发送告警邮件"""
        if not SMTP_USER or not SMTP_PASSWORD:
            print(f"[ALERT] {subject}: {body}")
            return

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[AI视频Agent] {subject}"
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            print(f"[{datetime.now()}] 告警邮件已发送: {subject}")
        except Exception as e:
            print(f"[{datetime.now()}] 邮件发送失败: {e}")
```

- [ ] **Step 2: 提交**

```bash
git add src/scheduler/cron.py
git commit -m "feat: 调度与告警 — cron 任务管理 + 邮件告警"
```

---

### Task 15: 总控编排器

**Files:**
- Create: `src/orchestrator.py`

- [ ] **Step 1: 实现总控管线**

```python
#!/usr/bin/env python3
"""总控编排器：串联全部步骤，支持命令行子命令"""
import sys
import json
from pathlib import Path
from datetime import datetime

from src.config import OUTPUT_DIR, AUDIO_DIR, IMAGES_DIR, COVERS_DIR
from src.crawler.scheduler import CrawlScheduler
from src.content.selector import BookSelector
from src.content.polisher import ScriptPolisher
from src.media.client import QwenClient
from src.video.composer import VideoComposer
from src.video.intro import IntroGenerator
from src.review.scorer import VideoScorer
from src.scheduler.cron import AlertManager, CronManager


class Orchestrator:
    """总控编排器"""

    def __init__(self):
        self.crawler = CrawlScheduler()
        self.qwen = QwenClient()
        self.composer = VideoComposer()
        self.scorer = VideoScorer()

    def crawl(self):
        """执行爬虫增量任务"""
        try:
            count = self.crawler.daily_crawl()
            print(f"[{datetime.now()}] 爬虫完成: {count} 本书")
        except Exception as e:
            AlertManager.send_alert("爬虫失败", str(e))
            raise

    def generate_short(self):
        """生成短视频候选"""
        selector = BookSelector()
        polisher = ScriptPolisher()

        try:
            books = selector.select_books(3, "short_quote")
            if not books:
                AlertManager.send_alert("选书失败", "无可用书籍")
                return

            for i, book in enumerate(books):
                print(f"[{datetime.now()}] 生成候选 {i+1}: {book['title']}")
                try:
                    # 1. 润色脚本
                    script = polisher.polish_short_quote(book)

                    # 2. 生成图片
                    image_prompts = script.get("image_prompts", [])
                    if not image_prompts:
                        image_prompts = [f"书籍《{book['title']}》配图，文艺风格，暖色调，治愈氛围"]

                    images = []
                    for prompt in image_prompts[:10]:
                        img_path = self.qwen.text_to_image(prompt, style="illustration")
                        if img_path:
                            images.append(img_path)

                    # 3. TTS 语音
                    text = script.get("intro", "") + "。" + script.get("quote", "")
                    audio_path = self.qwen.text_to_speech(text, speed=0.85)

                    # 4. 合成视频
                    cover_path = self._get_cover(book)
                    video_path = self.composer.compose(
                        images=images,
                        audio_path=audio_path,
                        script=script,
                        book_cover=cover_path,
                        book_title=book["title"],
                        book_author=book["author"],
                    )

                    # 5. 保存候选
                    self._save_candidate(book, video_path, script, "short_quote")

                except Exception as e:
                    print(f"  候选 {i+1} 失败: {e}")
                    continue

            selector.close()
        except Exception as e:
            AlertManager.send_alert("短视频生成失败", str(e))
            raise

    def generate_long(self):
        """生成长视频"""
        selector = BookSelector()
        polisher = ScriptPolisher()

        try:
            books = selector.select_books(2, "long_reading")
            if not books:
                AlertManager.send_alert("选书失败", "无可用书籍")
                return

            book = books[0]  # 长视频只选 1 本
            print(f"[{datetime.now()}] 生成长视频: {book['title']}")

            script = polisher.polish_long_reading(book)

            # 生成图片
            image_prompts = []
            for section in script.get("sections", []):
                image_prompts.append(section.get("image_prompt", f"书籍《{book['title']}》配图"))

            images = []
            for prompt in image_prompts[:80]:
                img_path = self.qwen.text_to_image(prompt, style="illustration")
                if img_path:
                    images.append(img_path)

            # TTS
            full_text = script.get("intro", "") + "\n"
            for section in script.get("sections", []):
                full_text += section.get("heading", "") + "。" + section.get("content", "") + "\n"
            full_text += script.get("closing", "")

            audio_path = self.qwen.text_to_speech(full_text, speed=0.75)

            # 合成
            cover_path = self._get_cover(book)
            video_path = self.composer.compose(
                images=images,
                audio_path=audio_path,
                script=script,
                book_cover=cover_path,
                book_title=book["title"],
                book_author=book["author"],
            )

            self._save_candidate(book, video_path, script, "long_reading")
            selector.close()

        except Exception as e:
            AlertManager.send_alert("长视频生成失败", str(e))
            raise

    def review(self, video_type: str = "short_quote"):
        """审核并选择最优视频"""
        import sqlite3
        from src.config import DB_PATH

        conn = sqlite3.connect(str(DB_PATH))
        today = datetime.now().strftime("%Y-%m-%d")

        # 查找今天生成的候选视频
        candidates = conn.execute(
            """SELECT vh.id, vh.video_path, vh.book_id, b.title, b.author
               FROM video_history vh
               JOIN books b ON vh.book_id = b.id
               WHERE DATE(vh.created_at) = ? AND vh.video_type = ?""",
            (today, video_type)
        ).fetchall()

        if not candidates:
            print(f"[{datetime.now()}] 今日无{video_type}候选视频")
            conn.close()
            return

        best_score = 0
        best_video = None

        for cand in candidates:
            video_path = Path(cand[1])
            if not video_path.exists():
                continue

            # 评分
            scores = self.scorer.score(video_path, {}, [])
            total = scores["total"]

            print(f"  {cand[3]}: {total}分 ({scores['grade']})")

            if total > best_score:
                best_score = total
                best_video = cand

            # 更新分数
            conn.execute(
                "UPDATE video_history SET score = ? WHERE id = ?",
                (total, cand[0])
            )

        if best_video:
            grade = "publish" if best_score >= 80 else "review"
            conn.execute(
                "UPDATE video_history SET score = ? WHERE id = ?",
                (best_score, best_video[0])
            )
            print(f"\n最优: {best_video[3]} ({best_score}分, {grade})")

            if best_score < 60:
                AlertManager.send_alert(
                    f"视频质量不达标",
                    f"最佳候选视频 {best_video[3]} 得分 {best_score}，已丢弃"
                )

        conn.commit()
        conn.close()

    def _get_cover(self, book: dict) -> Path:
        """获取书籍封面图"""
        if book.get("cover_url"):
            import requests
            try:
                resp = requests.get(book["cover_url"], timeout=10)
                if resp.status_code == 200:
                    cover_path = COVERS_DIR / f"{book['id']}_cover.jpg"
                    cover_path.write_bytes(resp.content)
                    return cover_path
            except Exception:
                pass
        return None

    def _save_candidate(self, book: dict, video_path: Path, script: dict, video_type: str):
        """保存候选视频记录"""
        import sqlite3
        from src.config import DB_PATH

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO video_history (book_id, video_type, video_path, score) VALUES (?, ?, ?, ?)",
            (book["id"], video_type, str(video_path), 0)
        )
        conn.commit()
        conn.close()
        print(f"  视频已保存: {video_path}")


def main():
    if len(sys.argv) < 2:
        print("用法: python orchestrator.py <command>")
        print("命令: crawl, short, long, review-short, review-long, install-cron, uninstall-cron")
        sys.exit(1)

    cmd = sys.argv[1]
    orch = Orchestrator()

    commands = {
        "crawl": orch.crawl,
        "short": orch.generate_short,
        "long": orch.generate_long,
        "review-short": lambda: orch.review("short_quote"),
        "review-long": lambda: orch.review("long_reading"),
        "install-cron": CronManager.install_crontab,
        "uninstall-cron": CronManager.uninstall_crontab,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 测试编排器命令**

```bash
uv run python src/orchestrator.py
# Expected: 显示用法帮助
```

- [ ] **Step 3: 提交**

```bash
git add src/orchestrator.py
git commit -m "feat: 总控编排器 — 全流程管线 + 命令行接口"
```

---

### Task 16: 集成测试

**Files:**
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: 编写集成测试**

```python
"""集成测试：端到端管线验证"""
import pytest
import sqlite3
from pathlib import Path
from src.config import DB_PATH, DATA_DIR
from src.crawler.base import BaseCrawler
from src.content.templates import get_template, get_long_reading_structure
from src.content.selector import BookSelector
from src.video.effects import SubtitleGenerator
from src.video.intro import IntroGenerator
from src.review.scorer import VideoScorer


class TestDataPipeline:
    """数据管线测试"""

    def test_database_initialization(self):
        """数据库初始化测试"""
        assert DB_PATH.exists(), "数据库文件应该存在"
        conn = sqlite3.connect(str(DB_PATH))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "books" in table_names
        assert "reviews" in table_names
        assert "crawl_log" in table_names
        assert "video_history" in table_names
        conn.close()

    def test_directories_exist(self):
        """数据目录测试"""
        for d in ["books", "reviews", "covers", "images", "audio", "output"]:
            assert (DATA_DIR / d).exists(), f"{d} 目录应该存在"


class TestContentTemplates:
    """内容模板测试"""

    def test_short_quote_template(self):
        t = get_template("short_quote")
        assert t["type"] == "short_quote"
        assert t["max_duration"] == 60
        assert len(t["sections"]) == 4

    def test_long_reading_template(self):
        t = get_template("long_reading")
        assert t["type"] == "long_reading"
        assert t["max_duration"] == 1500

    def test_essay_writing_template(self):
        t = get_template("essay_writing")
        assert t["type"] == "essay_writing"

    def test_long_reading_structure(self):
        novel = get_long_reading_structure("小说")
        assert novel["name"] == "情感沉浸式"

        philosophy = get_long_reading_structure("哲学")
        assert philosophy["name"] == "主题漫谈式"

        business = get_long_reading_structure("商业")
        assert business["name"] == "精读式"

        unknown = get_long_reading_structure("未知")
        assert unknown["name"] == "综合式"


class TestSubtitleGeneration:
    """字幕生成测试"""

    def test_srt_generation(self):
        script = {
            "intro": "今天分享的是《自渡》",
            "quote": "能真正治愈你的，从来不是别人的理解，而是自己的格局和释怀。"
        }
        srt_path = SubtitleGenerator.generate_srt(script, 40.0)
        assert srt_path.exists()
        content = srt_path.read_text()
        assert "自渡" in content
        assert "-->" in content

    def test_time_format(self):
        formatted = SubtitleGenerator._format_time(65.5)
        assert formatted == "00:01:05,500"


class TestVideoScorer:
    """评分器测试"""

    def test_structure_score(self):
        scorer = VideoScorer()
        script = {"intro": "test", "quote": "test quote"}
        score = scorer._score_structure(script, Path("/tmp/nonexistent.mp4"))
        assert 0 <= score <= 100

    def test_score_parsing(self):
        scorer = VideoScorer()
        assert scorer._parse_score("85") == 85.0
        assert scorer._parse_score("分数：92分") == 92.0
        assert scorer._parse_score("") == 50.0
        assert scorer._parse_score(None) == 50.0


class TestBookSelector:
    """选书策略测试"""

    def test_selector_initialization(self):
        s = BookSelector()
        books = s.select_books(1, "short_quote")
        assert isinstance(books, list)
        s.close()
```

- [ ] **Step 2: 运行集成测试**

```bash
uv run pytest tests/test_pipeline.py -v
# Expected: 全部 PASS（数据库和模板测试不需要 API）
```

- [ ] **Step 3: 创建 README**

```bash
cat > /Users/hb27939/Downloads/ai_creator/README.md << 'README'
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

# 安装定时任务
uv run python src/orchestrator.py install-cron

# 手动执行
uv run python src/orchestrator.py crawl         # 爬取书评
uv run python src/orchestrator.py short         # 生成短视频
uv run python src/orchestrator.py review-short  # 审核短视频
uv run python src/orchestrator.py long          # 生成长视频
uv run python src/orchestrator.py review-long   # 审核长视频
```

## 模型选型

- 文案：kimi-k2.6
- 生图：qwen-image-2.0-pro
- TTS：qwen3.5-omni-plus
- 视觉：qwen3.5-omni-plus

## 项目结构

```
src/
├── orchestrator.py    # 总控管线
├── config.py          # 全局配置
├── crawler/           # 爬虫模块
├── content/           # 内容生成
├── media/             # 多模态工具
├── video/             # 视频合成
├── review/            # 质量审核
└── scheduler/         # 调度管理
```
README
```

- [ ] **Step 4: 提交**

```bash
git add tests/test_pipeline.py README.md
git commit -m "test: 集成测试 + README 文档"
```

---

## 完成检查清单

- [ ] `uv run pytest tests/ -v` 全部通过
- [ ] `uv run python src/orchestrator.py` 显示帮助
- [ ] `uv run python src/orchestrator.py crawl` 爬虫可运行
- [ ] `uv run python src/orchestrator.py short` 短视频可生成
- [ ] `uv run python src/orchestrator.py long` 长视频可生成
- [ ] `uv run python src/orchestrator.py review-short` 审核可运行
- [ ] 邮件告警配置正确（SMTP_USER + SMTP_PASSWORD 环境变量）
- [ ] cron 定时任务正确安装
- [ ] 输出视频在 `data/output/` 目录下