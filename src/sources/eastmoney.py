"""East Money research report source (optimized)

References: AKShare, stock-open-api, RSSHub eastmoney route
API: reportapi.eastmoney.com/report/list
"""
import re
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import ReportSource, ReportItem

logger = logging.getLogger(__name__)


class EastMoneySource(ReportSource):
    REPORT_LIST_URL = "https://reportapi.eastmoney.com/report/list"
    REPORT_JGDY_URL = "https://reportapi.eastmoney.com/report/jgdy"
    REPORT_DETAIL_URL = "https://data.eastmoney.com/report/info/{}.html"

    INDUSTRY_CODES: Dict[str, str] = {
        "电子": "016", "半导体": "016035", "元件": "016036",
        "光学光电子": "016037", "消费电子": "016038", "电子化学品": "016039",
        "计算机": "017", "IT服务": "017024", "软件开发": "017025",
        "计算机设备": "017026", "通信": "018", "通信设备": "018027",
        "通信服务": "018028", "电力设备": "011", "电池": "011014",
        "光伏设备": "011015", "有色金属": "006", "化工": "004",
        "新材料": "004005", "化学制品": "004006",
    }

    REPORT_TYPES: Dict[str, int] = {
        "stock": 0, "industry": 1, "strategy": 2, "macro": 3, "morning": 4,
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/report/",
        "Accept": "application/json, text/plain, */*",
    }

    def __init__(self, days_back: int = 7, max_retries: int = 3):
        self.days_back = days_back
        self.session = self._create_session(max_retries)

    def _create_session(self, max_retries: int) -> requests.Session:
        session = requests.Session()
        retry = Retry(total=max_retries, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(self.HEADERS)
        return session

    @property
    def name(self) -> str:
        return "东方财富"

    def search(self, keywords: List[str], page: int = 1, page_size: int = 50) -> List[ReportItem]:
        all_reports, seen_ids = [], set()

        def _add(reports):
            for r in reports:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    all_reports.append(r)

        for kw in self._select_keywords(keywords, 10):
            try:
                _add(self._api_search(keyword=kw, q_type=0, page_size=30))
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"Keyword search '{kw}' failed: {e}")

        for code in list(self._match_codes(keywords))[:5]:
            try:
                _add(self._api_search(industry_code=code, q_type=1, page_size=20))
                time.sleep(0.3)
            except Exception as e:
                logger.debug(f"Industry search ({code}) failed: {e}")

        for rt in ["strategy", "macro"]:
            try:
                _add(self._api_search(q_type=self.REPORT_TYPES[rt], page_size=20))
                time.sleep(0.2)
            except Exception:
                pass

        filtered = self.filter_by_keywords(all_reports, keywords)
        logger.info(f"东方财富: {len(all_reports)} found, {len(filtered)} matched")
        return filtered

    def get_latest(self, page_size: int = 50) -> List[ReportItem]:
        try:
            return self._api_search(q_type=1, page_size=page_size)
        except Exception as e:
            logger.error(f"Get latest failed: {e}")
            return []

    def _select_keywords(self, keywords: List[str], max_count: int) -> List[str]:
        scored = []
        for kw in keywords:
            score = len(kw)
            if kw.isupper() and len(kw) >= 3:
                score += 3
            if any(x in kw for x in ['半导体', '封装', '光刻', '大模型', '算力']):
                score += 3
            scored.append((score, kw))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [kw for _, kw in scored[:max_count]]

    def _match_codes(self, keywords: List[str]) -> set:
        codes = set()
        for kw in keywords:
            for name, code in self.INDUSTRY_CODES.items():
                if kw in name or name in kw:
                    codes.add(code)
        kw_text = " ".join(keywords).lower()
        mappings = {
            ("半导体", "芯片", "封装"): ["016", "016035"],
            ("ai", "人工智能", "大模型", "算力"): ["017", "017025"],
            ("材料", "sic", "gan", "光刻"): ["004005", "016039"],
        }
        for triggers, target_codes in mappings.items():
            if any(w in kw_text for w in triggers):
                codes.update(target_codes)
        return codes

    def _api_search(self, keyword: str = "", industry_code: str = "*",
                    q_type: int = 0, page: int = 1, page_size: int = 30) -> List[ReportItem]:
        params = {
            "industryCode": industry_code, "pageSize": page_size,
            "industry": "*", "rating": "", "ratingChange": "",
            "beginTime": (datetime.now() - timedelta(days=self.days_back)).strftime("%Y-%m-%d"),
            "endTime": datetime.now().strftime("%Y-%m-%d"),
            "pageNo": page, "fields": "", "qType": q_type,
            "orgCode": "", "code": "*", "rcode": "",
            "p": page, "pageNum": page, "pageNumber": page,
            "_": int(time.time() * 1000),
        }
        if keyword:
            params["keyWord"] = keyword

        try:
            resp = self.session.get(self.REPORT_LIST_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return []

        items = data.get("data", []) or []
        return [r for r in (self._parse(item) for item in items) if r]

    def _parse(self, item: dict) -> Optional[ReportItem]:
        info_code = item.get("infoCode", "") or item.get("infocode", "")
        title = item.get("title", "") or item.get("Title", "")
        if not info_code or not title:
            return None

        researcher = item.get("researcher", "") or ""
        if isinstance(researcher, list):
            researcher = ", ".join(str(r) for r in researcher if r)

        publish_date = item.get("publishDate", "") or ""
        if "T" in publish_date:
            publish_date = publish_date.split("T")[0]
        elif " " in publish_date:
            publish_date = publish_date.split(" ")[0]

        summary = item.get("abstract", "") or item.get("stockName", "") or ""
        if isinstance(summary, list):
            summary = ", ".join(str(s) for s in summary)

        return ReportItem(
            id=f"em_{info_code}", title=title.strip(), author=researcher,
            org_name=(item.get("orgSName", "") or "").strip(),
            publish_date=publish_date[:10],
            summary=summary[:300],
            pdf_url=item.get("attachUrl", "") or item.get("pdfUrl", "") or "",
            info_url=self.REPORT_DETAIL_URL.format(info_code),
            industry=item.get("industryName", "") or item.get("indvInduName", "") or "",
            source=self.name,
            rating=item.get("emRatingName", "") or item.get("sRatingName", "") or "",
        )

    def get_pdf_url(self, report: ReportItem) -> str:
        if report.pdf_url:
            return report.pdf_url
        try:
            resp = self.session.get(report.info_url, timeout=10)
            resp.raise_for_status()
            for pattern in [r'(https?://pdf\.dfcfw\.com/pdf/[^"\'>\s]+\.pdf)', r'href="([^"]+\.pdf)"']:
                m = re.search(pattern, resp.text)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return ""
