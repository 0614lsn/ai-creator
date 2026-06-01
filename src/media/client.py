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

    def text_to_speech(self, text: str, voice: str = "Tina",
                       speed: float = 0.85, output_path: Optional[Path] = None) -> Path:
        """TTS 语音合成 — 使用 qwen3.5-omni-plus 的 audio 输出

        Returns: 音频文件路径
        """
        import numpy as np
        import soundfile as sf

        if output_path is None:
            output_path = AUDIO_DIR / f"tts_{int(time.time())}.wav"

        completion = self.client.chat.completions.create(
            model=TTS_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"请用自然的语气朗读以下文字，语速{speed}x：\n{text}"}
                ],
            }],
            modalities=["text", "audio"],
            audio={"voice": voice, "format": "wav"},
            stream=True,
            stream_options={"include_usage": True},
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