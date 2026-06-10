"""HappyHorse 文生视频客户端：异步提交 → 轮询 → 下载"""
import time
import requests
from pathlib import Path

from src.config import (
    DASHSCOPE_API_KEY, VIDEO_SYNTHESIS_URL, TASK_QUERY_URL,
    VIDEO_MODEL, VIDEO_RESOLUTION, VIDEO_RATIO,
    CLIP_MIN_SECONDS, CLIP_MAX_SECONDS, CLIPS_DIR,
)

_HEADERS = {
    "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
    "Content-Type": "application/json",
}


def submit(prompt: str, duration: int, seed: int = None,
           resolution: str = None) -> str:
    """提交文生视频任务，返回 task_id"""
    duration = max(CLIP_MIN_SECONDS, min(CLIP_MAX_SECONDS, int(duration)))
    payload = {
        "model": VIDEO_MODEL,
        "input": {"prompt": prompt},
        "parameters": {
            "resolution": resolution or VIDEO_RESOLUTION,
            "ratio": VIDEO_RATIO,
            "duration": duration,
            "watermark": False,
        },
    }
    if seed is not None:
        payload["parameters"]["seed"] = seed

    for attempt in range(3):
        resp = requests.post(
            VIDEO_SYNTHESIS_URL,
            headers={**_HEADERS, "X-DashScope-Async": "enable"},
            json=payload, timeout=60,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("output", {}).get("task_id"):
            return data["output"]["task_id"]
        # 限流/服务端错误退避重试
        if resp.status_code in (429, 500, 502, 503):
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError(f"HappyHorse 提交失败: {resp.status_code} {data}")
    raise RuntimeError("HappyHorse 提交失败: 重试耗尽（限流）")


def query(task_id: str) -> dict:
    """查询任务状态，返回 output 字典"""
    resp = requests.get(
        TASK_QUERY_URL.format(task_id=task_id),
        headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}"},
        timeout=30,
    )
    return resp.json().get("output", {})


def wait_all(task_ids: list[str], poll_interval: int = 15,
             timeout: int = 1800) -> list[str]:
    """轮询等待一批任务完成，按提交顺序返回 video_url 列表"""
    urls: dict[str, str] = {}
    pending = set(task_ids)
    start = time.time()

    while pending:
        if time.time() - start > timeout:
            raise TimeoutError(f"等待超时，未完成任务: {pending}")
        time.sleep(poll_interval)
        for tid in list(pending):
            out = query(tid)
            status = out.get("task_status", "UNKNOWN")
            if status == "SUCCEEDED":
                urls[tid] = out["video_url"]
                pending.discard(tid)
                print(f"    片段完成 {len(urls)}/{len(task_ids)}")
            elif status in ("FAILED", "CANCELED", "UNKNOWN"):
                raise RuntimeError(
                    f"任务 {tid} 失败: {status} "
                    f"{out.get('code', '')} {out.get('message', '')}"
                )
        elapsed = int(time.time() - start)
        if pending:
            print(f"    生成中... {len(urls)}/{len(task_ids)} 完成（{elapsed}s）")

    return [urls[tid] for tid in task_ids]


def download(url: str, out_path: Path) -> Path:
    """下载视频（结果 URL 24h 失效，生成后立即落盘）"""
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    return out_path


def generate_clips(shots: list[dict], run_id: str) -> list[Path]:
    """为每个分镜生成视频片段。

    shots 每项需含: video_prompt, clip_seconds
    返回与 shots 等长的本地 mp4 路径列表。
    """
    print(f"  提交 {len(shots)} 个 HappyHorse 任务...")
    task_ids = []
    for i, shot in enumerate(shots):
        tid = submit(shot["video_prompt"], shot["clip_seconds"])
        task_ids.append(tid)
        print(f"    [{i + 1}/{len(shots)}] task={tid} duration={shot['clip_seconds']}s")
        time.sleep(1)  # 平滑提交速率

    urls = wait_all(task_ids)

    paths = []
    for i, url in enumerate(urls):
        path = CLIPS_DIR / f"{run_id}_shot{i + 1}.mp4"
        download(url, path)
        paths.append(path)
        print(f"    已下载: {path.name}")
    return paths
