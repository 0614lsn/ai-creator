#!/usr/bin/env python3
"""AI 读书短视频生产管线（≤60s，复刻"七页读书吧"金句短视频风格）

用法:
    python -m src.pipeline                       # 自动从书单选一本未做过的书
    python -m src.pipeline --book 自渡 --author 墨多先生
    python -m src.pipeline --dry-run             # 只生成脚本+旁白，不花视频生成费
    VIDEO_RESOLUTION=1080P python -m src.pipeline  # 正式出片用 1080P
"""
import argparse
import json
import math
import random
import tempfile
import time
from datetime import datetime
from pathlib import Path

from src import videogen, llm, tts, assemble, intro
from src.config import (
    SCRIPTS_DIR, HISTORY_FILE, CLIP_MIN_SECONDS, CLIP_MAX_SECONDS,
    SHOT_GAP_SECONDS, MAX_TOTAL_SECONDS, VIDEO_RESOLUTION,
    VIDEO_PRICE_PER_SECOND, CROSSFADE_SECONDS,
)

# 内置精选书单（书名, 作者）——文笔向、适合金句短视频
BOOK_LIST = [
    ("自渡", "墨多先生"),
    ("人间失格", "太宰治"),
    ("我与地坛", "史铁生"),
    ("活着", "余华"),
    ("月亮与六便士", "毛姆"),
    ("瓦尔登湖", "梭罗"),
    ("小王子", "圣埃克苏佩里"),
    ("围城", "钱锺书"),
    ("百年孤独", "加西亚·马尔克斯"),
    ("霍乱时期的爱情", "加西亚·马尔克斯"),
    ("平凡的世界", "路遥"),
    ("撒哈拉的故事", "三毛"),
    ("目送", "龙应台"),
    ("皮囊", "蔡崇达"),
    ("被讨厌的勇气", "岸见一郎"),
    ("苏东坡传", "林语堂"),
    ("追风筝的人", "卡勒德·胡赛尼"),
    ("白夜行", "东野圭吾"),
    ("解忧杂货店", "东野圭吾"),
    ("孤独六讲", "蒋勋"),
    ("生死疲劳", "莫言"),
    ("文化苦旅", "余秋雨"),
]


def pick_book() -> tuple[str, str]:
    """从书单选一本近期没做过的"""
    done = set()
    if HISTORY_FILE.exists():
        done = {item["book"] for item in json.loads(HISTORY_FILE.read_text())}
    candidates = [b for b in BOOK_LIST if b[0] not in done] or BOOK_LIST
    return random.choice(candidates)


def record_history(book: str, output: str):
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
    history.append({
        "book": book,
        "output": output,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def plan_clip_seconds(shots: list[dict]):
    """按旁白实测时长决定每镜头的 HappyHorse 生成时长（含转场重叠余量）"""
    for shot in shots:
        need = shot["audio_seconds"] + SHOT_GAP_SECONDS + CROSSFADE_SECONDS + 0.5
        shot["clip_seconds"] = max(CLIP_MIN_SECONDS, min(CLIP_MAX_SECONDS, math.ceil(need)))


def run(book: str = None, author: str = None, hint: str = "",
        dry_run: bool = False, review: bool = True):
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not book:
        book, author = pick_book()
    print(f"[1/6] 选书: 《{book}》 {author or ''}")

    print("[2/6] 生成脚本与分镜 (kimi-k2.6)...")
    script = llm.generate_script(book, author or "", hint)
    shots = script["shots"]
    for i, shot in enumerate(shots):
        print(f"    镜{i + 1}: {shot['narration']}")

    print("[3/6] 合成旁白 (克隆音色 qwen3-tts-vc)...")
    tts.synthesize_shots(shots, run_id)

    # 片头句与片头动画同步；正文镜头从第 2 句起
    hold = intro.plan_hold_seconds(shots[0]["audio_seconds"], SHOT_GAP_SECONDS)
    intro_seconds = intro.intro_total_seconds(hold)
    body_shots = shots[1:]
    plan_clip_seconds(body_shots)
    total_clip = sum(s["clip_seconds"] for s in body_shots)
    total_video = intro_seconds + sum(s["audio_seconds"] + SHOT_GAP_SECONDS for s in body_shots)
    cost = total_clip * VIDEO_PRICE_PER_SECOND[VIDEO_RESOLUTION]
    print(f"    成片预计 {total_video:.0f}s（含片头 {intro_seconds:.1f}s）"
          f"| 需生成素材 {total_clip}s | {VIDEO_RESOLUTION} 预计费用 ¥{cost:.1f}")
    if total_video > MAX_TOTAL_SECONDS:
        raise RuntimeError(f"成片超过 {MAX_TOTAL_SECONDS}s 上限，请重新生成脚本")

    script_path = SCRIPTS_DIR / f"{run_id}_{book}.json"
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2))
    print(f"    脚本已保存: {script_path}")

    if dry_run:
        print("[dry-run] 跳过视频生成与拼装")
        return None

    print(f"[4/6] 生成动态画面 (happyhorse-1.0-t2v, {VIDEO_RESOLUTION})...")
    t0 = time.time()
    clip_paths = videogen.generate_clips(body_shots, run_id)
    for shot, path in zip(body_shots, clip_paths):
        shot["clip_path"] = str(path)
    print(f"    画面生成耗时 {time.time() - t0:.0f}s")
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2))

    print("[5/6] 生成片头（入场动画 + 标题卡快闪）...")
    with tempfile.TemporaryDirectory(prefix="intro_") as tmp:
        intro_path = intro.generate_intro(script, run_id, Path(tmp), hold_seconds=hold)

        print("[6/6] FFmpeg 拼装成片...")
        output = assemble.assemble(script, shots, run_id,
                                   intro_path=intro_path,
                                   intro_seconds=intro_seconds)
    record_history(book, str(output))
    duration = assemble.get_media_duration(output)
    print(f"\n完成: {output}  ({duration:.1f}s)")

    if review:
        print("[评审] 多模型投票打分...")
        from src import evaluate
        report = evaluate.evaluate_video(output, script)
        evaluate.print_report(report)
    return output


def main():
    parser = argparse.ArgumentParser(description="AI 读书短视频生产管线")
    parser.add_argument("--book", help="书名（不传则自动从书单选）")
    parser.add_argument("--author", default="", help="作者")
    parser.add_argument("--hint", default="", help="优先使用的金句素材")
    parser.add_argument("--from-up", metavar="书名",
                        help="用 data/up_transcripts.json 里 UP 主同名视频的转写文本作素材")
    parser.add_argument("--dry-run", action="store_true",
                        help="只生成脚本+旁白，不调用视频生成（不花钱）")
    parser.add_argument("--no-review", action="store_true", help="跳过多模型评审")
    args = parser.parse_args()

    book, author, hint = args.book, args.author, args.hint
    if args.from_up:
        bank = json.loads((SCRIPTS_DIR.parent / "up_transcripts.json").read_text())
        match = next((v for v in bank.values() if v.get("book") == args.from_up), None)
        if not match:
            raise SystemExit(f"up_transcripts.json 中没有《{args.from_up}》，"
                             f"现有: {[v.get('book') for v in bank.values()]}")
        book = match["book"]
        author = author or match.get("author", "")
        hint = f"UP 主原视频旁白全文（请参考其选句与结构，但用你自己的话重组）：\n{match['transcript']}"
    run(book, author, hint, args.dry_run, review=not args.no_review)


if __name__ == "__main__":
    main()
