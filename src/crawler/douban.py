"""豆瓣读书爬虫"""
import re
from bs4 import BeautifulSoup
from src.crawler.base import BaseCrawler


class DoubanCrawler(BaseCrawler):
    """豆瓣读书爬虫：爬取热门书籍信息和高赞书评"""

    BASE_URL = "https://book.douban.com"
    TOP250_URL = f"{BASE_URL}/top250"

    def crawl_books(self, count: int = 5) -> list[dict]:
        """爬取豆瓣 TOP250 书籍信息"""
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

                    books.append({
                        "title": title,
                        "author": author,
                        "douban_id": douban_id,
                        "cover_url": cover_url,
                        "rating": rating,
                        "summary": quote,
                        "category": self._guess_category(author_info),
                    })
                except Exception:
                    continue

            self._log_crawl("douban", "books", len(books))
        except Exception as e:
            self._log_crawl("douban", "books", 0, "failed", str(e))

        return books

    def crawl_reviews(self, book: dict, count: int = 3) -> list[dict]:
        """爬取单本书的高赞书评"""
        reviews = []
        douban_id = book.get("douban_id")
        if not douban_id:
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
        parts = author_info.split("/")
        return parts[0].strip() if parts else ""

    def _guess_category(self, info: str) -> str:
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
        highlights = []
        quotes = re.findall(r'["""]([^"""]+)[""」]', text)
        highlights.extend(quotes[:5])
        return "\n".join(highlights)