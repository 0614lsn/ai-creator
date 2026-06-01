"""片头动画：封面快闪效果"""
import subprocess
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from src.config import VIDEO_RESOLUTION, VIDEO_FPS


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

        # 渲染书名作者文字为图片
        text_overlay_path = self._render_text_overlay(book_title, book_author)

        flash_duration = max(0.3, (duration - 0.5) / len(cover_list))
        inputs = []
        for cover in cover_list:
            inputs.extend(["-loop", "1", "-t", str(flash_duration), "-i", str(cover)])

        concat_inputs = "".join(f"[{i}:v]" for i in range(len(cover_list)))
        filter_complex = (
            f"{concat_inputs}concat=n={len(cover_list)}:v=1:a=0[coverstream];"
            f"[coverstream]fps={VIDEO_FPS},format=yuv420p,"
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2[bg];"
            f"movie={text_overlay_path}:loop=1,setpts=PTS+1/TB[over];"
            f"[bg][over]overlay=(W-w)/2:(H-h)/2:shortest=1,"
            f"fps={VIDEO_FPS},format=yuv420p[v]"
        )

        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
               "-map", "[v]", "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _generate_fallback_intro(self, title: str, author: str, duration: float, output_path: Path) -> Path:
        # 使用 Pillow 渲染文字到图片上
        img_path = self._render_text_overlay(title, author)

        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", f"color=c=0x1a1a2e:s={self.width}x{self.height}:d={duration}",
               "-i", str(img_path),
               "-filter_complex",
               f"[0:v][1:v]overlay=(W-w)/2:(H-h)/2:shortest=1",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _render_text_overlay(self, title: str, author: str) -> Path:
        """用 Pillow 渲染书名 + 作者文字到带透明通道的 PNG 上"""
        output = Path("/tmp/text_overlay.png")
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 尝试加载中文字体
        font_title = self._load_font(64)
        font_author = self._load_font(40)

        # 文字阴影
        shadow_offset = 3
        for text, font, y_off in [
            (title, font_title, -40),
            (f"{author}/著", font_author, 30),
        ]:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            x = (self.width - tw) // 2
            y = (self.height // 2) + y_off
            # 阴影
            draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 180))
            # 主体白色文字
            color = (255, 255, 255, 255) if text == title else (255, 255, 255, 204)
            draw.text((x, y), text, font=font, fill=color)

        output.parent.mkdir(parents=True, exist_ok=True)
        img.save(output, "PNG")
        return output

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        """加载中文字体，优先系统字体，无字体时使用默认"""
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]
        for fp in font_paths:
            if Path(fp).exists():
                return ImageFont.truetype(fp, size)
        # 最后回退 — Pillow 默认字体不支持中文，尝试常见路径
        try:
            return ImageFont.truetype("PingFang.ttc", size)
        except OSError:
            return ImageFont.load_default()