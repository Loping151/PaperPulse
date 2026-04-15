"""Simple FastAPI server for Paper Pulse web frontend."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", BASE_DIR / "reports"))
JSON_DIR = REPORTS_DIR / "json"
WEB_DIR = BASE_DIR / "web"
PDF_CACHE_DIR = Path(os.getenv("PDF_CACHE_DIR", BASE_DIR / "cache" / "pdfs"))

app = FastAPI(title="Paper Pulse Web")


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def _list_report_files() -> list[Path]:
    if not JSON_DIR.exists():
        return []
    files = list(JSON_DIR.glob("paper-pulse-*.json"))
    return sorted(files, reverse=True)


def _date_from_filename(path: Path) -> Optional[str]:
    name = path.stem
    if name.startswith("paper-pulse-"):
        return name.replace("paper-pulse-", "")
    return None


def _load_report(date: Optional[str] = None) -> dict:
    if date:
        # Try new naming first, then old
        target = JSON_DIR / f"paper-pulse-{date}.json"
        if not target.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        return json.loads(target.read_text(encoding="utf-8"))

    files = _list_report_files()
    if not files:
        raise HTTPException(status_code=404, detail="No reports available")
    return json.loads(files[0].read_text(encoding="utf-8"))


def _sanitize_paper_id(paper_id: str) -> str:
    return str(paper_id or "").strip().replace("/", "_").replace(":", "_")


def _sanitize_source(source: Optional[str]) -> str:
    if not source:
        return ""
    return str(source).strip().replace(" ", "_").replace("/", "_").lower()


def _find_cached_pdf(
    paper_id: str,
    date: Optional[str] = None,
    source: Optional[str] = None,
) -> Optional[Path]:
    """Resolve a cached PDF path using known cache layouts."""
    safe_id = _sanitize_paper_id(paper_id)
    if not safe_id or not PDF_CACHE_DIR.exists():
        return None

    safe_source = _sanitize_source(source)
    candidates: list[Path] = []

    # Preferred layout: cache/pdfs/{date}/{source}/{paper_id}.pdf
    if date and safe_source:
        candidates.append(PDF_CACHE_DIR / str(date) / safe_source / f"{safe_id}.pdf")
    # Other supported layouts
    if date:
        candidates.append(PDF_CACHE_DIR / str(date) / f"{safe_id}.pdf")
    if safe_source:
        candidates.append(PDF_CACHE_DIR / safe_source / f"{safe_id}.pdf")
    candidates.append(PDF_CACHE_DIR / f"{safe_id}.pdf")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate

    # Fallback: search recursively for legacy/variant layouts.
    # Triggered only when direct candidates miss.
    for matched in PDF_CACHE_DIR.rglob(f"{safe_id}.pdf"):
        if matched.is_file():
            return matched

    return None


@app.get("/")
def index():
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/dates")
def list_dates():
    dates = []
    for path in _list_report_files():
        date = _date_from_filename(path)
        if date:
            dates.append(date)
    return dates


@app.get("/api/report")
def get_report(date: Optional[str] = None):
    return _load_report(date)


@app.get("/api/local-pdf")
def get_local_pdf(
    paper_id: str,
    date: Optional[str] = None,
    source: Optional[str] = None,
    fallback_url: Optional[str] = None,
):
    """
    Open locally cached PDF when available, otherwise redirect to fallback URL.
    """
    pdf_path = _find_cached_pdf(paper_id=paper_id, date=date, source=source)
    if pdf_path:
        return FileResponse(str(pdf_path), media_type="application/pdf")

    if fallback_url:
        safe = fallback_url.strip()
        if safe.startswith("http://") or safe.startswith("https://"):
            return RedirectResponse(url=safe, status_code=307)

    raise HTTPException(status_code=404, detail="Local PDF not found")


@app.get("/favicon.ico")
def favicon():
    icon_path = WEB_DIR / "favicon.ico"
    if icon_path.exists():
        return FileResponse(str(icon_path))
    raise HTTPException(status_code=404, detail="Not found")
