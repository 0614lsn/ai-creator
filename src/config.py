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
TTS_MODEL = "qwen3-tts-vc-2026-01-22"   # 声音复刻版 TTS（合成模型须与复刻 target_model 一致）
VIDEO_MODEL = "happyhorse-1.0-t2v"  # 文生视频（动态画面）
IMAGE_MODEL = "qwen-image-2.0-pro"  # 片头标题卡生图
IMAGE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# 多模型评审团（投票打分；调用失败的评委自动跳过）
JUDGE_TEXT_MODELS = ["kimi-k2.6", "qwen3.7-plus", "qwen3.5-omni-plus"]
JUDGE_AV_MODELS = ["qwen3.5-omni-plus", "qwen3-omni-flash"]  # 音/视频理解

# ── 视频生成参数（HappyHorse）────────────────────────────────────
# 720P 0.9 元/秒，1080P 1.6 元/秒
VIDEO_RESOLUTION = os.getenv("VIDEO_RESOLUTION", "1080P")  # 720P / 1080P
VIDEO_RATIO = "3:4"                 # 跟随原 UP 主：竖屏 3:4
CLIP_MIN_SECONDS = 3                # HappyHorse 支持 3-15 秒
CLIP_MAX_SECONDS = 15
VIDEO_PRICE_PER_SECOND = {"720P": 0.9, "1080P": 1.6}

# ── 成片参数 ─────────────────────────────────────────────────────
MAX_TOTAL_SECONDS = 60              # 成片不超过 1 分钟
SHOT_GAP_SECONDS = 1.0              # 每镜头旁白后的留白（慢节奏，回味感）
OUTPUT_FPS = 24
CROSSFADE_SECONDS = 0.5             # 镜头间渐隐转场时长

# ── 片头（复刻原 UP 主：入场动画 + 标题卡快闪 + 齿轮声）─────────
INTRO_SLIDE_SECONDS = 1.0           # 0-1s 左右合拢入场
INTRO_FLASH_CARDS = 3               # 快闪标题卡张数（其他书）
INTRO_FLASH_SECONDS = 0.5           # 每张快闪停留
INTRO_HOLD_SECONDS = 1.2            # 本期书标题卡定格

# ── TTS 参数（克隆自"七页读书吧"旁白，样本经 BS-RoFormer 人声分离）──
TTS_VOICE = os.getenv("TTS_VOICE", "qwen-tts-vc-qiye_v2-voice-20260611014114216-2108")
# 后处理向原声靠拢（实测 UP 主语速 3.8-4.2 字/秒）
TTS_TEMPO = float(os.getenv("TTS_TEMPO", "0.92"))   # rubberband 速率，可试 0.90/0.92/0.94
TTS_PITCH_SHIFT = 0.96              # rubberband 音高倍率（略低沉）
TTS_SAMPLE_RATE = 24000

# ── BGM ──────────────────────────────────────────────────────────
# assets/bgm/ 下的音频文件将被循环垫底（音量自动压低）；为空则成片无 BGM
BGM_DIR = ROOT_DIR / "assets" / "bgm"
BGM_VOLUME = 0.20                   # 实测原片 BGM 比人声低约 12-15dB

# ── FFmpeg / 字体 ────────────────────────────────────────────────
FFMPEG_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
FFPROBE_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"
FONT_NAME = "PingFang SC"           # ASS 字幕用字体名
FONT_FILE = "/System/Library/Fonts/STHeiti Medium.ttc"  # drawtext 用字体文件

# ── 数据路径 ─────────────────────────────────────────────────────
DATA_DIR = ROOT_DIR / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"  # 生成的脚本 JSON
AUDIO_DIR = DATA_DIR / "audio"      # 旁白音频
CLIPS_DIR = DATA_DIR / "clips"      # HappyHorse 视频片段
OUTPUT_DIR = DATA_DIR / "output"    # 最终成片
HISTORY_FILE = DATA_DIR / "history.json"  # 已做过的书，避免重复

for d in [DATA_DIR, SCRIPTS_DIR, AUDIO_DIR, CLIPS_DIR, OUTPUT_DIR, BGM_DIR]:
    d.mkdir(parents=True, exist_ok=True)
