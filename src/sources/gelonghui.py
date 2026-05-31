"""Gelonghui (格隆汇) research report source"""
import re
import time
import logging
from typing import List, Optional

import requests
from .base import ReportSource, ReportItem

logger = logging.getLogger(__name__)


class GelonghuiSource(ReportSource):
    SEARCH_URL = "https://www.gelonghui.com/api/search/v3"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.gelonghui.com/",
        "Accept": "application/json",
    }

    @property
    def name(self) -> str:
        return "格隆汇"

    def search(self, keywords: List[str], page: int = 1, page_size: int = 50) -> List[ReportItem]:
        all_reports, seen_ids = [], set()
        for keyword in keywords[:5]:
            try:
                for r in self._search_kw(keyword, page, min(page_size, 20)):
                    if r.id not in seen_ids:
                        seen_ids.add(r.id)
                        all_reports.append(r)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Gelonghui search '{keyword}' failed: {e}")
        return self.filter_by_keywords(all_reports, keywords)

    def get_latest(self, page_size: int = 50) -> List[ReportItem]:
        return []

    def _search_kw(self, keyword: str, page: int, page_size: int) -> List[ReportItem]:
        params = {"keyword": keyword, "type": "article", "page": page, "pageSize": page_size}
        try:
            resp = requests.get(self.SEARCH_URL, params=params, headers=self.HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        items = data.get("result", {}).get("list", []) or data.get("data", []) or []
        return [r for r in (self._parse(item) for item in items) if r]

    def _parse(self, item: dict) -> Optional[ReportItem]:
        item_id = str(item.get("id", "") or item.get("articleId", ""))
        title = item.get("title", "") or ""
        if not title:
            return None
        title = re.sub(r'<[^>]+>', '', title)
        pub_date = (item.get("publishDate", "") or item.get("createDate", "") or "")[:10]

        return ReportItem(
            id=f"glh_{item_id}", title=title,
            author=item.get("author", "") or "",
            org_name=item.get("source", "") or "",
            publish_date=pub_date,
            summary=(item.get("summary", "") or "")[:200],
            pdf_url=item.get("pdfUrl", "") or "",
            info_url=f"https://www.gelonghui.com/p/{item_id}" if item_id else "",
            industry="", source=self.name, rating="",
        )
