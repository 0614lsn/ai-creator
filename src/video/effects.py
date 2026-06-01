"""视频特效：中英双语字幕生成 + ffmpeg 滤镜"""
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


class SubtitleGenerator:
    """中英双语字幕生成器"""

    @staticmethod
    def generate_srt(script: dict, audio_duration: float) -> Path:
        srt_path = Path("/tmp/subtitle.srt")
        text = SubtitleGenerator._extract_text(script)
        sentences = SubtitleGenerator._split_sentences(text)
        total_chars = sum(len(s) for s in sentences)
        total_duration = max(audio_duration - 2, 1)

        entries = []
        current_time = 1.0

        for i, sentence in enumerate(sentences):
            char_ratio = len(sentence) / max(total_chars, 1)
            duration = max(1.5, char_ratio * total_duration)
            start = current_time
            end = current_time + duration
            current_time = end

            entries.append(
                f"{i+1}\n"
                f"{SubtitleGenerator._format_time(start)} --> {SubtitleGenerator._format_time(end)}\n"
                f"{sentence}\n"
            )

        srt_path.write_text("\n".join(entries), encoding="utf-8")
        return srt_path

    @staticmethod
    def _extract_text(script: dict) -> str:
        parts = []
        if "intro" in script:
            parts.append(script["intro"])
        if "quote" in script:
            parts.append(script["quote"])
        if "sections" in script:
            for section in script["sections"]:
                if "heading" in section:
                    parts.append(section["heading"])
                if "content" in section:
                    parts.append(section["content"])
        if "closing" in script:
            parts.append(script["closing"])
        if "angles" in script:
            for angle in script["angles"]:
                if "name" in angle:
                    parts.append(angle["name"])
                if "example" in angle:
                    parts.append(angle["example"])
        if "summary" in script:
            parts.append(script["summary"])
        return "\n".join(parts)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        sentences = re.split(r'[。！？\n]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 2]

    @staticmethod
    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class FFmpegEffects:
    """FFmpeg 特效工具 — 基于 Pillow 渲染文字，使用 overlay 滤镜叠到视频上"""

    # 视频尺寸用于字幕渲染
    VIDEO_WIDTH = 1920
    VIDEO_HEIGHT = 1080

    @staticmethod
    def render_subtitle_image(text: str, width: int = 1920,
                               font_size: int = 48) -> Path:
        """用 Pillow 渲染单条字幕为带透明背景的 PNG"""
        output = Path("/tmp/subtitle_frame.png")
        # 创建透明画布
        img = Image.new("RGBA", (width, font_size + 40), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = FFmpegEffects._load_font(font_size)

        # 测量文字尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # 半透明黑色背景条
        margin = 10
        bg_x0 = (width - tw) // 2 - margin
        bg_y0 = (img.height - th) // 2 - margin
        bg_x1 = bg_x0 + tw + margin * 2
        bg_y1 = bg_y0 + th + margin * 2
        draw.rectangle([bg_x0, bg_y0, bg_x1, bg_y1], fill=(0, 0, 0, 128))

        # 文字阴影 + 主体
        x = (width - tw) // 2
        y = (img.height - th) // 2
        draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

        img.save(output, "PNG")
        return output

    @staticmethod
    def subtitle_filter(srt_path: Path, font_size: int = 48) -> str:
        """返回字幕滤镜描述（提示：需要 ffmpeg 编译了 libass 支持）
        如果不可用，请改用 render_subtitle_image + overlay 方案。
        """
        return (
            f"subtitles={srt_path}:"
            f"force_style='FontSize={font_size},"
            f"PrimaryColour=&HFFFFFF,"
            f"Alignment=2,Bold=1,Outline=1,Shadow=1'"
        )

    @staticmethod
    def text_overlay(text: str, font_size: int = 36, x: str = "w/2", y: str = "h-100") -> str:
        """返回 drawtext 滤镜描述（提示：需要 ffmpeg 编译了 libfreetype 支持）
        如果不可用，请改用 render_subtitle_image + overlay 方案。
        """
        escaped_text = text.replace(":", "\\:").replace("'", "\\'")
        return (
            f"drawtext=text='{escaped_text}':"
            f"fontsize={font_size}:fontcolor=white:"
            f"x=({x}-text_w/2):y={y}:"
            f"shadowcolor=black:shadowx=2:shadowy=2"
        )

    @staticmethod
    def overlay_subtitle_on_video(video_path: Path, subtitle_text: str,
                                   output_path: Path, font_size: int = 48) -> Path:
        """通过 Pillow 渲染字幕 + overlay 滤镜叠到视频上"""
        subtitle_img = FFmpegEffects.render_subtitle_image(subtitle_text, font_size=font_size)

        cmd = ["/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "-y", "-i", str(video_path), "-i", str(subtitle_img),
               "-filter_complex",
               "[0:v][1:v]overlay=(W-w)/2:H-h-80:shortest=1",
               "-c:v", "libx264", "-c:a", "copy", "-pix_fmt", "yuv420p",
               str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        """加载中文字体"""
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]
        for fp in font_paths:
            if Path(fp).exists():
                return ImageFont.truetype(fp, size)
        try:
            return ImageFont.truetype("PingFang.ttc", size)
        except OSError:
            return ImageFont.load_default()