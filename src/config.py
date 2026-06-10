"""全局配置：AI 读书短视频生产管线"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent

# ── DashScope（阿里云百炼，所有模型走同一个 key）──────────────────
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY 未设置，请写入 .env 或导出环境变量")

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
VIDEO_SYNTHESIS_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
TASK_QUERY_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

# ── 模型 ─────────────────────────────────────────────────────────
TEXT_MODEL = "kimi-k2.6"            # 脚本/分镜生成
TTS_MODEL = "qwen3.5-omni-plus"     # 旁白语音合成
VIDEO_MODEL = "happyhorse-1.0-t2v"  # 文生视频（动态画面）

# ── 视频生成参数（HappyHorse）────────────────────────────────────
# 720P 0.9 元/秒，1080P 1.6 元/秒；测试期默认 720P 控制成本
VIDEO_RESOLUTION = os.getenv("VIDEO_RESOLUTION", "720P")   # 720P / 1080P
VIDEO_RATIO = "16:9"                # B站横屏
CLIP_MIN_SECONDS = 3                # HappyHorse 支持 3-15 秒
CLIP_MAX_SECONDS = 15
VIDEO_PRICE_PER_SECOND = {"720P": 0.9, "1080P": 1.6}

# ── 成片参数 ─────────────────────────────────────────────────────
MAX_TOTAL_SECONDS = 60              # 成片不超过 1 分钟
SHOT_GAP_SECONDS = 1.0              # 每镜头旁白后的留白（慢节奏，回味感）
OUTPUT_FPS = 24

# ── TTS 参数 ─────────────────────────────────────────────────────
TTS_VOICE = "Ethan"                 # 温暖沉稳男声
TTS_SPEED = 0.9                     # 慢语速，娓娓道来

# ── FFmpeg / 字体 ────────────────────────────────────────────────
FFMPEG_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
FFPROBE_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"
FONT_NAME = "PingFang SC"           # ASS 字幕用字体名

# ── 数据路径 ─────────────────────────────────────────────────────
DATA_DIR = ROOT_DIR / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"  # 生成的脚本 JSON
AUDIO_DIR = DATA_DIR / "audio"      # 旁白音频
CLIPS_DIR = DATA_DIR / "clips"      # HappyHorse 视频片段
OUTPUT_DIR = DATA_DIR / "output"    # 最终成片
HISTORY_FILE = DATA_DIR / "history.json"  # 已做过的书，避免重复

for d in [DATA_DIR, SCRIPTS_DIR, AUDIO_DIR, CLIPS_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)
