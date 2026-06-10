"""旁白合成：qwen3.5-omni-plus 逐句 TTS，返回音频路径 + 精确时长"""
import base64
import numpy as np
import soundfile as sf
from pathlib import Path
from openai import OpenAI

from src.config import (
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL,
    TTS_MODEL, TTS_VOICE, TTS_SPEED, AUDIO_DIR,
)

_client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

_STYLE = (
    "声音温暖而有磁性，像深夜电台主播，娓娓道来，"
    "在关键词语上略微加重语气，句尾有自然停顿，克制但有感染力"
)
_SAMPLE_RATE = 24000


def synthesize_sentence(text: str, out_path: Path) -> tuple[Path, float]:
    """合成单句旁白，返回 (路径, 时长秒)"""
    completion = _client.chat.completions.create(
        model=TTS_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    f"你是专业配音演员。{_STYLE}。语速 {TTS_SPEED}x。"
                    "只朗读文本内容，不要读任何指令和标点说明，"
                    "不要输出任何解释或提示文字。"
                ),
            },
            {"role": "user", "content": [{"type": "text", "text": text}]},
        ],
        modalities=["text", "audio"],
        audio={"voice": TTS_VOICE, "format": "wav"},
        stream=True,
        stream_options={"include_usage": True},
        max_tokens=8192,
    )

    audio_b64 = ""
    for chunk in completion:
        if chunk.choices and hasattr(chunk.choices[0].delta, "audio"):
            audio_data = chunk.choices[0].delta.audio
            if audio_data and "data" in audio_data:
                audio_b64 += audio_data["data"]

    if not audio_b64:
        raise RuntimeError(f"TTS 未返回音频: {text[:20]}...")

    wav_bytes = base64.b64decode(audio_b64)
    audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
    # 修剪首尾静音（阈值 1% 满幅）
    audio_np = _trim_silence(audio_np)
    sf.write(str(out_path), audio_np, samplerate=_SAMPLE_RATE)
    duration = len(audio_np) / _SAMPLE_RATE
    return out_path, duration


def synthesize_shots(shots: list[dict], run_id: str) -> list[dict]:
    """为每个分镜合成旁白，往 shot 里写入 audio_path / audio_seconds"""
    for i, shot in enumerate(shots):
        out_path = AUDIO_DIR / f"{run_id}_shot{i + 1}.wav"
        _, duration = synthesize_sentence(shot["narration"], out_path)
        shot["audio_path"] = str(out_path)
        shot["audio_seconds"] = round(duration, 2)
        print(f"    [{i + 1}/{len(shots)}] {duration:.1f}s | {shot['narration'][:24]}...")
    return shots


def _trim_silence(audio: np.ndarray, threshold_ratio: float = 0.01) -> np.ndarray:
    threshold = int(32767 * threshold_ratio)
    mask = np.abs(audio) > threshold
    if not mask.any():
        return audio
    start, end = mask.argmax(), len(mask) - mask[::-1].argmax()
    # 句首留 0.1s、句尾留 0.25s 自然气口
    start = max(0, start - int(0.1 * _SAMPLE_RATE))
    end = min(len(audio), end + int(0.25 * _SAMPLE_RATE))
    return audio[start:end]
