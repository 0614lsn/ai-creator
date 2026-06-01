"""爬虫增量调度器"""
import sqlite3
import random
from datetime import datetime, timedelta
from src.crawler.douban import DoubanCrawler
from src.crawler.weread import WereadCrawler
from src.config import DB_PATH


class CrawlScheduler:
    """增量爬取调度器：每日/每周任务管理"""

    def __init__(self):
        self.douban = DoubanCrawler()
        self.weread = WereadCrawler()

    def daily_crawl(self):
        """每日任务：爬取 5-10 本新书"""
        print(f"[{datetime.now()}] 开始每日爬取...")
        douban_books = self.douban.crawl_books(5)
        self._save_books(douban_books, "douban")
        weread_books = self.weread.crawl_books(5)
        self._save_books(weread_books, "weread")
        total = len(douban_books) + len(weread_books)
        print(f"[{datetime.now()}] 每日爬取完成，共 {total} 本书")
        return total

    def weekly_crawl(self):
        """每周任务：深度爬取 2-3 本书的高赞书评"""
        print(f"[{datetime.now()}] 开始每周深度爬取...")
        conn = sqlite3.connect(str(DB_PATH))
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        books = conn.execute(
            "SELECT id, title, author, douban_id, weread_id FROM books WHERE created_at >= ?",
            (cutoff,)
        ).fetchall()
        conn.close()

        selected = random.sample(books, min(3, len(books)))
        total_reviews = 0
        for book in selected:
            book_dict = {
                "id": book[0], "title": book[1], "author": book[2],
                "douban_id": book[3], "weread_id": book[4]
            }
            if book[3]:
                reviews = self.douban.crawl_reviews(book_dict, 3)
                self._save_reviews(book[0], reviews)
                total_reviews += len(reviews)
            if book[4]:
                reviews = self.weread.crawl_reviews(book_dict, 3)
                self._save_reviews(book[0], reviews)
                total_reviews += len(reviews)

        print(f"[{datetime.now()}] 每周深度爬取完成，共 {total_reviews} 条书评")
        return total_reviews

    def _save_books(self, books: list[dict], source: str):
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
                if source == "douban" and book.get("douban_id"):
                    conn.execute(
                        "UPDATE books SET douban_id = ?, cover_url = COALESCE(?, cover_url) WHERE id = ?",
                        (book["douban_id"], book.get("cover_url"), existing[0])
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