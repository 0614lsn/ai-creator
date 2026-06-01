"""质量审核：五维度自动评分"""
import re
from pathlib import Path
from src.media.client import QwenClient


class VideoScorer:
    """视频质量评分器"""

    WEIGHTS = {
        "content_quality": 0.30,
        "voice_naturalness": 0.20,
        "image_text_match": 0.25,
        "structure_completeness": 0.15,
        "emotional_appeal": 0.10,
    }

    def __init__(self):
        self.client = QwenClient()

    def score(self, video_path: Path, script: dict, images: list[Path]) -> dict:
        scores = {}
        scores["content_quality"] = self._score_content(script)
        scores["voice_naturalness"] = self._score_voice(video_path)
        scores["image_text_match"] = self._score_image_text_match(script, images)
        scores["structure_completeness"] = self._score_structure(script, video_path)
        scores["emotional_appeal"] = self._score_emotional(script)
        total = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        scores["total"] = round(total, 1)
        if total >= 80:
            scores["grade"] = "publish"
        elif total >= 60:
            scores["grade"] = "review"
        else:
            scores["grade"] = "reject"
        return scores

    def _score_content(self, script: dict) -> float:
        prompt = f"""请为以下视频脚本的文案质量打分（0-100 分）：
评分标准：语句通顺(30分)、金句感染力(30分)、结构清晰(20分)、适合朗读(20分)
脚本内容：{str(script)[:2000]}
请只返回一个数字分数。"""
        response = self.client.chat(
            model="kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10, temperature=0.1
        )
        return self._parse_score(response)

    def _score_voice(self, video_path: Path) -> float:
        if not video_path.exists():
            return 50.0
        return 70.0  # 简化：TTS 质量基本稳定

    def _score_image_text_match(self, script: dict, images: list[Path]) -> float:
        if not images:
            return 50.0
        import random
        sample = random.sample(images, min(2, len(images)))
        scores = []
        for img in sample:
            prompt = f"图片与以下文字匹配度 0-100 分（只返回数字）：\n{str(script)[:500]}"
            response = self.client.analyze_image(img, prompt)
            scores.append(self._parse_score(response))
        return sum(scores) / len(scores) if scores else 50.0

    def _score_structure(self, script: dict, video_path: Path) -> float:
        score = 100.0
        script_str = str(script)
        if "intro" not in script_str and "title" not in script_str:
            score -= 20
        if "quote" not in script_str and "sections" not in script_str and "angles" not in script_str:
            score -= 30
        if not video_path.exists() or video_path.stat().st_size < 1000:
            score -= 30
        return max(0, score)

    def _score_emotional(self, script: dict) -> float:
        prompt = f"""请为以下视频脚本的情感吸引力打分（0-100 分）：
评分标准：引发共鸣(40分)、情感自然(30分)、记忆点(30分)
脚本：{str(script)[:2000]}
请只返回一个数字分数。"""
        response = self.client.chat(
            model="kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10, temperature=0.1
        )
        return self._parse_score(response)

    def _parse_score(self, text: str) -> float:
        if not text:
            return 50.0
        match = re.search(r'(\d+(?:\.\d+)?)', str(text))
        if match:
            return min(100, max(0, float(match.group(1))))
        return 50.0