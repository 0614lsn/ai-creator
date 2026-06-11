"""成片拼装：片头 + 分镜渐隐转场 + 双语字幕 + 书名角标 + BGM 混音

时间轴模型（净时长制，与原 UP 主一致）：
  第 1 句旁白（"今天分享的是…"）与片头动画同步，片头净长 I ≥ 该句旁白长。
  正文镜头从第 2 句起，每镜净长 V_i = 旁白时长 + 留白。
  相邻段之间用 xfade 渐隐 D 秒，转场吃掉下一段渲染时多给的 D 秒余量，
  因此字幕/旁白的时间轴始终按净时长累计，不受转场影响。
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

from src.config import (
    FFMPEG_BIN, FFPROBE_BIN, FONT_NAME, OUTPUT_DIR,
    OUTPUT_FPS, SHOT_GAP_SECONDS, VIDEO_RESOLUTION,
    BGM_DIR, BGM_VOLUME, CROSSFADE_SECONDS,
)

# 竖屏 3:4（跟随原 UP 主）
CANVAS_W, CANVAS_H = 1080, 1440


def assemble(script: dict, shots: list[dict], run_id: str,
             intro_path: Path, intro_seconds: float) -> Path:
    """把片头、分镜片段、旁白、字幕合成最终视频。

    shots[0] 为片头句（画面 = intro_path，旁白与片头动画同步）；
    shots[1:] 需含 clip_path（HappyHorse 镜头）。
    """
    workdir = Path(tempfile.mkdtemp(prefix=f"ai_creator_{run_id}_"))
    try:
        shots[0]["visual_seconds"] = round(intro_seconds, 2)
        for shot in shots[1:]:
            shot["visual_seconds"] = round(shot["audio_seconds"] + SHOT_GAP_SECONDS, 2)
        total = round(sum(s["visual_seconds"] for s in shots), 2)

        body = _concat_video(shots, intro_path, workdir)
        audio = _build_audio(shots, intro_path, total, workdir)
        ass = _build_ass(script, shots, workdir)
        return _final_mux(body, audio, ass, script, total)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ── 视觉流（xfade 渐隐链）────────────────────────────────────────

def _concat_video(shots: list[dict], intro_path: Path, workdir: Path) -> Path:
    """每段统一规格，相邻段 xfade 渐隐拼接"""
    D = CROSSFADE_SECONDS
    n = len(shots)

    # 每段渲染长度 = 净长 + D（最后一段不加）；shots[0] 的画面是片头
    segs = []   # (path, net_seconds)
    for i, shot in enumerate(shots):
        src = intro_path if i == 0 else Path(shot["clip_path"])
        render = shot["visual_seconds"] + (D if i < n - 1 else 0)
        seg = workdir / f"seg_{i}.mp4"
        _reencode(src, render, seg, pad_tail=(i == 0))
        segs.append((seg, shot["visual_seconds"]))

    if len(segs) == 1:
        return segs[0][0]

    cmd = [FFMPEG_BIN, "-y"]
    for seg, _ in segs:
        cmd += ["-i", str(seg)]
    filters = []
    offset = 0.0
    prev = "[0:v]"
    for i in range(1, len(segs)):
        offset += segs[i - 1][1]
        label = f"[x{i}]" if i < len(segs) - 1 else "[v]"
        filters.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={D}:offset={offset:.3f}{label}"
        )
        prev = label
    body = workdir / "body.mp4"
    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(body)]
    _run(cmd)
    return body


def _reencode(src: Path, seconds: float, out: Path, pad_tail: bool = False):
    """统一到画布规格并裁/补到指定时长（末帧 clone 补齐）"""
    vf = (
        f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_W}:{CANVAS_H},fps={OUTPUT_FPS},format=yuv420p,"
        f"tpad=stop_mode=clone:stop_duration={8 if pad_tail else 5}"
    )
    _run([FFMPEG_BIN, "-y", "-i", str(src), "-vf", vf, "-t", str(seconds),
          "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(out)])


# ── 音频流（片头音效 + 延迟旁白 + BGM 全程）──────────────────────

def _build_audio(shots: list[dict], intro_path: Path,
                 total: float, workdir: Path) -> Path:
    """旁白轨（片头句从 0 开始） + 片头齿轮音效 + BGM 全程"""
    narr = _concat_track(
        [(s["audio_path"], s["visual_seconds"]) for s in shots],
        workdir / "narr.wav",
    )
    out = workdir / "audio.wav"
    intro_seconds = shots[0]["visual_seconds"]
    bgm = _pick_bgm()

    cmd = [FFMPEG_BIN, "-y", "-i", str(narr)]
    fc = "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[narr];"
    mix_inputs, idx = ["[narr]"], 1

    if intro_path is not None and _has_audio(intro_path):
        cmd += ["-i", str(intro_path)]
        fc += (f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
               f"atrim=0:{intro_seconds},apad=whole_dur={total},volume=0.7[sfx];")
        mix_inputs.append("[sfx]")
        idx += 1

    if bgm is not None:
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
        fc += (f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
               f"volume={BGM_VOLUME},"
               f"afade=t=in:d=1,afade=t=out:st={max(total - 2.0, 0)}:d=2[bg];")
        mix_inputs.append("[bg]")
        idx += 1
    else:
        print("    提示: assets/bgm/ 下无 BGM 文件，成片无背景音乐")

    fc += ("".join(mix_inputs) +
           f"amix=inputs={len(mix_inputs)}:duration=first:normalize=0,"
           "loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    cmd += ["-filter_complex", fc, "-map", "[a]", "-t", str(total), str(out)]
    _run(cmd)
    return out


def _pick_bgm() -> Path | None:
    """取 assets/bgm 下第一个音频文件（按文件名排序）"""
    if not BGM_DIR.exists():
        return None
    for f in sorted(BGM_DIR.iterdir()):
        if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".aac"):
            return f
    return None


def _concat_track(items: list[tuple], out: Path) -> Path:
    """把 (音频路径, 目标秒数) 列表逐段裁齐后串联为单条音轨"""
    cmd = [FFMPEG_BIN, "-y"]
    labels = []
    for path, _ in items:
        cmd += ["-i", str(path)]
    filters = []
    for i, (path, seconds) in enumerate(items):
        filters.append(
            f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"atrim=0:{seconds},apad=whole_dur={seconds}[s{i}];"
        )
        labels.append(f"[s{i}]")
    filter_str = "".join(filters) + "".join(labels) + \
        f"concat=n={len(items)}:v=0:a=1[a]"
    cmd += ["-filter_complex", filter_str, "-map", "[a]", str(out)]
    _run(cmd)
    return out


def _has_audio(path: Path) -> bool:
    result = subprocess.run(
        [FFPROBE_BIN, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return "audio" in result.stdout


# ── 字幕（ASS，竖屏排版）─────────────────────────────────────────

_ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {CANVAS_W}
PlayResY: {CANVAS_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ZH,{FONT_NAME},58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,1.5,0,1,2.5,1.5,2,60,60,300,1
Style: EN,{FONT_NAME},30,&H00D8D8D8,&H00D8D8D8,&H00000000,&H80000000,0,1,0,0,100,100,0.5,0,1,1.5,1,2,60,60,245,1
Style: Corner,{FONT_NAME},30,&H00F0F0F0,&H00F0F0F0,&H00000000,&H80000000,0,0,0,0,100,100,0.5,0,1,1.5,1,9,30,36,34,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _build_ass(script: dict, shots: list[dict], workdir: Path) -> Path:
    book = script.get("book", "")
    author = script.get("author", "").split("/")[0].strip()
    corner = f"《{book}》  {author} 著" if author else f"《{book}》"
    lines = []
    t = 0.0
    for i, shot in enumerate(shots):
        start, end = t, t + shot["visual_seconds"]
        t = end
        zh = _ass_escape(shot["narration"])
        en = _ass_escape(shot.get("narration_en", ""))
        lines.append(_dialogue(start, end, "ZH", r"{\fad(200,200)}" + zh))
        if en:
            lines.append(_dialogue(start, end, "EN", r"{\fad(200,200)}" + en))
        if i > 0:  # 片头画面自带书名大字，不叠角标
            lines.append(_dialogue(start, end, "Corner", _ass_escape(corner)))

    ass = workdir / "subs.ass"
    ass.write_text(_ASS_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    return ass


def _dialogue(start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: 0,{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}"


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("{", "（").replace("}", "）").replace("\n", r"\N")


# ── 终混 ─────────────────────────────────────────────────────────

def _final_mux(body: Path, audio: Path, ass: Path, script: dict, total: float) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    book = re.sub(r'[/\\:*?"<>| ]', "_", script.get("book", "video"))[:30]
    out = OUTPUT_DIR / f"{timestamp}_{book}_{VIDEO_RESOLUTION}.mp4"

    ass_path = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    _run([
        FFMPEG_BIN, "-y", "-i", str(body), "-i", str(audio),
        "-vf", f"ass='{ass_path}'",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(total), "-movflags", "+faststart",
        str(out),
    ])
    return out


def get_media_duration(path: Path) -> float:
    result = subprocess.run(
        [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def _run(cmd: list[str]):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 失败: {' '.join(cmd[:6])}...\n{result.stderr[-1500:]}")
