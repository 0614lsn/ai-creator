"""多模态 API 统一客户端"""
import base64
import time
import requests
from pathlib import Path
from typing import Optional
from openai import OpenAI
from src.config import (
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL,
    TEXT_MODEL, IMAGE_MODEL, TTS_MODEL, VISION_MODEL,
    IMAGE_API_URL, IMAGES_DIR, AUDIO_DIR,
)


class BaseClient:
    """API 客户端基类，封装重试、超时"""
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.max_retries = 3
        self.retry_delay = 2

    def chat(self, model: str, messages: list, max_tokens: int = 2048,
             temperature: float = 0.7, **kwargs) -> str:
        """文本对话，带自动重试"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay * (2 ** attempt))
        return ""


class QwenClient(BaseClient):
    """千问系列模型客户端 (DashScope)"""

    def __init__(self):
        super().__init__(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

    def text_to_image(self, prompt: str, size: str = "1280*720",
                      n: int = 1, model: str = None) -> Optional[Path]:
        """AI 生图 — 使用原生 DashScope HTTP API（非 OpenAI 兼容接口）

        Returns: 本地文件路径
        """
        if model is None:
            model = IMAGE_MODEL

        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ]
            },
            "parameters": {"size": size, "n": n}
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    IMAGE_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # 解析 output.choices[0].message.content[0].image
                    choices = data.get("output", {}).get("choices", [])
                    if choices:
                        content_list = choices[0].get("message", {}).get("content", [])
                        for item in content_list:
                            url = item.get("image", "")
                            if url:
                                img_data = requests.get(url).content
                                filename = f"img_{int(time.time())}_{hash(prompt) % 10000}.png"
                                filepath = IMAGES_DIR / filename
                                filepath.write_bytes(img_data)
                                return filepath
                elif resp.status_code in (429, 500, 502, 503):
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                else:
                    if attempt == self.max_retries - 1:
                        print(f"Image API error: {resp.status_code} {resp.text[:200]}")
                    break
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay * (2 ** attempt))
        return None

    def text_to_speech(self, text: str, voice: str = "Ethan",
                       speed: float = 0.90, output_path: Optional[Path] = None,
                       emotion: str = "warm") -> Path:
        """TTS 语音合成 — qwen3.5-omni-plus

        Args:
            text: 要朗读的纯文本（不包含任何指令）
            voice: 音色 (Ethan=男声)
            speed: 语速倍率 (0.9=稍慢有感情, 1.0=正常)
            emotion: 情感风格 (warm/sad/gentle/calm)
        Returns: 音频文件路径
        """
        import numpy as np
        import soundfile as sf

        if output_path is None:
            output_path = AUDIO_DIR / f"tts_{int(time.time())}.wav"

        emotion_guide = {
            "warm": "声音温暖而有磁性，像深夜电台主播，娓娓道来，在关键词语上略微加重语气，句尾有自然停顿",
            "sad": "声音低沉略带忧伤，像在分享一个令人感慨的故事，节奏缓慢，情感克制但深刻",
            "gentle": "声音轻柔温和，像是在耳边低声诉说，给人安全感和治愈感",
            "calm": "声音平静沉稳，像冥想引导，节奏均匀，不带强烈情绪起伏",
        }
        style = emotion_guide.get(emotion, emotion_guide["warm"])

        completion = self.client.chat.completions.create(
            model=TTS_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"你是专业配音演员。{style}。语速 {speed}x。不要读任何指令和标点说明，只朗读文本内容。不要输出任何解释或提示文字。"
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": text}],
                },
            ],
            modalities=["text", "audio"],
            audio={"voice": voice, "format": "wav"},
            stream=True,
            stream_options={"include_usage": True},
            max_tokens=8192,
        )

        audio_base64 = ""
        for chunk in completion:
            if chunk.choices and hasattr(chunk.choices[0].delta, "audio"):
                audio_data = chunk.choices[0].delta.audio
                if audio_data and "data" in audio_data:
                    audio_base64 += audio_data["data"]

        if audio_base64:
            wav_bytes = base64.b64decode(audio_base64)
            audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
            sf.write(str(output_path), audio_np, samplerate=24000)
        return output_path

    def analyze_image(self, image_path: Path, prompt: str) -> str:
        """视觉理解：分析图片内容"""
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""