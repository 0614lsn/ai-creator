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