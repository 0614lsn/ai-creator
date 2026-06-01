"""全局配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent

# API 配置 — 全部走 DashScope
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY not set. Add it to .env file or export as environment variable.")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 模型配置
TEXT_MODEL = "kimi-k2.6"              # 文案润色 + 质量评估（通过 DashScope）
IMAGE_MODEL = "wan2.6-t2i"            # AI 生图（原生 DashScope API）
TTS_MODEL = "qwen3.5-omni-plus"       # 语音合成
VISION_MODEL = "qwen3.5-omni-plus"    # 视觉理解

# 生图 API（注意：不能用 OpenAI 兼容接口，需原生 API）
IMAGE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# TTS 参数
TTS_VOICE = "Tina"
TTS_SPEED_SHORT = 0.85
TTS_SPEED_LONG = 0.75
TTS_PITCH = -2

# 视频参数
VIDEO_RESOLUTION = (1920, 1080)
VIDEO_FPS = 24
IMAGE_DISPLAY_SECONDS = 5
SUBTITLE_FONT_SIZE = 48
SUBTITLE_FONT_COLOR = "white"

# 去重窗口（天）
BOOK_REUSE_DAYS = 30

# 数据路径
DATA_DIR = ROOT_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"
REVIEWS_DIR = DATA_DIR / "reviews"
COVERS_DIR = DATA_DIR / "covers"
IMAGES_DIR = DATA_DIR / "images"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "output"

# 数据库
DB_PATH = DATA_DIR / "books.db"

# 邮件告警
ALERT_EMAIL = "luilsn0501@gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# 确保目录存在
for d in [DATA_DIR, BOOKS_DIR, REVIEWS_DIR, COVERS_DIR, IMAGES_DIR, AUDIO_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)