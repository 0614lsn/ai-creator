"""质量审核：五维度诊断评分 + 可执行修复建议"""
import re
import json
from pathlib import Path
from datetime import datetime
from src.media.client import QwenClient


class VideoScorer:
    """视频质量诊断器 — 输出评分 + 具体问题 + 修复建议"""

    WEIGHTS = {
        "content_quality": 0.30,     # 文案质量
        "voice_quality": 0.30,        # 语音质量 (+10%)
        "visual_quality": 0.15,       # 视觉质量 (-10%)
        "structure_completeness": 0.15,  # 结构完整性
        "overall_appeal": 0.10,       # 整体观感
    }

    def __init__(self):
        self.client = QwenClient()

    # ── 主入口 ──────────────────────────────────────

    def evaluate(self, video_path: Path, script: dict,
                 images: list[Path], book_title: str = "") -> dict:
        """全面评估，返回诊断报告"""
        dimensions = {}

        # 1. 文案质量
        dimensions["content_quality"] = self._eval_content(script, video_path)

        # 2. 语音质量
        dimensions["voice_quality"] = self._eval_voice(video_path, script)

        # 3. 视觉质量
        dimensions["visual_quality"] = self._eval_visual(images, script)

        # 4. 结构完整性
        dimensions["structure_completeness"] = self._eval_structure(script, video_path)

        # 5. 整体观感
        dimensions["overall_appeal"] = self._eval_overall(script, video_path)

        # 加权总分
        total = sum(
            dimensions[k]["score"] * self.WEIGHTS[k]
            for k in self.WEIGHTS
        )

        # 汇总所有问题
        all_issues = []
        for dim_name, dim_result in dimensions.items():
            for issue in dim_result.get("issues", []):
                issue["dimension"] = dim_name
                all_issues.append(issue)

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        all_issues.sort(key=lambda x: severity_order.get(x["severity"], 99))

        # 判定等级
        high_count = sum(1 for i in all_issues if i["severity"] == "high")
        if total >= 80 and high_count == 0:
            grade = "publish"
        elif total >= 60 and high_count <= 1:
            grade = "review"
        else:
            grade = "reject"

        return {
            "video": str(video_path),
            "book": book_title,
            "evaluated_at": datetime.now().isoformat(),
            "total_score": round(total, 1),
            "grade": grade,
            "dimensions": dimensions,
            "issues": all_issues,
            "high_count": high_count,
            "fix_priority": [i for i in all_issues if i["severity"] == "high"],
        }

    # ── 维度 1: 文案质量 ───────────────────────────

    def _eval_content(self, script: dict, video_path: Path) -> dict:
        text = self._extract_full_text(script)
        duration = self._get_video_duration(video_path)
        char_count = len(text)

        prompt = f"""你是短视频内容审核专家。请分析以下读书短视频的文案质量。

视频时长: {duration:.0f} 秒
文案字数: {char_count}
文案内容:
{text}

请从以下方面诊断（不要检查片头 hook，片头是固定模板）：

1. 语句是否通顺流畅？
2. 金句是否有感染力？（能否引发共鸣）
3. 是否适合朗读？（有无拗口长句、断句问题）
4. 信息密度是否合理？（字数/时长比约 3-4 字/秒最佳，当前 {char_count/max(duration,1):.1f} 字/秒）
5. 是否有语病或不通顺的地方？

请以 JSON 格式返回诊断结果：
{{"score": 0-100, "summary": "一句话总结", "issues": [{{"severity": "high|medium|low", "description": "具体问题描述", "location": "问题在文案中的位置", "suggestion": "如何修复"}}], "strengths": ["优点1", "优点2"]}}

只返回 JSON，不要有其他文字。"""

        response = self.client.chat(
            model="kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024, temperature=0.3
        )
        return self._parse_diagnosis(response, default_score=70)

    # ── 维度 2: 语音质量 ───────────────────────────

    def _eval_voice(self, video_path: Path, script: dict) -> dict:
        text = self._extract_full_text(script)
        duration = self._get_video_duration(video_path)

        # 如果视频存在且有足够长度，用 qwen3.5-omni-plus 分析音频
        if video_path.exists() and duration > 5:
            try:
                return self._eval_voice_with_ai(video_path, text, duration)
            except Exception:
                pass

        # 备选：基于规则的评估
        char_count = len(text)
        chars_per_sec = char_count / max(duration, 1)

        issues = []
        if chars_per_sec < 3.0:
            issues.append({
                "severity": "medium", "description": f"语速偏慢 ({chars_per_sec:.1f} 字/秒)，听众可能觉得拖沓",
                "suggestion": "调高 TTS speed 参数到 0.95-1.0"
            })
        elif chars_per_sec > 5.0:
            issues.append({
                "severity": "medium", "description": f"语速偏快 ({chars_per_sec:.1f} 字/秒)，听众可能跟不上",
                "suggestion": "降低 TTS speed 参数到 0.80-0.85"
            })

        score = 85 if not issues else 65
        return {
            "score": score, "summary": f"语速 {chars_per_sec:.1f} 字/秒",
            "issues": issues, "strengths": []
        }

    def _eval_voice_with_ai(self, video_path: Path, text: str, duration: float) -> dict:
        """用 qwen3.5-omni-plus 分析视频音频"""
        # 提取音频片段用于分析
        import base64, subprocess
        audio_sample = Path("/tmp/voice_sample.wav")
        subprocess.run([
            "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "-y",
            "-i", str(video_path), "-ss", "1", "-t", "15",
            "-q:a", "0", "-map", "a", str(audio_sample)
        ], capture_output=True, check=True)

        with open(audio_sample, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = f"""你是配音导演。请分析这段读书短视频的旁白质量。

文案内容: {text[:300]}
视频总时长: {duration:.0f} 秒

请从以下方面诊断：
1. 语速是否适中？（短视频最佳 3.5-4.5 字/秒）
2. 情感表达是否丰富？（温暖、有磁性、娓娓道来）
3. 关键词语是否有强调？
4. 停顿是否在自然位置？
5. 整体听起来是否舒服？

请以 JSON 格式返回：
{{"score": 0-100, "summary": "一句话总结", "issues": [{{"severity": "high|medium|low", "description": "具体问题", "suggestion": "修复建议"}}], "strengths": ["优点"]}}"""

        response = self.client._send_audio_analysis(audio_b64, prompt)
        return self._parse_diagnosis(response, default_score=70)

    # ── 维度 3: 视觉质量 ───────────────────────────

    def _eval_visual(self, images: list[Path], script: dict) -> dict:
        if not images:
            return {
                "score": 40, "summary": "无图片",
                "issues": [{"severity": "high", "description": "没有任何配图", "suggestion": "至少生成 4 张配图"}],
                "strengths": []
            }

        # 抽样分析
        import random
        sample = random.sample(images, min(3, len(images)))

        text_snippets = self._extract_text_segments(script)

        visual_scores = []
        for i, img in enumerate(sample):
            if not img.exists():
                continue
            context = text_snippets[i % len(text_snippets)] if text_snippets else str(script)[:200]
            prompt = f"""你是视觉设计审核。请评估这张配图：

对应文案: {context}

请从以下方面诊断：
1. 图片是否与文案内容相关？
2. 画面是否美观（构图/色彩/氛围）？
3. 是否适合作为读书视频的配图？
4. 风格是否统一（与其他图片对比）？

返回 JSON: {{"score": 0-100, "relevance": 0-100, "beauty": 0-100, "issues": [{{"severity": "...", "description": "..."}}]}}"""
            try:
                response = self.client.analyze_image(img, prompt)
                result = self._parse_diagnosis(response, default_score=60)
                visual_scores.append(result)
            except Exception:
                visual_scores.append({"score": 60})

        avg_score = sum(v.get("score", 60) for v in visual_scores) / max(len(visual_scores), 1)

        all_issues = []
        for v in visual_scores:
            all_issues.extend(v.get("issues", []))

        # 图片数量检查
        if len(images) < 4:
            all_issues.append({
                "severity": "medium", "description": f"只有 {len(images)} 张配图，40秒视频建议 6-10 张",
                "suggestion": "在生图阶段增加 image_prompts 数量"
            })

        return {
            "score": round(avg_score),
            "summary": f"分析了 {len(sample)}/{len(images)} 张图片",
            "issues": all_issues,
            "strengths": [],
            "per_image": visual_scores,
        }

    # ── 维度 4: 结构完整性 ─────────────────────────

    def _eval_structure(self, script: dict, video_path: Path) -> dict:
        issues = []
        strengths = []
        score = 100

        script_str = str(script)
        duration = self._get_video_duration(video_path)

        # 检查必要组成部分
        has_intro = "intro" in script_str or "title" in script_str
        has_body = "quote" in script_str or "sections" in script_str or "angles" in script_str
        has_closing = "closing" in script_str or "summary" in script_str
        video_exists = video_path.exists() and video_path.stat().st_size > 10000

        if not has_intro:
            issues.append({"severity": "high", "description": "缺少片头内容", "suggestion": "检查脚本润色模板"})
            score -= 20
        else:
            strengths.append("片头结构完整")

        if not has_body:
            issues.append({"severity": "high", "description": "缺少主体内容", "suggestion": "检查 LLM 脚本生成"})
            score -= 30
        else:
            strengths.append("主体内容完整")

        if not video_exists:
            issues.append({"severity": "high", "description": "视频文件异常（过小或不存在）", "suggestion": "检查 FFmpeg 合成"})
            score -= 30

        # 时长检查
        if duration < 15:
            issues.append({"severity": "medium", "description": f"视频时长 {duration:.0f}s 偏短", "suggestion": "增加文案字数或降低语速"})
            score -= 10
        elif duration > 70:
            issues.append({"severity": "medium", "description": f"视频时长 {duration:.0f}s 偏长", "suggestion": "精简文案或提高语速"})
            score -= 10

        return {
            "score": max(0, score),
            "summary": f"结构检查: intro={has_intro} body={has_body} duration={duration:.0f}s",
            "issues": issues,
            "strengths": strengths,
        }

    # ── 维度 5: 整体观感 ───────────────────────────

    def _eval_overall(self, script: dict, video_path: Path) -> dict:
        text = self._extract_full_text(script)
        duration = self._get_video_duration(video_path)

        prompt = f"""你是内容审核。请评估这个读书短视频的整体观感。

文案:
{text[:500]}

时长: {duration:.0f} 秒

请从以下方面诊断：
1. 是否有情感共鸣？（看完有没有被打动）
2. 是否有记忆点？（有没有让人记住的金句或画面）
3. BGM 是否合适？（如果有背景音乐的话）
4. 整体是否流畅连贯？

不要检查是否"像 AI 生成"——这就是 AI 生成的，不需要假装是人类做的。

返回 JSON: {{"score": 0-100, "summary": "...", "issues": [{{"severity": "high|medium|low", "description": "...", "suggestion": "..."}}], "strengths": ["..."]}}"""

        response = self.client.chat(
            model="kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512, temperature=0.3
        )
        return self._parse_diagnosis(response, default_score=65)

    # ── 辅助方法 ────────────────────────────────────

    def _extract_full_text(self, script: dict) -> str:
        parts = []
        if "intro" in script:
            parts.append(script["intro"])
        if "quote" in script:
            parts.append(script["quote"])
        if "sections" in script:
            for s in script["sections"]:
                if "heading" in s:
                    parts.append(s["heading"])
                if "content" in s:
                    parts.append(s["content"])
        if "closing" in script:
            parts.append(script["closing"])
        if "angles" in script:
            for a in script["angles"]:
                if "name" in a:
                    parts.append(a["name"])
                if "example" in a:
                    parts.append(a["example"])
        return "。".join(parts)

    def _extract_text_segments(self, script: dict) -> list[str]:
        """提取文案的各段文字（用于图文匹配检查）"""
        segments = []
        if "intro" in script:
            segments.append(script["intro"])
        if "quote" in script:
            segments.append(script["quote"][:100])
            if len(script["quote"]) > 100:
                segments.append(script["quote"][100:200])
        if "sections" in script:
            for s in script["sections"]:
                segments.append(s.get("content", "")[:150])
        return segments or [str(script)[:200]]

    @staticmethod
    def _get_video_duration(video_path: Path) -> float:
        import subprocess
        try:
            cmd = ["/opt/homebrew/opt/ffmpeg-full/bin/ffprobe", "-v", "error",
                   "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _parse_diagnosis(self, response: str, default_score: int = 60) -> dict:
        """解析 LLM 返回的诊断 JSON"""
        try:
            # 提取 JSON 部分
            text = str(response) if response else ""
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            result = json.loads(text.strip())

            # 确保必要字段
            if "score" not in result:
                result["score"] = default_score
            if "issues" not in result:
                result["issues"] = []
            if "strengths" not in result:
                result["strengths"] = []
            if "summary" not in result:
                result["summary"] = ""
            return result
        except (json.JSONDecodeError, AttributeError):
            return {
                "score": default_score,
                "summary": "无法解析诊断结果",
                "issues": [],
                "strengths": [],
            }

    def _send_audio_analysis(self, audio_b64: str, prompt: str) -> str:
        """发送音频到 qwen3.5-omni-plus 分析"""
        import base64
        try:
            completion = self.client.client.chat.completions.create(
                model="qwen3.5-omni-plus",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"data": f"data:;base64,{audio_b64}", "format": "wav"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                modalities=["text"],
                max_tokens=1024,
                stream=True,
                stream_options={"include_usage": True},
            )
            text = ""
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    text += chunk.choices[0].delta.content
            return text
        except Exception:
            return ""

    # ── 兼容旧接口 ──────────────────────────────────

    def score(self, video_path: Path, script: dict, images: list[Path]) -> dict:
        """旧接口兼容：返回简化评分"""
        result = self.evaluate(video_path, script, images)
        return {
            "total": result["total_score"],
            "grade": result["grade"],
            "content_quality": result["dimensions"]["content_quality"]["score"],
            "voice_naturalness": result["dimensions"]["voice_quality"]["score"],
            "image_text_match": result["dimensions"]["visual_quality"]["score"],
            "structure_completeness": result["dimensions"]["structure_completeness"]["score"],
            "emotional_appeal": result["dimensions"]["overall_appeal"]["score"],
        }
