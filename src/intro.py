"""片头生成（复刻原 UP 主三段式片头）

0-1s   入场动画：本期标题卡底图左右两半向中间合拢 + "今天分享的是"大字
1-2.5s 标题卡快闪：3 张其他书的标题卡（意境图 + 书名 + 作者/著）快速切换
2.5s-  定格本期书标题卡
音效   齿轮快闪声（assets/sfx/intro_gears.wav，无则合成 tick 序列）
"""
import subprocess
import time
import requests
from pathlib import Path

from src.config import (
    DASHSCOPE_API_KEY, IMAGE_MODEL, IMAGE_API_URL, FFMPEG_BIN,
    FONT_FILE, ROOT_DIR, CLIPS_DIR, OUTPUT_FPS,
    INTRO_SLIDE_SECONDS, INTRO_FLASH_CARDS, INTRO_FLASH_SECONDS, INTRO_HOLD_SECONDS,
)
from src.assemble import CANVAS_W, CANVAS_H

SFX_DIR = ROOT_DIR / "assets" / "sfx"


def intro_total_seconds(hold_seconds: float = None) -> float:
    return (INTRO_SLIDE_SECONDS + INTRO_FLASH_CARDS * INTRO_FLASH_SECONDS
            + (hold_seconds if hold_seconds is not None else INTRO_HOLD_SECONDS))


def plan_hold_seconds(first_narration_seconds: float, gap: float) -> float:
    """片头句旁白与片头动画同步：定格段拉伸到旁白读完"""
    need = first_narration_seconds + gap - INTRO_SLIDE_SECONDS \
        - INTRO_FLASH_CARDS * INTRO_FLASH_SECONDS
    return round(max(INTRO_HOLD_SECONDS, need), 2)


def generate_intro(script: dict, run_id: str, workdir: Path,
                   hold_seconds: float = None) -> Path:
    """生成片头视频段（含齿轮音效音轨），返回 mp4 路径"""
    hold = hold_seconds if hold_seconds is not None else INTRO_HOLD_SECONDS
    cards = script.get("intro_cards", [])[:INTRO_FLASH_CARDS]
    main_card = {
        "book": script["book"],
        "author": script.get("author", ""),
        "image_prompt": script.get("cover_prompt", script.get("style", "")),
    }

    # 1. 生图（本期 1 张 + 快闪 N 张）
    print("    片头生图...")
    main_img = _gen_image(main_card["image_prompt"], workdir / "card_main.png")
    flash_imgs = []
    for i, card in enumerate(cards):
        img = _gen_image(card["image_prompt"], workdir / f"card_{i}.png")
        flash_imgs.append((img, card))

    # 2. 各片段
    segs = []
    segs.append(_slide_in_segment(main_img, workdir / "seg_slide.mp4"))
    for i, (img, card) in enumerate(flash_imgs):
        segs.append(_card_segment(img, card["book"], card.get("author", ""),
                                  INTRO_FLASH_SECONDS, workdir / f"seg_flash{i}.mp4"))
    segs.append(_card_segment(main_img, main_card["book"], main_card["author"],
                              hold, workdir / "seg_hold.mp4"))

    # 3. 拼接 + 音效
    concat_list = workdir / "intro_concat.txt"
    concat_list.write_text("\n".join(f"file '{s}'" for s in segs) + "\n")
    silent = workdir / "intro_silent.mp4"
    _run([FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0",
          "-i", str(concat_list), "-c", "copy", str(silent)])

    total = intro_total_seconds(hold)
    sfx = _gear_sfx(total, workdir)
    out = CLIPS_DIR / f"{run_id}_intro.mp4"
    _run([FFMPEG_BIN, "-y", "-i", str(silent), "-i", str(sfx),
          "-map", "0:v", "-map", "1:a", "-c:v", "copy",
          "-c:a", "aac", "-shortest", str(out)])
    return out


# ── 图像 ─────────────────────────────────────────────────────────

def _gen_image(prompt: str, out: Path) -> Path:
    """qwen-image 生成竖屏意境图（9:16 生成后裁 3:4）"""
    full_prompt = (
        f"{prompt}。唯美意境插画或摄影，电影感，构图上方留白以便叠加文字，"
        "画面中不要出现任何文字。竖版构图。"
    )
    payload = {
        "model": IMAGE_MODEL,
        "input": {"messages": [{"role": "user", "content": [{"text": full_prompt}]}]},
        "parameters": {"size": "720*1280", "n": 1},
    }
    for attempt in range(5):
        resp = requests.post(
            IMAGE_API_URL,
            headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload, timeout=90,
        )
        if resp.status_code == 200:
            choices = resp.json().get("output", {}).get("choices", [])
            for item in (choices[0].get("message", {}).get("content", []) if choices else []):
                if item.get("image"):
                    raw = out.with_suffix(".raw.png")
                    raw.write_bytes(requests.get(item["image"], timeout=60).content)
                    # 裁切为画布比例并统一尺寸
                    _run([FFMPEG_BIN, "-y", "-i", str(raw),
                          "-vf", f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
                                 f"crop={CANVAS_W}:{CANVAS_H}",
                          "-frames:v", "1", str(out)])
                    time.sleep(2)  # 平滑 QPS，避免下一张被限流
                    return out
            raise RuntimeError(f"生图被拒（可能触发内容审核）: {resp.text[:200]}")
        # 限流/服务端错误退避重试
        time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"片头生图失败: {prompt[:30]}...")


# ── 视频段 ───────────────────────────────────────────────────────

def _slide_in_segment(img: Path, out: Path) -> Path:
    """左右两半向中间合拢 + 顶部'今天分享的是'，时长 INTRO_SLIDE_SECONDS"""
    d = INTRO_SLIDE_SECONDS
    half = CANVAS_W // 2
    # 左半从画面外(-half)滑到 0；右半从 CANVAS_W 滑到 half；slide 用时 60% 后定住
    slide = d * 0.6
    lx = f"min(0,-{half}+{half}*t/{slide})"
    rx = f"max({half},{CANVAS_W}-{half}*t/{slide})"
    title = _escape_drawtext("今天分享的是")
    filter_str = (
        f"[0:v]crop={half}:{CANVAS_H}:0:0[left];"
        f"[0:v]crop={half}:{CANVAS_H}:{half}:0[right];"
        f"color=c=0x101018:s={CANVAS_W}x{CANVAS_H}:d={d}[bg];"
        f"[bg][left]overlay=x='{lx}':y=0[t1];"
        f"[t1][right]overlay=x='{rx}':y=0[t2];"
        f"[t2]drawtext=fontfile='{FONT_FILE}':text='{title}':"
        f"fontsize={int(CANVAS_W * 0.085)}:fontcolor=white:borderw=4:bordercolor=black@0.85:"
        f"x=(w-text_w)/2:y=h*0.16:alpha='min(1,t/{slide})',"
        f"fps={OUTPUT_FPS},format=yuv420p[v]"
    )
    _run([FFMPEG_BIN, "-y", "-loop", "1", "-t", str(d), "-i", str(img),
          "-filter_complex", filter_str, "-map", "[v]",
          "-t", str(d), "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(out)])
    return out


def _card_segment(img: Path, book: str, author: str, seconds: float, out: Path) -> Path:
    """标题卡：意境图 + 《书名》 + 作者/著"""
    book_t = _escape_drawtext(f"《{book}》")
    vf = (
        f"scale={CANVAS_W}:{CANVAS_H},"
        f"drawtext=fontfile='{FONT_FILE}':text='{book_t}':"
        f"fontsize={int(CANVAS_W * 0.078)}:fontcolor=white:borderw=4:bordercolor=black@0.85:"
        f"x=(w-text_w)/2:y=h*0.13"
    )
    if author:
        author_t = _escape_drawtext(f"{author}/著")
        vf += (
            f",drawtext=fontfile='{FONT_FILE}':text='{author_t}':"
            f"fontsize={int(CANVAS_W * 0.042)}:fontcolor=white:borderw=3:bordercolor=black@0.85:"
            f"x=(w-text_w)/2:y=h*0.21"
        )
    vf += f",fps={OUTPUT_FPS},format=yuv420p"
    _run([FFMPEG_BIN, "-y", "-loop", "1", "-t", str(seconds), "-i", str(img),
          "-vf", vf, "-t", str(seconds),
          "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(out)])
    return out


# ── 音效 ─────────────────────────────────────────────────────────

def _gear_sfx(total: float, workdir: Path) -> Path:
    """齿轮快闪声：优先 assets/sfx/intro_gears.wav，否则合成 tick 序列"""
    out = workdir / "intro_sfx.wav"
    custom = sorted(SFX_DIR.glob("intro_gears.*")) if SFX_DIR.exists() else []
    if custom:
        _run([FFMPEG_BIN, "-y", "-i", str(custom[0]),
              "-af", f"apad=whole_dur={total},atrim=0:{total},"
                     f"afade=t=out:st={max(total - 0.4, 0)}:d=0.4",
              str(out)])
        return out
    # 合成: 周期短脉冲模拟齿轮/快门 tick（仅快闪区间密集）
    flash_start = INTRO_SLIDE_SECONDS
    _run([FFMPEG_BIN, "-y",
          "-f", "lavfi", "-t", str(total),
          "-i", "anoisesrc=color=white:amplitude=0.5:seed=7",
          "-af",
          # 8Hz 方波门控白噪声 → 连续 tick；只在 slide+flash 区间出声
          f"apulsator=mode=square:hz=8:width=0.12,"
          f"volume='if(between(t,{flash_start * 0.5},{flash_start + INTRO_FLASH_CARDS * INTRO_FLASH_SECONDS}),0.5,0)':eval=frame,"
          "highpass=f=1800,lowpass=f=6000,"
          f"afade=t=out:st={max(total - 0.4, 0)}:d=0.4",
          str(out)])
    return out


def _escape_drawtext(text: str) -> str:
    return (text.replace("\\", r"\\").replace(":", r"\:")
            .replace("'", r"\'").replace("%", r"\%"))


def _run(cmd: list[str]):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg/intro 失败: {' '.join(cmd[:5])}...\n{result.stderr[-1200:]}")
