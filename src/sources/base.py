"""Data source base class / 数据源基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class ReportItem:
    """Research report item / 研报条目"""
    id: str
    title: str
    author: str = ""
    org_name: str = ""
    publish_date: str = ""
    summary: str = ""
    pdf_url: str = ""
    info_url: str = ""
    industry: str = ""
    keywords: List[str] = field(default_factory=list)
    source: str = ""
    rating: str = ""

    def __str__(self):
        return f"[{self.publish_date}] [{self.org_name}] {self.title}"


class ReportSource(ABC):
    """Abstract base class for report data sources"""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def search(self, keywords: List[str], page: int = 1, page_size: int = 50) -> List[ReportItem]:
        pass

    @abstractmethod
    def get_latest(self, page_size: int = 50) -> List[ReportItem]:
        pass

    def filter_by_keywords(self, reports: List[ReportItem], keywords: List[str]) -> List[ReportItem]:
        """Filter reports by keyword matching in title/summary/industry"""
        filtered = []
        for report in reports:
            matched_keywords = []
            text = f"{report.title} {report.summary} {report.industry}".lower()
            for kw in keywords:
                if kw.lower() in text:
                    matched_keywords.append(kw)
            if matched_keywords:
                report.keywords = matched_keywords
                filtered.append(report)
        return filtered
