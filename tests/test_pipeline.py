"""管线纯逻辑单元测试（不调用任何付费 API）"""
import json
import pytest

from src.llm import _parse_json, _validate
from src.pipeline import plan_clip_seconds
from src.assemble import _ts, _ass_escape, _build_ass
from src.config import CLIP_MIN_SECONDS, CLIP_MAX_SECONDS


# ── llm ──────────────────────────────────────────────────────────

def test_parse_json_with_fence():
    text = '```json\n{"title": "t", "shots": []}\n```'
    assert _parse_json(text) == {"title": "t", "shots": []}


def test_parse_json_plain():
    assert _parse_json('{"a": 1}') == {"a": 1}
    assert _parse_json("not json") is None


def _make_script(n_shots: int, narration: str = "这是一句正常长度的旁白文案"):
    return {
        "shots": [
            {"narration": narration, "narration_en": "en", "video_prompt": "p"}
            for _ in range(n_shots)
        ]
    }


def test_validate_accepts_normal_script():
    assert _validate(_make_script(5))


def test_validate_rejects_bad_shot_count():
    assert not _validate(_make_script(2))
    assert not _validate(_make_script(9))


def test_validate_rejects_overlong_narration():
    assert not _validate(_make_script(5, narration="超" * 50))


# ── pipeline ─────────────────────────────────────────────────────

def test_plan_clip_seconds_clamps_to_model_range():
    shots = [
        {"audio_seconds": 0.5},   # 过短 → 提到下限
        {"audio_seconds": 5.0},   # 正常 → 向上取整留余量
        {"audio_seconds": 30.0},  # 过长 → 压到上限
    ]
    plan_clip_seconds(shots)
    assert shots[0]["clip_seconds"] == CLIP_MIN_SECONDS
    assert shots[1]["clip_seconds"] >= 6
    assert shots[2]["clip_seconds"] == CLIP_MAX_SECONDS


# ── assemble ─────────────────────────────────────────────────────

def test_ass_timestamp_format():
    assert _ts(0) == "0:00:00.00"
    assert _ts(65.5) == "0:01:05.50"
    assert _ts(3661.25) == "1:01:01.25"


def test_ass_escape_replaces_braces():
    assert "{" not in _ass_escape("a{b}c")
    assert _ass_escape("一\n二") == r"一\N二"


def test_build_ass_contains_title_and_corner(tmp_path):
    script = {"book": "自渡", "author": "墨多先生"}
    shots = [
        {"narration": "片头句", "narration_en": "intro", "visual_seconds": 5.0},
        {"narration": "金句", "narration_en": "quote", "visual_seconds": 4.0},
    ]
    ass = _build_ass(script, shots, tmp_path)
    content = ass.read_text(encoding="utf-8")
    assert "每天一个顶级文笔" in content       # 片头大字
    assert "《自渡》  墨多先生 著" in content   # 第二镜起角标
    # 镜1: ZH+EN+Title+SubTitle = 4 条；镜2: ZH+EN+Corner = 3 条
    assert content.count("Dialogue:") == 7
