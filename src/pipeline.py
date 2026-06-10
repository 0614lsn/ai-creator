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
import time
from datetime import datetime

from src import videogen, llm, tts, assemble
from src.config import (
    SCRIPTS_DIR, HISTORY_FILE, CLIP_MIN_SECONDS, CLIP_MAX_SECONDS,
    SHOT_GAP_SECONDS, MAX_TOTAL_SECONDS, VIDEO_RESOLUTION,
    VIDEO_PRICE_PER_SECOND,
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
    """按旁白实测时长决定每镜头的 HappyHorse 生成时长"""
    for shot in shots:
        need = shot["audio_seconds"] + SHOT_GAP_SECONDS + 0.5  # 0.5s 裁剪余量
        shot["clip_seconds"] = max(CLIP_MIN_SECONDS, min(CLIP_MAX_SECONDS, math.ceil(need)))


def run(book: str = None, author: str = None, hint: str = "", dry_run: bool = False):
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not book:
        book, author = pick_book()
    print(f"[1/5] 选书: 《{book}》 {author or ''}")

    print("[2/5] 生成脚本与分镜 (kimi-k2.6)...")
    script = llm.generate_script(book, author or "", hint)
    shots = script["shots"]
    for i, shot in enumerate(shots):
        print(f"    镜{i + 1}: {shot['narration']}")

    print("[3/5] 合成旁白 (qwen3.5-omni-plus)...")
    tts.synthesize_shots(shots, run_id)

    plan_clip_seconds(shots)
    total_clip = sum(s["clip_seconds"] for s in shots)
    total_video = sum(s["audio_seconds"] + SHOT_GAP_SECONDS for s in shots)
    cost = total_clip * VIDEO_PRICE_PER_SECOND[VIDEO_RESOLUTION]
    print(f"    成片预计 {total_video:.0f}s | 需生成素材 {total_clip}s "
          f"| {VIDEO_RESOLUTION} 预计费用 ¥{cost:.1f}")
    if total_video > MAX_TOTAL_SECONDS:
        raise RuntimeError(f"成片超过 {MAX_TOTAL_SECONDS}s 上限，请重新生成脚本")

    script_path = SCRIPTS_DIR / f"{run_id}_{book}.json"
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2))
    print(f"    脚本已保存: {script_path}")

    if dry_run:
        print("[dry-run] 跳过视频生成与拼装")
        return None

    print(f"[4/5] 生成动态画面 (happyhorse-1.0-t2v, {VIDEO_RESOLUTION})...")
    t0 = time.time()
    clip_paths = videogen.generate_clips(shots, run_id)
    for shot, path in zip(shots, clip_paths):
        shot["clip_path"] = str(path)
    print(f"    画面生成耗时 {time.time() - t0:.0f}s")
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2))

    print("[5/5] FFmpeg 拼装成片...")
    output = assemble.assemble(script, shots, run_id)
    record_history(book, str(output))
    duration = assemble.get_media_duration(output)
    print(f"\n完成: {output}  ({duration:.1f}s)")
    return output


def main():
    parser = argparse.ArgumentParser(description="AI 读书短视频生产管线")
    parser.add_argument("--book", help="书名（不传则自动从书单选）")
    parser.add_argument("--author", default="", help="作者")
    parser.add_argument("--hint", default="", help="优先使用的金句素材")
    parser.add_argument("--dry-run", action="store_true",
                        help="只生成脚本+旁白，不调用视频生成（不花钱）")
    args = parser.parse_args()
    run(args.book, args.author, args.hint, args.dry_run)


if __name__ == "__main__":
    main()
