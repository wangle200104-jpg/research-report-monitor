"""PDF downloader with retry and concurrent download"""
import os
import re
import logging
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .sources.base import ReportItem

logger = logging.getLogger(__name__)


class ReportDownloader:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf, application/octet-stream, */*",
    }

    def __init__(self, output_dir: str, max_concurrent: int = 3, max_file_size_mb: int = 50, max_retries: int = 3):
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent
        self.max_file_size = max_file_size_mb * 1024 * 1024
        session = requests.Session()
        retry = Retry(total=max_retries, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("http://", HTTPAdapter(max_retries=retry))
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update(self.HEADERS)
        self.session = session
        os.makedirs(output_dir, exist_ok=True)

    def download_report(self, report: ReportItem) -> Optional[str]:
        if not report.pdf_url:
            return None
        filename = self._safe_filename(report)
        sub_dir = self._get_sub_dir(report)
        filepath = os.path.join(sub_dir, filename)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath
        try:
            resp = self.session.get(report.pdf_url, stream=True, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "html" in content_type:
                return None
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > self.max_file_size:
                return None
            downloaded = 0
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded > self.max_file_size:
                            break
                        f.write(chunk)
            if downloaded < 1024:
                os.remove(filepath)
                return None
            logger.info(f"Downloaded: {filename} ({downloaded/1024:.0f}KB)")
            return filepath
        except Exception as e:
            logger.error(f"Download failed: {report.title} - {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None

    def batch_download(self, reports: List[ReportItem]) -> Dict[str, list]:
        results = {"success": [], "failed": [], "skipped": []}
        with_pdf = [r for r in reports if r.pdf_url]
        results["skipped"] = [r for r in reports if not r.pdf_url]
        if not with_pdf:
            return results
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {executor.submit(self.download_report, r): r for r in with_pdf}
            for future in as_completed(futures):
                report = futures[future]
                try:
                    if future.result():
                        results["success"].append(report)
                    else:
                        results["failed"].append(report)
                except Exception:
                    results["failed"].append(report)
        return results

    def _get_sub_dir(self, report: ReportItem) -> str:
        from datetime import datetime
        month = report.publish_date[:7] if report.publish_date and len(report.publish_date) >= 7 else datetime.now().strftime("%Y-%m")
        sub_dir = os.path.join(self.output_dir, month)
        os.makedirs(sub_dir, exist_ok=True)
        return sub_dir

    def _safe_filename(self, report: ReportItem) -> str:
        parts = []
        if report.publish_date:
            parts.append(report.publish_date)
        if report.org_name:
            parts.append(report.org_name[:8])
        parts.append(report.title[:50])
        filename = "_".join(parts) + ".pdf"
        filename = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', filename)
        filename = re.sub(r'_{2,}', '_', filename).strip('_. ')
        return filename if filename.endswith('.pdf') else filename + '.pdf'
