"""片头动画：封面快闪效果"""
import subprocess
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from src.config import VIDEO_RESOLUTION, VIDEO_FPS, FFMPEG_BIN


class IntroGenerator:
    """片头生成器：固定背景 + 封面快闪 + 书名作者"""

    def __init__(self):
        self.width, self.height = VIDEO_RESOLUTION

    def generate_intro(self, book_cover: Optional[Path], other_covers: list[Path],
                       book_title: str, book_author: str, duration: float = 3.0) -> Path:
        output_path = Path("/tmp/intro_segment.mp4")
        cover_list = list(other_covers[:5]) + ([book_cover] if book_cover else [])
        cover_list = [c for c in cover_list if c and c.exists()]

        if not cover_list:
            return self._generate_fallback_intro(book_title, book_author, duration, output_path)

        # 渲染文字叠加层
        text_overlay_path = self._render_text_overlay(book_title, book_author)

        flash_duration = max(0.3, duration / len(cover_list))
        inputs = []
        for cover in cover_list:
            inputs.extend(["-loop", "1", "-t", str(flash_duration), "-i", str(cover)])
        # 文字叠加层也循环
        inputs.extend(["-loop", "1", "-i", str(text_overlay_path)])

        num_covers = len(cover_list)
        concat_inputs = "".join(f"[{i}:v]" for i in range(num_covers))
        # 先 concat 封面，再 overlay 文字
        filter_complex = (
            f"{concat_inputs}concat=n={num_covers}:v=1:a=0[coverstream];"
            f"[coverstream]fps={VIDEO_FPS},format=yuv420p,"
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2[bg];"
            f"[{num_covers}:v]setpts=PTS+1/TB[over];"
            f"[bg][over]overlay=(W-w)/2:(H-h)/2[v]"
        )

        cmd = [FFMPEG_BIN, "-y", *inputs, "-filter_complex", filter_complex,
               "-map", "[v]", "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _generate_fallback_intro(self, title: str, author: str, duration: float, output_path: Path) -> Path:
        img_path = self._render_text_overlay(title, author)
        cmd = [FFMPEG_BIN, "-y",
               "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s={self.width}x{self.height}:d={duration}",
               "-loop", "1", "-i", str(img_path),
               "-filter_complex", "[0:v][1:v]overlay=(W-w)/2:(H-h)/2",
               "-t", str(duration),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _render_text_overlay(self, title: str, author: str) -> Path:
        output = Path("/tmp/text_overlay.png")
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_title = self._load_font(64)
        font_author = self._load_font(40)
        shadow_offset = 3
        for text, font, y_off in [
            (title, font_title, -40),
            (f"{author}/著", font_author, 30),
        ]:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            x = (self.width - tw) // 2
            y = (self.height // 2) + y_off
            draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 180))
            color = (255, 255, 255, 255) if text == title else (255, 255, 255, 204)
            draw.text((x, y), text, font=font, fill=color)
        img.save(output, "PNG")
        return output

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        font_paths = [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
        for fp in font_paths:
            if Path(fp).exists():
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()
