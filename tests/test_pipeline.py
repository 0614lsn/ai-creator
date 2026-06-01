"""集成测试：端到端管线验证"""
import pytest
import sqlite3
from pathlib import Path
from src.config import DB_PATH, DATA_DIR
from src.content.templates import get_template, get_long_reading_structure
from src.video.effects import SubtitleGenerator
from src.review.scorer import VideoScorer


class TestDataPipeline:
    def test_database_tables(self):
        assert DB_PATH.exists()
        conn = sqlite3.connect(str(DB_PATH))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = [t[0] for t in tables]
        for t in ["books", "reviews", "crawl_log", "video_history"]:
            assert t in names, f"Table {t} missing"
        conn.close()

    def test_directories_exist(self):
        for d in ["books", "reviews", "covers", "images", "audio", "output"]:
            assert (DATA_DIR / d).exists(), f"{d} directory missing"


class TestContentTemplates:
    def test_short_template(self):
        t = get_template("short_quote")
        assert t["max_duration"] == 60

    def test_essay_template(self):
        t = get_template("essay_writing")
        assert t["max_duration"] == 70

    def test_structure_routing(self):
        assert get_long_reading_structure("小说")["name"] == "情感沉浸式"
        assert get_long_reading_structure("哲学")["name"] == "主题漫谈式"
        assert get_long_reading_structure("未知")["name"] == "综合式"


class TestSubtitleGeneration:
    def test_srt_format(self):
        script = {"intro": "test intro", "quote": "test quote content"}
        srt = SubtitleGenerator.generate_srt(script, 30.0)
        content = srt.read_text()
        assert "-->" in content
        assert "test" in content.lower()

    def test_time_format(self):
        assert SubtitleGenerator._format_time(65.5) == "00:01:05,500"


class TestVideoScorer:
    def test_parse_score(self):
        s = VideoScorer()
        assert s._parse_score("85") == 85.0
        assert s._parse_score("分数：92分") == 92.0
        assert s._parse_score("") == 50.0

    def test_structure_scoring(self):
        s = VideoScorer()
        script = {"intro": "test", "quote": "test"}
        score = s._score_structure(script, Path("/tmp/nonexistent.mp4"))
        assert 0 <= score <= 100