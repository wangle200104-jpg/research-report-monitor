"""Core monitor scheduler with Rich CLI output"""
import os
import sys
import logging
import time
from datetime import datetime
from typing import List

import schedule
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config_loader import load_config, get_keywords, get_download_dir
from .sources.eastmoney import EastMoneySource
from .sources.cninfo import CninfoSource
from .sources.gelonghui import GelonghuiSource
from .sources.rss_source import RSSSource
from .sources.akshare_source import AKShareSource
from .sources.base import ReportItem
from .downloader import ReportDownloader
from .history import DownloadHistory

console = Console()
logger = logging.getLogger(__name__)


class ReportMonitor:
    def __init__(self, config_path: str = None):
        self.config = load_config(config_path)
        self.keywords = get_keywords(self.config)
        self.output_dir = get_download_dir(self.config)
        self._setup_logging()
        self.sources = self._init_sources()
        dl_cfg = self.config.get("download", {})
        self.downloader = ReportDownloader(
            output_dir=self.output_dir,
            max_concurrent=dl_cfg.get("max_concurrent", 3),
            max_file_size_mb=dl_cfg.get("max_file_size_mb", 50)
        )
        dedup_cfg = self.config.get("dedup", {})
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        hf = dedup_cfg.get("history_file", "./data/download_history.json")
        if not os.path.isabs(hf):
            hf = os.path.join(base_dir, hf)
        self.history = DownloadHistory(history_file=hf, keep_days=dedup_cfg.get("keep_days", 90))

    def _init_sources(self) -> list:
        sources = []
        cfg = self.config.get("sources", {})
        if cfg.get("eastmoney", {}).get("enabled", True):
            sources.append(EastMoneySource())
        if cfg.get("cninfo", {}).get("enabled", True):
            sources.append(CninfoSource())
        if cfg.get("gelonghui", {}).get("enabled", False):
            sources.append(GelonghuiSource())
        rss_cfg = cfg.get("rss", {})
        if rss_cfg.get("enabled", False):
            sources.append(RSSSource(config=rss_cfg))
        if cfg.get("akshare", {}).get("enabled", False):
            ak = AKShareSource()
            if ak.is_available:
                sources.append(ak)
        if not sources:
            sources.append(EastMoneySource())
        return sources

    def _setup_logging(self):
        log_level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        log_cfg = self.config.get("notification", {})
        log_file = log_cfg.get("log_file", "./logs/monitor.log")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.isabs(log_file):
            log_file = os.path.join(base_dir, log_file)
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        logging.basicConfig(
            level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)]
        )

    def check_once(self) -> List[ReportItem]:
        console.print(Panel(
            f"[bold cyan]Starting report check[/bold cyan]\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Sources: {', '.join(s.name for s in self.sources)}\n"
            f"Keywords: {', '.join(self.keywords[:8])}{'...' if len(self.keywords) > 8 else ''}",
            title="Research Report Monitor", border_style="blue"
        ))
        all_new = []
        for source in self.sources:
            try:
                console.print(f"\n[yellow]> Fetching from [{source.name}]...[/yellow]")
                reports = source.search(self.keywords, page_size=50)
                if not reports:
                    console.print(f"  [dim]No matches found[/dim]")
                    continue
                new = [r for r in reports if not self.history.is_downloaded(r.id)]
                if not new:
                    console.print(f"  [dim]No new reports ({len(reports)} already seen)[/dim]")
                    continue
                console.print(f"  [green]Found {len(new)} new reports![/green]")
                all_new.extend(new)
            except Exception as e:
                console.print(f"  [red]Failed: {e}[/red]")

        if all_new:
            all_new.sort(key=lambda r: r.publish_date or "", reverse=True)
            self._display(all_new)
            self._process(all_new)
        else:
            console.print("\n[dim]No new reports found[/dim]")
        return all_new

    def _display(self, reports: List[ReportItem]):
        table = Table(title=f"New Reports ({len(reports)})", show_lines=True)
        table.add_column("Date", style="cyan", width=12)
        table.add_column("Source", style="magenta", width=8)
        table.add_column("Org", style="yellow", width=12)
        table.add_column("Title", style="white", width=40)
        table.add_column("Keywords", style="green", width=18)
        table.add_column("PDF", width=4)
        for r in reports[:30]:
            table.add_row(r.publish_date, r.source[:6], (r.org_name or "-")[:10],
                          r.title[:38] + ("..." if len(r.title) > 38 else ""),
                          ", ".join(r.keywords[:3])[:16], "Y" if r.pdf_url else "N")
        console.print(table)

    def _process(self, reports: List[ReportItem]):
        if self.config.get("download", {}).get("download_pdf", True):
            results = self.downloader.batch_download(reports)
            for r in reports:
                self.history.add(r.id, r.title, r.info_url)
            if results["success"]:
                console.print(f"\n[green]Downloaded {len(results['success'])} reports to: {self.output_dir}[/green]")
            if results["failed"]:
                console.print(f"[red]Failed: {len(results['failed'])}[/red]")
            if results["skipped"]:
                console.print(f"[dim]Skipped: {len(results['skipped'])} (no PDF)[/dim]")
        else:
            for r in reports:
                self.history.add(r.id, r.title, r.info_url)

    def run_daemon(self):
        sched_cfg = self.config.get("schedule", {})
        check_times = sched_cfg.get("check_times", ["08:30", "12:00", "18:00"])
        interval = sched_cfg.get("interval_minutes", 0)
        console.print(Panel(
            f"[bold green]Daemon started[/bold green]\nSources: {', '.join(s.name for s in self.sources)}\n"
            f"Check times: {', '.join(check_times)}\n[dim]Press Ctrl+C to stop[/dim]",
            title="Daemon Mode", border_style="green"
        ))
        if interval > 0:
            schedule.every(interval).minutes.do(self.check_once)
        else:
            for t in check_times:
                schedule.every().day.at(t).do(self.check_once)
        self.check_once()
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped[/yellow]")

    def search_interactive(self, keyword: str = None):
        if keyword is None:
            keyword = input("Enter keywords (space-separated): ").strip()
        if not keyword:
            console.print("[red]Keywords cannot be empty[/red]")
            return
        kws = keyword.split()
        console.print(f"\n[cyan]Searching: {', '.join(kws)}[/cyan]\n")
        all_reports = []
        for source in self.sources:
            try:
                reports = source.search(kws)
                if reports:
                    all_reports.extend(reports)
                    console.print(f"  [{source.name}] found {len(reports)}")
            except Exception as e:
                console.print(f"  [{source.name}] failed: {e}")
        if all_reports:
            seen, unique = set(), []
            for r in all_reports:
                if r.id not in seen:
                    seen.add(r.id)
                    unique.append(r)
            unique.sort(key=lambda r: r.publish_date or "", reverse=True)
            self._display(unique)
        else:
            console.print("[dim]No results[/dim]")
