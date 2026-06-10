"""成片拼装：FFmpeg 拼接分镜 + 双语字幕 + 片头标题 + 书名角标 + BGM 混音"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

from src.config import (
    FFMPEG_BIN, FFPROBE_BIN, FONT_NAME, OUTPUT_DIR,
    OUTPUT_FPS, SHOT_GAP_SECONDS, VIDEO_RESOLUTION,
)

# 成片画布固定 1080p（720P 素材上采样，字幕清晰度不受影响）
CANVAS_W, CANVAS_H = 1920, 1080


def assemble(script: dict, shots: list[dict], run_id: str) -> Path:
    """把分镜片段、旁白、字幕合成最终视频。

    shots 每项需含: narration, narration_en, audio_path, audio_seconds, clip_path
    """
    workdir = Path(tempfile.mkdtemp(prefix=f"ai_creator_{run_id}_"))
    try:
        # 每镜头展示时长 = 旁白时长 + 留白
        for shot in shots:
            shot["visual_seconds"] = round(shot["audio_seconds"] + SHOT_GAP_SECONDS, 2)
        total = round(sum(s["visual_seconds"] for s in shots), 2)

        body = _concat_video(shots, workdir)
        audio = _build_audio(shots, total, workdir)
        ass = _build_ass(script, shots, workdir)
        return _final_mux(body, audio, ass, script, total)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ── 视觉流 ───────────────────────────────────────────────────────

def _concat_video(shots: list[dict], workdir: Path) -> Path:
    """每个片段统一规格并裁到精确时长，再无损拼接"""
    segs = []
    for i, shot in enumerate(shots):
        seg = workdir / f"seg_{i}.mp4"
        vf = (
            f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
            f"crop={CANVAS_W}:{CANVAS_H},fps={OUTPUT_FPS},format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration=5"  # 片段略短时用末帧补齐
        )
        _run([
            FFMPEG_BIN, "-y", "-i", str(shot["clip_path"]),
            "-vf", vf, "-t", str(shot["visual_seconds"]),
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            str(seg),
        ])
        segs.append(seg)

    concat_list = workdir / "concat.txt"
    concat_list.write_text("\n".join(f"file '{s}'" for s in segs) + "\n")
    body = workdir / "body.mp4"
    _run([
        FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(body),
    ])
    return body


# ── 音频流 ───────────────────────────────────────────────────────

def _build_audio(shots: list[dict], total: float, workdir: Path) -> Path:
    """旁白轨（主）+ HappyHorse 片段自带环境音（低音量垫底）"""
    narr = _concat_track(
        [(s["audio_path"], s["visual_seconds"]) for s in shots],
        workdir / "narr.wav",
    )
    amb_inputs = [
        (s["clip_path"] if _has_audio(s["clip_path"]) else None, s["visual_seconds"])
        for s in shots
    ]
    amb = _concat_track(amb_inputs, workdir / "amb.wav")

    out = workdir / "audio.wav"
    _run([
        FFMPEG_BIN, "-y", "-i", str(narr), "-i", str(amb),
        "-filter_complex",
        "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[v];"
        "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        "volume=0.22,lowpass=f=6000,"
        f"afade=t=in:d=0.8,afade=t=out:st={max(total - 1.2, 0)}:d=1.2[bg];"
        "[v][bg]amix=inputs=2:duration=first:normalize=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=11[a]",  # 平台标准响度
        "-map", "[a]", "-t", str(total), str(out),
    ])
    return out


def _concat_track(items: list[tuple], out: Path) -> Path:
    """把 (媒体路径|None, 目标秒数) 列表逐段裁齐后串联为单条音轨"""
    cmd = [FFMPEG_BIN, "-y"]
    labels = []
    for path, _ in items:
        if path is not None:
            cmd += ["-i", str(path)]

    filters = []
    idx = 0
    for i, (path, seconds) in enumerate(items):
        if path is None:  # 该片段无音轨，用静音占位
            filters.append(
                f"anullsrc=r=48000:cl=stereo,atrim=0:{seconds}[s{i}];"
            )
        else:
            filters.append(
                f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"atrim=0:{seconds},apad=whole_dur={seconds}[s{i}];"
            )
            idx += 1
        labels.append(f"[s{i}]")

    filter_str = "".join(filters) + "".join(labels) + \
        f"concat=n={len(items)}:v=0:a=1[a]"
    cmd += ["-filter_complex", filter_str, "-map", "[a]", str(out)]
    _run(cmd)
    return out


def _has_audio(path) -> bool:
    result = subprocess.run(
        [FFPROBE_BIN, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return "audio" in result.stdout


# ── 字幕（ASS）───────────────────────────────────────────────────

_ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {CANVAS_W}
PlayResY: {CANVAS_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ZH,{FONT_NAME},62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,2.5,1.5,2,80,80,150,1
Style: EN,{FONT_NAME},34,&H00D8D8D8,&H00D8D8D8,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,1.5,1,2,80,80,95,1
Style: Title,{FONT_NAME},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,6,0,1,3,2,8,60,60,360,1
Style: SubTitle,{FONT_NAME},58,&H00E8E8E8,&H00E8E8E8,&H00000000,&H80000000,0,0,0,0,100,100,4,0,1,2,1.5,8,60,60,500,1
Style: Corner,{FONT_NAME},36,&H00F0F0F0,&H00F0F0F0,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,1.5,1,9,40,48,42,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _build_ass(script: dict, shots: list[dict], workdir: Path) -> Path:
    book = script.get("book", "")
    author = script.get("author", "").split("/")[0].strip()
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

        if i == 0:
            # 片头大字标题（该系列的视觉签名）
            lines.append(_dialogue(start, end, "Title", r"{\fad(400,400)}每天一个顶级文笔"))
            lines.append(_dialogue(start, end, "SubTitle",
                                   r"{\fad(400,400)}—— 《" + _ass_escape(book) + r"》 ——"))
        else:
            # 第二镜起右上角常驻书名角标
            corner = f"《{book}》  {author} 著" if author else f"《{book}》"
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
