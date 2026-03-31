"""Test page endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()

TEST_PAGE_PATH = Path(__file__).resolve().parent.parent.parent / "static" / "test" / "index.html"


@router.get("/test", response_class=HTMLResponse)
async def test_page() -> FileResponse:
    """Serve test page for manual API testing.

    Returns an HTML page with a form for testing the agent API.
    No authentication required for development/testing.
    """
    return FileResponse(TEST_PAGE_PATH)
