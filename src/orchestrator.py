#!/usr/bin/env python3
"""总控编排器：串联全部步骤，支持命令行子命令"""
import sys
import subprocess
import sqlite3
import time
from pathlib import Path
from datetime import datetime

from src.config import DB_PATH, OUTPUT_DIR, COVERS_DIR
from src.crawler.scheduler import CrawlScheduler
from src.content.selector import BookSelector
from src.content.polisher import ScriptPolisher
from src.media.client import QwenClient
from src.video.composer import VideoComposer
from src.review.scorer import VideoScorer
from src.scheduler.cron import AlertManager, CronManager


class Orchestrator:
    def __init__(self):
        self.crawler = CrawlScheduler()
        self.qwen = QwenClient()
        self.composer = VideoComposer()
        self.scorer = VideoScorer()

    def crawl(self):
        try:
            count = self.crawler.daily_crawl()
            print(f"[{datetime.now()}] 爬虫完成: {count} 本书")
        except Exception as e:
            AlertManager.send_alert("爬虫失败", str(e))
            raise

    def generate_short(self):
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
                    script = polisher.polish_short_quote(book)
                    image_prompts = script.get("image_prompts", [f"书籍《{book['title']}》配图，文艺风格，暖色调"])
                    images = []
                    for prompt in image_prompts[:10]:
                        img_path = self.qwen.text_to_image(prompt, size="1280*720")
                        if img_path:
                            images.append(img_path)
                    text = script.get("intro", "") + "。" + script.get("quote", "")
                    audio_path = self.qwen.text_to_speech(text, speed=0.90, emotion="warm")
                    cover_path = self._get_cover(book)
                    # 生成 BGM
                    bgm_path = self._generate_bgm(audio_path)
                    video_path = self.composer.compose(
                        images=images, audio_path=audio_path, script=script,
                        book_cover=cover_path, book_title=book["title"], book_author=book["author"],
                        bgm_path=bgm_path,
                    )
                    self._save_candidate(book, video_path, "short_quote")
                except Exception as e:
                    print(f"  候选 {i+1} 失败: {e}")
            selector.close()
        except Exception as e:
            AlertManager.send_alert("短视频生成失败", str(e))

    def generate_long(self):
        selector = BookSelector()
        polisher = ScriptPolisher()
        try:
            books = selector.select_books(2, "long_reading")
            if not books:
                AlertManager.send_alert("选书失败", "无可用书籍")
                return
            book = books[0]
            print(f"[{datetime.now()}] 生成长视频: {book['title']}")
            script = polisher.polish_long_reading(book)
            image_prompts = [s.get("image_prompt", f"书籍《{book['title']}》配图") for s in script.get("sections", [])]
            images = []
            for prompt in image_prompts[:80]:
                img_path = self.qwen.text_to_image(prompt, size="1280*720")
                if img_path:
                    images.append(img_path)
            full_text = ""
            for section in script.get("sections", []):
                full_text += section.get("heading", "") + "。" + section.get("content", "") + "\n"
            full_text += script.get("closing", "")
            audio_path = self.qwen.text_to_speech(full_text, speed=0.75)
            cover_path = self._get_cover(book)
            video_path = self.composer.compose(
                images=images, audio_path=audio_path, script=script,
                book_cover=cover_path, book_title=book["title"], book_author=book["author"],
            )
            self._save_candidate(book, video_path, "long_reading")
            selector.close()
        except Exception as e:
            AlertManager.send_alert("长视频生成失败", str(e))

    def review(self, video_type: str = "short_quote"):
        conn = sqlite3.connect(str(DB_PATH))
        today = datetime.now().strftime("%Y-%m-%d")
        candidates = conn.execute(
            """SELECT vh.id, vh.video_path, vh.book_id, b.title
               FROM video_history vh JOIN books b ON vh.book_id = b.id
               WHERE DATE(vh.created_at) = ? AND vh.video_type = ?""",
            (today, video_type)
        ).fetchall()

        if not candidates:
            print(f"[{datetime.now()}] 今日无{video_type}候选视频")
            conn.close()
            return

        best = None
        best_score = 0
        for cand in candidates:
            video_path = Path(cand[1])
            if not video_path.exists():
                continue
            scores = self.scorer.score(video_path, {}, [])
            total = scores["total"]
            print(f"  {cand[3]}: {total}分 ({scores['grade']})")
            conn.execute("UPDATE video_history SET score = ? WHERE id = ?", (total, cand[0]))
            if total > best_score:
                best_score = total
                best = cand

        if best:
            grade = "publish" if best_score >= 80 else "review"
            print(f"最优: {best[3]} ({best_score}分, {grade})")
            if best_score < 60:
                AlertManager.send_alert("视频质量不达标", f"最佳候选 {best[3]} 得分 {best_score}，已丢弃")

        conn.commit()
        conn.close()

    def _generate_bgm(self, audio_path: Path) -> Path:
        """生成环境背景音乐"""
        from src.config import FFMPEG_BIN, AUDIO_DIR
        duration = VideoComposer._get_audio_duration(audio_path)
        bgm_path = AUDIO_DIR / f"bgm_{int(time.time())}.wav"

        cmd = [FFMPEG_BIN, "-y",
               "-f", "lavfi", "-i", f"sine=frequency=110:duration={duration + 5}",
               "-f", "lavfi", "-i", f"sine=frequency=165:duration={duration + 5}",
               "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration + 5}",
               "-filter_complex",
               "[0:a][1:a][2:a]amix=inputs=3:duration=first:weights=0.4 0.3 0.3,volume=0.06,lowpass=f=400,aecho=0.8:0.7:40:0.3[a]",
               "-map", "[a]", "-t", str(duration + 5), str(bgm_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return bgm_path

    def _get_cover(self, book: dict) -> Path:
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

    def _save_candidate(self, book: dict, video_path: Path, video_type: str):
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