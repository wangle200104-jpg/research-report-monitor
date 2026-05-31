"""Download history manager for deduplication / 下载历史记录管理"""
import os
import json
from datetime import datetime, timedelta


class DownloadHistory:
    def __init__(self, history_file: str = None, keep_days: int = 90):
        if history_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            history_file = os.path.join(base_dir, "data", "download_history.json")
        self.history_file = history_file
        self.keep_days = keep_days
        self.history = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save(self):
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def is_downloaded(self, report_id: str) -> bool:
        return report_id in self.history

    def add(self, report_id: str, title: str, url: str = ""):
        self.history[report_id] = {
            "title": title,
            "url": url,
            "downloaded_at": datetime.now().isoformat()
        }
        self.save()

    def cleanup(self):
        cutoff = datetime.now() - timedelta(days=self.keep_days)
        to_remove = []
        for report_id, info in self.history.items():
            try:
                downloaded_at = datetime.fromisoformat(info["downloaded_at"])
                if downloaded_at < cutoff:
                    to_remove.append(report_id)
            except (KeyError, ValueError):
                continue
        for report_id in to_remove:
            del self.history[report_id]
        if to_remove:
            self.save()
        return len(to_remove)

    def count(self) -> int:
        return len(self.history)
