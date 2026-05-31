"""AKShare research report source (optional)
Requires: pip install akshare
Reference: https://github.com/akfamily/akshare
"""
import logging
from typing import List
from .base import ReportSource, ReportItem

logger = logging.getLogger(__name__)

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


class AKShareSource(ReportSource):
    @property
    def name(self) -> str:
        return "AKShare"

    @property
    def is_available(self) -> bool:
        return AKSHARE_AVAILABLE

    def search(self, keywords: List[str], page: int = 1, page_size: int = 50) -> List[ReportItem]:
        if not AKSHARE_AVAILABLE:
            return []
        reports = []
        try:
            reports.extend(self._get_industry(page_size))
        except Exception as e:
            logger.error(f"AKShare industry failed: {e}")
        try:
            reports.extend(self._get_stock(page_size))
        except Exception as e:
            logger.error(f"AKShare stock failed: {e}")
        return self.filter_by_keywords(reports, keywords)

    def get_latest(self, page_size: int = 50) -> List[ReportItem]:
        if not AKSHARE_AVAILABLE:
            return []
        try:
            return self._get_industry(page_size)
        except Exception:
            return []

    def _get_industry(self, limit: int = 50) -> List[ReportItem]:
        df = ak.stock_institute_report_em(symbol="全部")
        if df is None or df.empty:
            return []
        reports = []
        for _, row in df.head(limit).iterrows():
            title = str(row.get("报告名称", "") or "")
            if title:
                reports.append(ReportItem(
                    id=f"ak_ind_{row.get('序号', hash(title))}",
                    title=title, author=str(row.get("研究员", "") or ""),
                    org_name=str(row.get("机构", "") or ""),
                    publish_date=str(row.get("日期", "") or "")[:10],
                    industry=str(row.get("行业", "") or ""),
                    source=self.name, rating=str(row.get("评级", "") or ""),
                ))
        return reports

    def _get_stock(self, limit: int = 50) -> List[ReportItem]:
        df = ak.stock_research_report_em(symbol="全部")
        if df is None or df.empty:
            return []
        reports = []
        for _, row in df.head(limit).iterrows():
            title = str(row.get("报告名称", "") or "")
            if title:
                reports.append(ReportItem(
                    id=f"ak_stk_{row.get('序号', hash(title))}",
                    title=title, author=str(row.get("研究员", "") or ""),
                    org_name=str(row.get("机构", "") or ""),
                    publish_date=str(row.get("日期", "") or "")[:10],
                    source=self.name, rating=str(row.get("最新评级", "") or ""),
                ))
        return reports
