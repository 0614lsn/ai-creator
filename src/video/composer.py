"""视频合成主控：将图片、音频、字幕合成为最终视频"""
import subprocess
from pathlib import Path
from datetime import datetime
from src.config import OUTPUT_DIR, VIDEO_RESOLUTION, VIDEO_FPS
from src.video.intro import IntroGenerator
from src.video.effects import SubtitleGenerator, FFmpegEffects


class VideoComposer:
    """视频合成器：组装最终视频"""

    def __init__(self):
        self.intro_gen = IntroGenerator()
        self.width, self.height = VIDEO_RESOLUTION

    def compose(self, images: list[Path], audio_path: Path, script: dict,
                book_cover: Path = None, other_covers: list[Path] = None,
                book_title: str = "", book_author: str = "") -> Path:
        audio_duration = self._get_audio_duration(audio_path)

        # 1. 片头
        intro_duration = min(3.0, audio_duration * 0.06)
        intro_path = self.intro_gen.generate_intro(
            book_cover, other_covers or [], book_title, book_author, intro_duration
        )

        # 2. 字幕 SRT 文件
        srt_path = SubtitleGenerator.generate_srt(script, audio_duration)

        # 3. 主体图片轮播
        body_duration = audio_duration - intro_duration
        image_segment = self._compose_image_carousel(images, body_duration, book_title, book_author)

        # 4. 合并片头 + 主体（先不带字幕）
        merged_path = Path("/tmp/merged_no_subtitle.mp4")
        cmd_merge = ["ffmpeg", "-y", "-i", str(intro_path), "-i", str(image_segment),
                     "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[vid]",
                     "-map", "[vid]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(merged_path)]
        subprocess.run(cmd_merge, capture_output=True, check=True)

        # 5. 从 SRT 读取字幕文本并逐帧叠加（以第一条字幕为代表）
        subtitle_text = self._extract_first_subtitle(srt_path)

        # 6. 最终输出
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = book_title.replace(" ", "_").replace("/", "_")[:30] if book_title else "video"
        output_path = OUTPUT_DIR / f"{timestamp}_{safe_title}.mp4"

        # 用 Pillow 渲染字幕并合成
        if subtitle_text:
            subtitle_img = FFmpegEffects.render_subtitle_image(subtitle_text)
            cmd = ["ffmpeg", "-y", "-i", str(merged_path), "-i", str(audio_path),
                   "-i", str(subtitle_img),
                   "-filter_complex",
                   "[0:v][2:v]overlay=(W-w)/2:H-h-80:shortest=1[out]",
                   "-map", "[out]", "-map", "1:a",
                   "-c:v", "libx264", "-c:a", "aac",
                   "-pix_fmt", "yuv420p", "-shortest", str(output_path)]
        else:
            cmd = ["ffmpeg", "-y", "-i", str(merged_path), "-i", str(audio_path),
                   "-c:v", "libx264", "-c:a", "aac",
                   "-pix_fmt", "yuv420p", "-shortest", str(output_path)]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _compose_image_carousel(self, images: list[Path], duration: float,
                                 book_title: str, book_author: str) -> Path:
        valid_images = [img for img in images[:100] if img.exists()]
        if not valid_images:
            return self._generate_blank(duration)

        # 在图片上叠加书名作者文字
        text_overlay_path = self._render_small_text_overlay(book_title, book_author)

        per_image = max(3.0, duration / len(valid_images))
        inputs = []
        for img in valid_images:
            inputs.extend(["-loop", "1", "-t", str(per_image), "-i", str(img)])

        concat_inputs = "".join(f"[{i}:v]" for i in range(len(valid_images)))
        filter_complex = (
            f"{concat_inputs}concat=n={len(valid_images)}:v=1:a=0[imgstream];"
            f"[imgstream]fps={VIDEO_FPS},format=yuv420p,"
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2[bg];"
            f"movie={text_overlay_path}:loop=1,setpts=PTS+1/TB[over];"
            f"[bg][over]overlay=0:0:shortest=1[v]"
        )

        output_path = Path("/tmp/body_segment.mp4")
        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
               "-map", "[v]", "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _render_small_text_overlay(self, title: str, author: str) -> Path:
        """渲染书名作者小字水印到左上角"""
        from PIL import Image, ImageDraw, ImageFont

        output = Path("/tmp/body_text_overlay.png")
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_title = self._find_font(32)
        font_author = self._find_font(24)

        draw.text((32, 32), title, font=font_title, fill=(255, 255, 255, 204))
        draw.text((32, 74), f"{author}/著", font=font_author, fill=(255, 255, 255, 153))

        img.save(output, "PNG")
        return output

    def _generate_blank(self, duration: float) -> Path:
        output_path = Path("/tmp/blank_segment.mp4")
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", f"color=c=0x1a1a2e:s={self.width}x{self.height}:d={duration}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def _get_audio_duration(audio_path: Path) -> float:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())

    @staticmethod
    def _extract_first_subtitle(srt_path: Path) -> str:
        """提取 SRT 文件第一条字幕文本"""
        if not srt_path.exists():
            return ""
        content = srt_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        # 跳过序号和时间码行，取第一条字幕文本
        for i, line in enumerate(lines):
            if "-->" in line and i + 1 < len(lines):
                return lines[i + 1].strip()
        return ""

    @staticmethod
    def _find_font(size: int):
        from PIL import ImageFont
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
        for fp in font_paths:
            if Path(fp).exists():
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()