"""选书策略：从本地书库中智能选书"""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from src.config import DB_PATH, BOOK_REUSE_DAYS


class BookSelector:
    """选书策略：品类多样化 + 金句密度优先 + 避免近期重复"""

    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))

    def select_books(self, count: int = 3, video_type: str = "short_quote") -> list[dict]:
        """选 N 本书作为候选"""
        cutoff = (datetime.now() - timedelta(days=BOOK_REUSE_DAYS)).isoformat()

        used_books = self.conn.execute(
            "SELECT book_id FROM video_history WHERE created_at >= ? AND video_type = ?",
            (cutoff, video_type)
        ).fetchall()
        used_ids = set(r[0] for r in used_books)

        placeholders = ",".join("?" * len(used_ids)) if used_ids else "0"
        params = list(used_ids) + [count * 5] if used_ids else [count * 5]

        candidates = self.conn.execute(f"""
            SELECT DISTINCT b.id, b.title, b.author, b.category, b.cover_url, b.summary
            FROM books b
            INNER JOIN reviews r ON b.id = r.book_id
            WHERE b.id NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
        """, params).fetchall()

        if len(candidates) < count:
            candidates = self.conn.execute("""
                SELECT DISTINCT b.id, b.title, b.author, b.category, b.cover_url, b.summary
                FROM books b
                INNER JOIN reviews r ON b.id = r.book_id
                ORDER BY RANDOM() LIMIT ?
            """, (count * 5,)).fetchall()

        if not candidates:
            return []

        return self._diversify_selection(candidates, count)

    def _diversify_selection(self, candidates: list, count: int) -> list[dict]:
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
        return selected[:count]

    def _load_book_with_reviews(self, row: tuple) -> Optional[dict]:
        book_id, title, author, category, cover_url, summary = row
        reviews = self.conn.execute(
            "SELECT source, rating, content, highlights FROM reviews WHERE book_id = ?",
            (book_id,)
        ).fetchall()
        return {
            "id": book_id, "title": title, "author": author,
            "category": category, "cover_url": cover_url, "summary": summary,
            "reviews": [{"source": r[0], "rating": r[1], "content": r[2], "highlights": r[3]} for r in reviews],
        }

    def close(self):
        self.conn.close()