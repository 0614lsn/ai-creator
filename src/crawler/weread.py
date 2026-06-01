"""微信读书爬虫"""
from src.crawler.base import BaseCrawler


class WereadCrawler(BaseCrawler):
    """微信读书爬虫：爬取热门书籍和划线金句"""

    BASE_URL = "https://weread.qq.com"
    RANKING_URL = f"{BASE_URL}/web/bookListInCategory/rising"

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
                books.append({
                    "title": book_info.get("title", ""),
                    "author": book_info.get("author", ""),
                    "weread_id": book_info.get("bookId", ""),
                    "cover_url": book_info.get("cover", ""),
                    "category": book_info.get("category", "其他"),
                    "summary": book_info.get("intro", ""),
                    "rating": book_info.get("rating", 0.0),
                })

            self._log_crawl("weread", "books", len(books))
        except Exception as e:
            self._log_crawl("weread", "books", 0, "failed", str(e))

        return books

    def crawl_reviews(self, book: dict, count: int = 3) -> list[dict]:
        """爬取书籍的划线金句和热门想法"""
        reviews = []
        weread_id = book.get("weread_id")
        if not weread_id:
            return reviews

        try:
            self._random_delay(3, 5)
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

            if highlights:
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