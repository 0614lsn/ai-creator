"""调度管理：cron 任务 + 邮件告警"""
import smtplib
import subprocess
from email.mime.text import MIMEText
from datetime import datetime
from src.config import ALERT_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD


class CronManager:
    @staticmethod
    def install_crontab():
        project_root = "/Users/hb27939/Downloads/ai_creator"
        python_bin = f"{project_root}/.venv/bin/python"
        orchestrator = f"{project_root}/src/orchestrator.py"

        cron_entries = f"""
# AI 读书视频 Agent 定时任务
0 8 * * * cd {project_root} && {python_bin} {orchestrator} crawl
0 10 * * * cd {project_root} && {python_bin} {orchestrator} short
0 12 * * * cd {project_root} && {python_bin} {orchestrator} review-short
0 14 * * 4 cd {project_root} && {python_bin} {orchestrator} long
0 18 * * 4 cd {project_root} && {python_bin} {orchestrator} review-long
"""

        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if "AI 读书视频 Agent" not in (result.stdout or ""):
            new_crontab = (result.stdout or "") + cron_entries
            subprocess.run(["crontab"], input=new_crontab.encode(), check=True)
            print("✅ Cron 任务已安装")
        else:
            print("Cron 任务已存在，跳过")

    @staticmethod
    def uninstall_crontab():
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        lines = (result.stdout or "").split("\n")
        filtered = []
        skip = False
        for line in lines:
            if "AI 读书视频 Agent" in line:
                skip = True
                continue
            if skip:
                if not line.strip() or line.startswith("#") or line.startswith("0 "):
                    continue
                skip = False
            filtered.append(line)
        subprocess.run(["crontab"], input="\n".join(filtered).encode(), check=True)
        print("✅ Cron 任务已移除")


class AlertManager:
    @staticmethod
    def send_alert(subject: str, body: str):
        if not SMTP_USER or not SMTP_PASSWORD:
            print(f"[ALERT] {subject}: {body}")
            return

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[AI视频Agent] {subject}"
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            print(f"[{datetime.now()}] 告警邮件已发送: {subject}")
        except Exception as e:
            print(f"[{datetime.now()}] 邮件发送失败: {e}")