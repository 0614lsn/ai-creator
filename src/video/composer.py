"""视频合成主控：将图片、音频、字幕合成为最终视频"""
import subprocess
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from src.config import OUTPUT_DIR, VIDEO_RESOLUTION, VIDEO_FPS, FFMPEG_BIN, FFPROBE_BIN
from src.video.intro import IntroGenerator
from src.video.effects import SubtitleGenerator


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

        # 2. 主体图片轮播
        body_duration = audio_duration - intro_duration
        body_path = self._compose_image_carousel(images, body_duration, book_title, book_author)

        # 3. 合并片头 + 主体
        merged_path = Path("/tmp/merged_no_subtitle.mp4")
        concat_list = Path("/tmp/concat_list.txt")
        concat_list.write_text(
            f"file '{intro_path}'\nfile '{body_path}'\n"
        )
        cmd_merge = [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_list), "-c", "copy", str(merged_path)]
        subprocess.run(cmd_merge, capture_output=True, check=True)

        # 4. 最终输出：合并视频 + 音频
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = book_title.replace(" ", "_").replace("/", "_")[:30] if book_title else "video"
        output_path = OUTPUT_DIR / f"{timestamp}_{safe_title}.mp4"

        cmd = [FFMPEG_BIN, "-y", "-i", str(merged_path), "-i", str(audio_path),
               "-c:v", "copy", "-c:a", "aac", "-shortest", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _compose_image_carousel(self, images: list[Path], duration: float,
                                 book_title: str, book_author: str) -> Path:
        valid_images = [img for img in images[:100] if img.exists()]
        if not valid_images:
            return self._generate_blank(duration)

        per_image = max(3.0, duration / len(valid_images))
        # 先生成每张图片的单独视频片段
        segments = []
        for i, img in enumerate(valid_images):
            seg_path = Path(f"/tmp/seg_{i}.mp4")
            cmd = [FFMPEG_BIN, "-y", "-loop", "1", "-i", str(img),
                   "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,fps={VIDEO_FPS},format=yuv420p",
                   "-t", str(per_image), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(seg_path)]
            subprocess.run(cmd, capture_output=True, check=True)
            segments.append(seg_path)

        # 使用 concat demuxer 合并
        concat_list = Path("/tmp/body_concat.txt")
        concat_list.write_text(
            "\n".join(f"file '{s}'" for s in segments) + "\n"
        )
        output_path = Path("/tmp/body_segment.mp4")
        cmd = [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0",
               "-i", str(concat_list), "-c", "copy", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _generate_blank(self, duration: float) -> Path:
        output_path = Path("/tmp/blank_segment.mp4")
        cmd = [FFMPEG_BIN, "-y", "-f", "lavfi",
               "-i", f"color=c=0x1a1a2e:s={self.width}x{self.height}:d={duration}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def _get_audio_duration(audio_path: Path) -> float:
        cmd = [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
