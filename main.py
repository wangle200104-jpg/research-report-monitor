#!/usr/bin/env python3
"""Research Report Monitor - CLI entry point"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.monitor import ReportMonitor


def main():
    parser = argparse.ArgumentParser(description="Research Report Monitor")
    parser.add_argument("--daemon", "-d", action="store_true", help="Daemon mode (scheduled checks)")
    parser.add_argument("--search", "-s", nargs="?", const="", default=None, help="Search mode")
    parser.add_argument("--config", "-c", default=None, help="Config file path")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup old history")
    parser.add_argument("--list-history", action="store_true", help="List download history")
    parser.add_argument("--no-download", action="store_true", help="Search only, no download")
    args = parser.parse_args()

    try:
        monitor = ReportMonitor(config_path=args.config)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.no_download:
        monitor.config.setdefault("download", {})["download_pdf"] = False

    if args.daemon:
        monitor.run_daemon()
    elif args.search is not None:
        monitor.search_interactive(args.search if args.search else None)
    elif args.cleanup:
        removed = monitor.history.cleanup()
        print(f"Cleaned {removed} records, {monitor.history.count()} remaining")
    elif args.list_history:
        from rich.console import Console
        from rich.table import Table
        c = Console()
        h = monitor.history.history
        if not h:
            c.print("[dim]No history[/dim]")
            return
        table = Table(title=f"Download History ({len(h)} total)")
        table.add_column("Time", width=20)
        table.add_column("Title", width=50)
        items = sorted(h.items(), key=lambda x: x[1].get("downloaded_at", ""), reverse=True)[:20]
        for _, info in items:
            table.add_row(info.get("downloaded_at", "")[:19], info.get("title", "")[:48])
        c.print(table)
    else:
        monitor.check_once()


if __name__ == "__main__":
    main()
