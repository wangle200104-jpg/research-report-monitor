"""RSS/RSSHub research report source
References: RSSHub (github.com/DIYgod/RSSHub)
Supports RSS 2.0 and Atom feeds, no feedparser dependency.
"""
import re
import logging
import xml.etree.ElementTree as ET
from typing import List, Optional
from datetime import datetime
from hashlib import md5

import requests
from .base import ReportSource, ReportItem

logger = logging.getLogger(__name__)


class RSSSource(ReportSource):
    DEFAULT_FEEDS = [
        {"name": "东方财富-行业研报", "path": "/eastmoney/report/industry", "enabled": True},
        {"name": "东方财富-个股研报", "path": "/eastmoney/report/stock", "enabled": True},
        {"name": "财联社-电报", "path": "/cls/telegraph", "enabled": False},
    ]

    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchReportMonitor/1.0)", "Accept": "application/xml, */*"}

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.rsshub_base = self.config.get("rsshub_base", "https://rsshub.app").rstrip("/")
        self.feeds = self.config.get("feeds", self.DEFAULT_FEEDS)
        self.custom_urls = self.config.get("custom_urls", [])

    @property
    def name(self) -> str:
        return "RSS订阅"

    def search(self, keywords: List[str], page: int = 1, page_size: int = 50) -> List[ReportItem]:
        return self.filter_by_keywords(self._fetch_all(page_size), keywords)

    def get_latest(self, page_size: int = 50) -> List[ReportItem]:
        return self._fetch_all(page_size)

    def _fetch_all(self, limit: int = 50) -> List[ReportItem]:
        all_items = []
        for feed in self.feeds:
            if not feed.get("enabled", True):
                continue
            url = f"{self.rsshub_base}{feed['path']}"
            try:
                all_items.extend(self._parse_feed(url, feed.get("name", "RSS"))[:20])
            except Exception as e:
                logger.debug(f"RSS [{feed.get('name')}] failed: {e}")
        for url in self.custom_urls:
            try:
                all_items.extend(self._parse_feed(url, "Custom")[:20])
            except Exception:
                pass
        return all_items[:limit]

    def _parse_feed(self, url: str, source_name: str) -> List[ReportItem]:
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.text.lstrip('\ufeff'))
        except Exception as e:
            raise RuntimeError(f"Feed parse failed: {e}")

        reports = []
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                r = self._parse_rss(item, source_name)
                if r:
                    reports.append(r)
        else:
            for entry in root.findall("entry") or root.findall("{http://www.w3.org/2005/Atom}entry"):
                r = self._parse_atom(entry, source_name)
                if r:
                    reports.append(r)
        return reports

    def _parse_rss(self, item: ET.Element, src: str) -> Optional[ReportItem]:
        title = self._text(item, "title")
        if not title:
            return None
        link = self._text(item, "link") or ""
        desc = re.sub(r'<[^>]+>', '', self._text(item, "description") or "")[:200]
        pub = self._parse_date(self._text(item, "pubDate") or "")
        pdf = ""
        enc = item.find("enclosure")
        if enc is not None and enc.get("url", "").endswith(".pdf"):
            pdf = enc.get("url")
        uid = md5(f"{title}{link}".encode()).hexdigest()[:12]
        return ReportItem(id=f"rss_{uid}", title=re.sub(r'<[^>]+>', '', title),
                          org_name=src, publish_date=pub, summary=desc,
                          pdf_url=pdf, info_url=link, source=f"RSS-{src}")

    def _parse_atom(self, entry: ET.Element, src: str) -> Optional[ReportItem]:
        title = self._text(entry, "title")
        if not title:
            return None
        link_el = entry.find("link")
        link = link_el.get("href", "") if link_el is not None else ""
        pub = self._parse_date(self._text(entry, "published") or self._text(entry, "updated") or "")
        uid = md5(f"{title}{link}".encode()).hexdigest()[:12]
        return ReportItem(id=f"rss_{uid}", title=re.sub(r'<[^>]+>', '', title),
                          org_name=src, publish_date=pub, info_url=link, source=f"RSS-{src}")

    @staticmethod
    def _text(el: ET.Element, tag: str) -> str:
        child = el.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    @staticmethod
    def _parse_date(s: str) -> str:
        if not s:
            return ""
        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"]:
            try:
                return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s[:10] if len(s) >= 10 and s[4] == '-' else ""
