"""CNINFO (巨潮资讯) research report source
References: cninfo_process, juchao_ants, CninfoSpider
"""
import re
import time
import logging
from typing import List, Optional
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import ReportSource, ReportItem

logger = logging.getLogger(__name__)


class CninfoSource(ReportSource):
    FULLTEXT_SEARCH_URL = "http://www.cninfo.com.cn/new/fulltextSearch/full"
    PDF_BASE_URL = "http://static.cninfo.com.cn/"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://www.cninfo.com.cn/new/fulltextSearch",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, days_back: int = 7, max_retries: int = 3):
        self.days_back = days_back
        session = requests.Session()
        retry = Retry(total=max_retries, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("http://", HTTPAdapter(max_retries=retry))
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update(self.HEADERS)
        self.session = session

    @property
    def name(self) -> str:
        return "巨潮资讯"

    def search(self, keywords: List[str], page: int = 1, page_size: int = 50) -> List[ReportItem]:
        all_reports, seen_ids = [], set()
        for keyword in [kw for kw in keywords if len(kw) >= 2][:5]:
            try:
                for r in self._search(keyword, page, min(page_size, 30)):
                    if r.id not in seen_ids:
                        seen_ids.add(r.id)
                        all_reports.append(r)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"CNINFO search '{keyword}' failed: {e}")
        filtered = self.filter_by_keywords(all_reports, keywords)
        logger.info(f"巨潮资讯: {len(all_reports)} found, {len(filtered)} matched")
        return filtered

    def get_latest(self, page_size: int = 50) -> List[ReportItem]:
        try:
            return self._search("研究报告", page=1, page_size=page_size)
        except Exception as e:
            logger.error(f"Get latest failed: {e}")
            return []

    def _search(self, keyword: str, page: int = 1, page_size: int = 30) -> List[ReportItem]:
        data = {
            "searchkey": keyword,
            "sdate": (datetime.now() - timedelta(days=self.days_back)).strftime("%Y-%m-%d"),
            "edate": datetime.now().strftime("%Y-%m-%d"),
            "isfulltext": "false",
            "sortName": "pubdate", "sortType": "desc",
            "pageNum": page, "pageSize": page_size,
        }
        try:
            resp = self.session.post(self.FULLTEXT_SEARCH_URL, data=data, timeout=15)
            resp.raise_for_status()
            result = resp.json()
        except Exception as e:
            logger.error(f"CNINFO API failed: {e}")
            return []

        items = result.get("announcements", []) or result.get("totalAnnouncement", []) or []
        return [r for r in (self._parse(item) for item in items) if r]

    def _parse(self, item: dict) -> Optional[ReportItem]:
        ann_id = str(item.get("announcementId", "") or item.get("id", ""))
        title = item.get("announcementTitle", "") or item.get("title", "")
        if not title:
            return None
        title = re.sub(r'<[^>]+>', '', title).strip()

        pub_time = item.get("announcementTime", 0)
        if isinstance(pub_time, (int, float)) and pub_time > 0:
            publish_date = datetime.fromtimestamp(pub_time / 1000).strftime("%Y-%m-%d")
        else:
            publish_date = str(pub_time)[:10] if pub_time else ""

        adj_url = item.get("adjunctUrl", "") or ""
        pdf_url = f"{self.PDF_BASE_URL}{adj_url}" if adj_url else ""

        return ReportItem(
            id=f"cn_{ann_id}" if ann_id else f"cn_{hash(title)}",
            title=title, author="",
            org_name=item.get("secName", "") or "",
            publish_date=publish_date, summary="",
            pdf_url=pdf_url,
            info_url=f"http://www.cninfo.com.cn/new/disclosure/detail?announcementId={ann_id}" if ann_id else "",
            industry="", source=self.name, rating="",
        )
