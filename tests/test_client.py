"""API 客户端测试"""
import pytest
from pathlib import Path
from src.media.client import QwenClient


class TestQwenClient:
    """QwenClient 测试 — 需要 API 网络可达"""

    @pytest.fixture
    def client(self):
        return QwenClient()

    def test_client_initialization(self, client):
        """客户端初始化"""
        assert client.api_key is not None
        assert "dashscope" in client.base_url

    def test_text_to_image(self, client):
        """生图测试"""
        result = client.text_to_image(
            "一本打开的书，温暖的阳光",
            size="1280*720", n=1
        )
        assert result is not None
        assert result.exists()
        assert result.stat().st_size > 0
        print(f"图片: {result} ({result.stat().st_size/1024:.1f}KB)")

    def test_text_to_speech(self, client):
        """TTS 测试"""
        result = client.text_to_speech(
            "能真正治愈你的，从来不是别人的理解。",
            speed=0.85
        )
        assert result.exists()
        assert result.stat().st_size > 0
        print(f"音频: {result} ({result.stat().st_size/1024:.1f}KB)")