"""旁白合成：克隆音色（复刻自 UP 主旁白）+ 后处理调音

链路: qwen3-tts-vc 合成 → rubberband 降速/降调 + 暖色 EQ → 修剪首尾静音
克隆音色用 scripts/clone_voice.py 重新创建。
"""
import subprocess
import tempfile
import numpy as np
import requests
import soundfile as sf
from pathlib import Path

from src.config import (
    DASHSCOPE_API_KEY, TTS_MODEL, TTS_VOICE,
    TTS_TEMPO, TTS_PITCH_SHIFT, TTS_SAMPLE_RATE,
    FFMPEG_BIN, AUDIO_DIR,
)

_SYNTH_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"


def synthesize_sentence(text: str, out_path: Path) -> tuple[Path, float]:
    """合成单句旁白（克隆音色），返回 (路径, 时长秒)"""
    resp = requests.post(
        _SYNTH_URL,
        headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": TTS_MODEL, "input": {"text": text, "voice": TTS_VOICE}},
        timeout=120,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise RuntimeError(f"TTS 失败: {resp.status_code} {data}")
    audio_url = data["output"]["audio"]["url"]

    with tempfile.NamedTemporaryFile(suffix=".wav") as raw:
        raw.write(requests.get(audio_url, timeout=60).content)
        raw.flush()
        # 向原 UP 主声音靠拢：降速 + 微降调 + 低频增暖/高频去亮
        tuned = _postprocess(Path(raw.name), out_path)
    return tuned


def synthesize_shots(shots: list[dict], run_id: str) -> list[dict]:
    """为每个分镜合成旁白，往 shot 里写入 audio_path / audio_seconds"""
    for i, shot in enumerate(shots):
        out_path = AUDIO_DIR / f"{run_id}_shot{i + 1}.wav"
        _, duration = synthesize_sentence(shot["narration"], out_path)
        shot["audio_path"] = str(out_path)
        shot["audio_seconds"] = round(duration, 2)
        print(f"    [{i + 1}/{len(shots)}] {duration:.1f}s | {shot['narration'][:24]}...")
    return shots


def _postprocess(raw: Path, out_path: Path) -> tuple[Path, float]:
    with tempfile.NamedTemporaryFile(suffix=".wav") as tuned:
        subprocess.run(
            [FFMPEG_BIN, "-y", "-v", "error", "-i", str(raw),
             "-af",
             f"rubberband=pitch={TTS_PITCH_SHIFT}:tempo={TTS_TEMPO},"
             "bass=g=2.5:f=160,treble=g=-2:f=4000,"
             f"aformat=sample_rates={TTS_SAMPLE_RATE}:channel_layouts=mono",
             str(tuned.name)],
            check=True, capture_output=True,
        )
        audio, sr = sf.read(tuned.name, dtype="int16")
    audio = _trim_silence(audio)
    sf.write(str(out_path), audio, samplerate=sr)
    return out_path, len(audio) / sr


def _trim_silence(audio: np.ndarray, threshold_ratio: float = 0.01) -> np.ndarray:
    threshold = int(32767 * threshold_ratio)
    mask = np.abs(audio) > threshold
    if not mask.any():
        return audio
    start, end = mask.argmax(), len(mask) - mask[::-1].argmax()
    # 句首留 0.1s、句尾留 0.25s 自然气口
    start = max(0, start - int(0.1 * TTS_SAMPLE_RATE))
    end = min(len(audio), end + int(0.25 * TTS_SAMPLE_RATE))
    return audio[start:end]
