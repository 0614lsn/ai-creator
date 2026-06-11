"""多模型投票评审：成片质量评估（文案 / 画面 / 声音三维度）

每个维度由多个评委模型独立打分（0-100 + 问题清单），
取有效分的中位数作为该维度得分，问题清单合并去重。

用法:
    python -m src.evaluate data/output/xxx.mp4 [--script data/scripts/xxx.json]
"""
import argparse
import base64
import json
import statistics
import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI

from src.config import (
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, FFMPEG_BIN,
    JUDGE_TEXT_MODELS, JUDGE_AV_MODELS,
)

_client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

_JSON_SPEC = '严格输出 JSON：{"score": 0到100整数, "issues": ["问题1", "问题2"]}，没有问题则 issues 为空数组。'


def evaluate_video(video_path: Path, script: dict = None) -> dict:
    """评审成片，返回 {total, dimensions: {名称: {score, votes, issues}}}"""
    with tempfile.TemporaryDirectory(prefix="eval_") as tmp:
        tmpdir = Path(tmp)
        frames = _extract_frames(video_path, tmpdir)
        audio = _extract_audio(video_path, tmpdir)

        dims = {}
        if script:
            dims["文案"] = _judge_text(script)
        dims["画面"] = _judge_frames(frames)
        dims["声音"] = _judge_audio(audio)

    weights = {"文案": 0.3, "画面": 0.35, "声音": 0.35}
    scored = {k: v for k, v in dims.items() if v["score"] is not None}
    total_w = sum(weights[k] for k in scored)
    total = round(sum(v["score"] * weights[k] for k, v in scored.items()) / total_w) if scored else 0
    return {"total": total, "dimensions": dims}


# ── 三个维度 ─────────────────────────────────────────────────────

def _judge_text(script: dict) -> dict:
    shots = script.get("shots", [])
    narrations = "\n".join(f"{i+1}. {s['narration']}" for i, s in enumerate(shots))
    prompt = f"""你是 B站读书短视频"每天一个顶级文笔"系列的资深审稿人。评审以下《{script.get('book')}》视频文案：

{narrations}

评分维度：金句是否真实可信出自该书/作者、文案感染力、片头收尾结构、口语流畅度。
{_JSON_SPEC}"""
    votes = {}
    for model in JUDGE_TEXT_MODELS:
        votes[model] = _ask_json(model, [{"role": "user", "content": prompt}])
    return _aggregate(votes)


def _judge_frames(frames: list[Path]) -> dict:
    content = [{"type": "text", "text": "以下是一支读书短视频的抽帧（按时间顺序）："}]
    for f in frames:
        b64 = base64.b64encode(f.read_bytes()).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"}})
    content.append({"type": "text", "text":
                    "评审画面：电影质感、风格一致性、竖屏构图合理性、字幕排版清晰度、"
                    "有无穿帮（畸形肢体/乱码文字/水印）。" + _JSON_SPEC})
    votes = {}
    for model in JUDGE_AV_MODELS:
        votes[model] = _ask_json(model, [{"role": "user", "content": content}])
    return _aggregate(votes)


def _judge_audio(audio: Path) -> dict:
    b64 = base64.b64encode(audio.read_bytes()).decode()
    content = [
        {"type": "input_audio", "input_audio": {"data": f"data:;base64,{b64}", "format": "mp3"}},
        {"type": "text", "text":
         "评审这段读书短视频音轨：旁白音色是否深沉治愈不出戏、语速是否舒缓得当、"
         "人声与 BGM 音量平衡、有无杂音或机械感。" + _JSON_SPEC},
    ]
    votes = {}
    for model in JUDGE_AV_MODELS:
        votes[model] = _ask_json(model, [{"role": "user", "content": content}])
    return _aggregate(votes)


# ── 评委调用与聚合 ───────────────────────────────────────────────

def _ask_json(model: str, messages: list) -> dict | None:
    try:
        resp = _client.chat.completions.create(
            model=model, messages=messages, max_tokens=600, temperature=0.2,
        )
        text = resp.choices[0].message.content or ""
        if "```" in text:
            text = text.split("```")[1].removeprefix("json")
        data = json.loads(text.strip())
        score = int(data.get("score"))
        if not 0 <= score <= 100:
            return None
        return {"score": score, "issues": [str(i) for i in data.get("issues", [])]}
    except Exception as e:
        print(f"    评委 {model} 失效，跳过: {str(e)[:80]}")
        return None


def _aggregate(votes: dict) -> dict:
    valid = {m: v for m, v in votes.items() if v}
    if not valid:
        return {"score": None, "votes": {}, "issues": ["所有评委调用失败"]}
    issues = []
    for v in valid.values():
        for issue in v["issues"]:
            if issue not in issues:
                issues.append(issue)
    return {
        "score": round(statistics.median(v["score"] for v in valid.values())),
        "votes": {m: v["score"] for m, v in valid.items()},
        "issues": issues,
    }


# ── 素材抽取 ─────────────────────────────────────────────────────

def _extract_frames(video: Path, tmpdir: Path, n: int = 4) -> list[Path]:
    from src.assemble import get_media_duration
    duration = get_media_duration(video)
    frames = []
    for i in range(n):
        t = duration * (i + 0.5) / n
        f = tmpdir / f"frame_{i}.png"
        subprocess.run([FFMPEG_BIN, "-y", "-v", "error", "-ss", str(t),
                        "-i", str(video), "-vframes", "1", "-vf", "scale=540:-2", str(f)],
                       check=True, capture_output=True)
        frames.append(f)
    return frames


def _extract_audio(video: Path, tmpdir: Path) -> Path:
    out = tmpdir / "audio.mp3"
    subprocess.run([FFMPEG_BIN, "-y", "-v", "error", "-i", str(video),
                    "-t", "45", "-b:a", "96k", str(out)],
                   check=True, capture_output=True)
    return out


def print_report(report: dict):
    print(f"\n  评审总分: {report['total']}/100")
    for name, dim in report["dimensions"].items():
        votes = "  ".join(f"{m.split('-')[0]}={s}" for m, s in dim.get("votes", {}).items())
        print(f"  [{name}] {dim['score']}分  ({votes})")
        for issue in dim.get("issues", [])[:4]:
            print(f"      - {issue}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="成片路径")
    parser.add_argument("--script", help="脚本 JSON 路径（可选，附带文案评审）")
    args = parser.parse_args()
    script = json.loads(Path(args.script).read_text()) if args.script else None
    report = evaluate_video(Path(args.video), script)
    print_report(report)


if __name__ == "__main__":
    main()
