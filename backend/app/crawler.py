"""
Unified crawling interface for GrantScope content extraction.

Supports three extraction backends:
- **trafilatura** (default): Lightweight, Railway-compatible. Uses httpx for fetching
  and trafilatura for HTML-to-text extraction. Best for standard web pages.
- **crawl4ai** (optional): Playwright-based JS rendering for dynamic/SPA pages.
  Enabled via CRAWLER_ENGINE=crawl4ai env var. Falls back to trafilatura if unavailable.
- **pymupdf**: Automatic PDF text extraction when URL points to a PDF document.

Public API:
    crawl_url(url, timeout) -> CrawlResult
    crawl_urls(urls, max_concurrent, timeout) -> List[CrawlResult]
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import trafilatura

# Optional: pymupdf for PDF extraction
try:
    import fitz  # PyMuPDF

    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False

# Optional: crawl4ai for JS-rendered pages
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

    _HAS_CRAWL4AI = True
except ImportError:
    _HAS_CRAWL4AI = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CRAWLER_ENGINE: str = os.environ.get("CRAWLER_ENGINE", "trafilatura")
CRAWLER_TIMEOUT: int = int(os.environ.get("CRAWLER_TIMEOUT", "30"))
CRAWLER_MAX_CONTENT_SIZE: int = int(os.environ.get("CRAWLER_MAX_CONTENT_SIZE", "50000"))

_MAX_PDF_PAGES: int = 20
_MAX_RETRY_ATTEMPTS: int = 2
_DOMAIN_CONCURRENCY: int = 3

# ---------------------------------------------------------------------------
# Module-level resources
# ---------------------------------------------------------------------------

# Reusable thread pool for blocking I/O (trafilatura is synchronous)
_executor = ThreadPoolExecutor(max_workers=5)

# Per-domain semaphores for rate limiting (lazily populated)
_domain_semaphores: Dict[str, asyncio.Semaphore] = {}
_domain_lock = asyncio.Lock()

# Default headers to mimic a regular browser
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CrawlResult:
    """Result of crawling a single URL."""

    url: str
    title: Optional[str]
    markdown: Optional[str]
    raw_html: Optional[str]
    content_type: str
    status_code: int
    success: bool
    error: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: str = ""
    word_count: int = 0
    source_engine: str = ""

    def __post_init__(self) -> None:
        if not self.extracted_at:
            self.extracted_at = datetime.now(timezone.utc).isoformat()
        if self.markdown and self.word_count == 0:
            self.word_count = len(self.markdown.split())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_domain(url: str) -> str:
    """Extract domain from a URL for rate-limiting purposes."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return "unknown"


async def _get_domain_semaphore(domain: str) -> asyncio.Semaphore:
    """Return (or create) a per-domain semaphore for concurrency control."""
    if domain not in _domain_semaphores:
        async with _domain_lock:
            # Double-check after acquiring lock
            if domain not in _domain_semaphores:
                _domain_semaphores[domain] = asyncio.Semaphore(_DOMAIN_CONCURRENCY)
    return _domain_semaphores[domain]


def _is_pdf_url(url: str) -> bool:
    """Heuristic check: does the URL path end with .pdf?"""
    try:
        path = urlparse(url).path.lower()
        return path.endswith(".pdf")
    except Exception:
        return False


def _truncate_content(text: str, max_size: int = CRAWLER_MAX_CONTENT_SIZE) -> str:
    """Truncate content to max_size characters, appending a notice."""
    if len(text) <= max_size:
        return text
    truncated = text[:max_size]
    # Try to break at a paragraph or sentence boundary
    for boundary in ["\n\n", "\n", ". ", " "]:
        last_pos = truncated.rfind(boundary)
        if last_pos > max_size * 0.8:
            truncated = truncated[: last_pos + len(boundary)]
            break
    return truncated + "\n\n[Content truncated — exceeded maximum length]"


def _make_error_result(
    url: str,
    error: str,
    status_code: int = 0,
    content_type: str = "",
    engine: str = "",
) -> CrawlResult:
    """Build a CrawlResult for a failed extraction."""
    return CrawlResult(
        url=url,
        title=None,
        markdown=None,
        raw_html=None,
        content_type=content_type,
        status_code=status_code,
        success=False,
        error=error,
        source_engine=engine,
    )


# ---------------------------------------------------------------------------
# Trafilatura backend
# ---------------------------------------------------------------------------


def _trafilatura_extract_sync(
    html: str,
) -> tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Synchronous trafilatura extraction — designed to run in a thread pool.

    Returns:
        (text, title, metadata_dict)
    """
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        deduplicate=True,
        output_format="txt",
    )

    meta = trafilatura.extract_metadata(html)
    title = meta.title if meta else None
    meta_dict: Dict[str, Any] = {}
    if meta:
        if meta.author:
            meta_dict["author"] = meta.author
        if meta.date:
            meta_dict["date"] = meta.date
        if meta.sitename:
            meta_dict["sitename"] = meta.sitename
        if meta.description:
            meta_dict["description"] = meta.description
        if meta.categories:
            meta_dict["categories"] = meta.categories
        if meta.tags:
            meta_dict["tags"] = meta.tags

    return text, title, meta_dict


async def _extract_with_trafilatura(
    url: str, timeout: int = CRAWLER_TIMEOUT
) -> CrawlResult:
    """
    Fetch a URL with httpx and extract content using trafilatura.

    This is the default, lightweight extraction path.
    """
    html: Optional[str] = None
    status_code: int = 0
    content_type: str = ""

    try:
        async with httpx.AsyncClient(
            timeout=float(timeout),
            headers=_DEFAULT_HEADERS,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            response = await client.get(url)
            status_code = response.status_code
            content_type = response.headers.get("content-type", "")

            if status_code >= 400:
                return _make_error_result(
                    url=url,
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                    content_type=content_type,
                    engine="trafilatura",
                )

            html = response.text

    except httpx.TimeoutException:
        return _make_error_result(
            url=url,
            error=f"Request timed out after {timeout}s",
            engine="trafilatura",
        )
    except httpx.HTTPError as exc:
        return _make_error_result(
            url=url,
            error=f"HTTP error: {exc}",
            engine="trafilatura",
        )

    if not html:
        return _make_error_result(
            url=url,
            error="Empty response body",
            status_code=status_code,
            content_type=content_type,
            engine="trafilatura",
        )

    # Run trafilatura in thread pool (it's synchronous and CPU-bound)
    loop = asyncio.get_running_loop()
    try:
        text, title, meta_dict = await loop.run_in_executor(
            _executor, _trafilatura_extract_sync, html
        )
    except Exception as exc:
        logger.warning("Trafilatura extraction error for %s: %s", url, exc)
        return _make_error_result(
            url=url,
            error=f"Extraction error: {exc}",
            status_code=status_code,
            content_type=content_type,
            engine="trafilatura",
        )

    if not text:
        return _make_error_result(
            url=url,
            error="Trafilatura extracted no content (paywall or empty page)",
            status_code=status_code,
            content_type=content_type,
            engine="trafilatura",
        )

    text = _truncate_content(text)

    return CrawlResult(
        url=url,
        title=title,
        markdown=text,
        raw_html=None,  # Omit to save memory; callers rarely need it
        content_type=content_type,
        status_code=status_code,
        success=True,
        error=None,
        metadata=meta_dict,
        source_engine="trafilatura",
    )


# ---------------------------------------------------------------------------
# Crawl4AI backend (optional)
# ---------------------------------------------------------------------------


async def _extract_with_crawl4ai(
    url: str, timeout: int = CRAWLER_TIMEOUT
) -> CrawlResult:
    """
    Extract content using crawl4ai with Playwright for JS-rendered pages.

    Falls back to trafilatura if crawl4ai is not installed.
    """
    if not _HAS_CRAWL4AI:
        logger.info("crawl4ai not installed, falling back to trafilatura for %s", url)
        return await _extract_with_trafilatura(url, timeout)

    try:
        browser_config = BrowserConfig(headless=True, text_mode=True)
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=timeout * 1000,  # crawl4ai uses milliseconds
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

        if not result.success:
            error_msg = getattr(result, "error_message", "Unknown crawl4ai error")
            return _make_error_result(
                url=url,
                error=f"crawl4ai failed: {error_msg}",
                status_code=getattr(result, "status_code", 0),
                engine="crawl4ai",
            )

        # Prefer fit_markdown (cleaned) over raw_markdown
        markdown_content: Optional[str] = None
        if result.markdown:
            markdown_content = getattr(
                result.markdown, "fit_markdown", None
            ) or getattr(result.markdown, "raw_markdown", None)
        # Fallback: some versions expose markdown as a string directly
        if not markdown_content and isinstance(result.markdown, str):
            markdown_content = result.markdown

        if not markdown_content:
            return _make_error_result(
                url=url,
                error="crawl4ai returned no markdown content",
                status_code=getattr(result, "status_code", 200),
                engine="crawl4ai",
            )

        markdown_content = _truncate_content(markdown_content)

        # Extract metadata from crawl4ai result
        meta_dict: Dict[str, Any] = {}
        if hasattr(result, "metadata") and result.metadata:
            if isinstance(result.metadata, dict):
                meta_dict = result.metadata

        title = meta_dict.get("title") or getattr(result, "title", None)

        return CrawlResult(
            url=url,
            title=title,
            markdown=markdown_content,
            raw_html=None,
            content_type=getattr(result, "content_type", "text/html"),
            status_code=getattr(result, "status_code", 200),
            success=True,
            error=None,
            metadata=meta_dict,
            source_engine="crawl4ai",
        )

    except ImportError:
        logger.warning("crawl4ai import failed at runtime, falling back to trafilatura")
        return await _extract_with_trafilatura(url, timeout)
    except Exception as exc:
        logger.warning("crawl4ai error for %s: %s", url, exc)
        return _make_error_result(
            url=url,
            error=f"crawl4ai error: {exc}",
            engine="crawl4ai",
        )


# ---------------------------------------------------------------------------
# PDF backend
# ---------------------------------------------------------------------------


async def _extract_pdf(url: str, timeout: int = CRAWLER_TIMEOUT) -> CrawlResult:
    """
    Download a PDF from a URL and extract text using PyMuPDF (fitz).

    For large PDFs (>20 pages), extracts only the first 20 pages plus
    the table of contents. Content is capped at CRAWLER_MAX_CONTENT_SIZE chars.
    """
    if not _HAS_PYMUPDF:
        return _make_error_result(
            url=url,
            error="PyMuPDF (fitz) is not installed — cannot extract PDF",
            engine="pymupdf",
        )

    pdf_bytes: bytes = b""
    status_code: int = 0
    content_type: str = "application/pdf"

    # Download the PDF
    try:
        async with httpx.AsyncClient(
            timeout=float(timeout),
            headers=_DEFAULT_HEADERS,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            response = await client.get(url)
            status_code = response.status_code
            content_type = response.headers.get("content-type", "application/pdf")

            if status_code >= 400:
                return _make_error_result(
                    url=url,
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                    content_type=content_type,
                    engine="pymupdf",
                )

            pdf_bytes = response.content

    except httpx.TimeoutException:
        return _make_error_result(
            url=url,
            error=f"PDF download timed out after {timeout}s",
            engine="pymupdf",
        )
    except httpx.HTTPError as exc:
        return _make_error_result(
            url=url,
            error=f"PDF download error: {exc}",
            engine="pymupdf",
        )

    if not pdf_bytes:
        return _make_error_result(
            url=url,
            error="Empty PDF response",
            status_code=status_code,
            content_type=content_type,
            engine="pymupdf",
        )

    # Extract text in thread pool (fitz is CPU-bound)
    loop = asyncio.get_running_loop()
    try:
        text, title, meta_dict = await loop.run_in_executor(
            _executor, _pymupdf_extract_sync, pdf_bytes, url
        )
    except Exception as exc:
        logger.warning("PDF extraction error for %s: %s", url, exc)
        return _make_error_result(
            url=url,
            error=f"PDF extraction error: {exc}",
            status_code=status_code,
            content_type=content_type,
            engine="pymupdf",
        )

    if not text:
        return _make_error_result(
            url=url,
            error="No text could be extracted from PDF",
            status_code=status_code,
            content_type=content_type,
            engine="pymupdf",
        )

    text = _truncate_content(text)

    return CrawlResult(
        url=url,
        title=title,
        markdown=text,
        raw_html=None,
        content_type=content_type,
        status_code=status_code,
        success=True,
        error=None,
        metadata=meta_dict,
        source_engine="pymupdf",
    )


def _pymupdf_extract_sync(
    pdf_bytes: bytes, url: str
) -> tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Synchronous PDF text extraction with PyMuPDF — runs in thread pool.

    Returns:
        (text, title, metadata_dict)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = len(doc)

        # Extract metadata
        meta_dict: Dict[str, Any] = {
            "total_pages": total_pages,
        }
        pdf_meta = doc.metadata
        if pdf_meta:
            for key in ("author", "creator", "producer", "subject", "keywords"):
                val = pdf_meta.get(key)
                if val:
                    meta_dict[key] = val

        # Determine title from PDF metadata or first-page content
        title: Optional[str] = pdf_meta.get("title") if pdf_meta else None
        if not title or len(title.strip()) < 3:
            title = None

        # Extract table of contents if available
        toc = doc.get_toc()
        toc_text = ""
        if toc:
            toc_lines = ["## Table of Contents\n"]
            for level, heading, page_num in toc[:50]:  # Cap at 50 entries
                indent = "  " * (level - 1)
                toc_lines.append(f"{indent}- {heading} (p. {page_num})")
            toc_text = "\n".join(toc_lines) + "\n\n"

        # Determine how many pages to extract
        pages_to_extract = min(total_pages, _MAX_PDF_PAGES)
        was_truncated = total_pages > _MAX_PDF_PAGES

        # Extract text page by page
        text_parts: list[str] = []
        if toc_text:
            text_parts.append(toc_text)

        for page_idx in range(pages_to_extract):
            page = doc[page_idx]
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                text_parts.append(f"--- Page {page_idx + 1} ---\n{page_text.strip()}")

        if was_truncated:
            text_parts.append(
                f"\n[PDF truncated — showing {pages_to_extract} of {total_pages} pages]"
            )
            meta_dict["truncated"] = True
            meta_dict["pages_extracted"] = pages_to_extract

        # If no title from metadata, try first line of content
        if not title and text_parts:
            # Look at first non-TOC text
            for part in text_parts:
                if part.startswith("##"):
                    continue
                first_line = part.split("\n")[0].replace("--- Page 1 ---", "").strip()
                if first_line and 5 <= len(first_line) <= 200:
                    title = first_line
                    break

        full_text = "\n\n".join(text_parts)
        return full_text, title, meta_dict
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# URL type detection
# ---------------------------------------------------------------------------


async def _is_pdf_content(url: str, timeout: int = 10) -> bool:
    """
    Determine if a URL points to a PDF by checking the URL path extension
    first, then falling back to a HEAD request to check Content-Type.
    """
    if _is_pdf_url(url):
        return True

    # HEAD request to check Content-Type without downloading the body
    try:
        async with httpx.AsyncClient(
            timeout=float(timeout),
            headers=_DEFAULT_HEADERS,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            response = await client.head(url)
            ct = response.headers.get("content-type", "").lower()
            return "application/pdf" in ct
    except (httpx.HTTPError, httpx.TimeoutException):
        # If HEAD fails, proceed with HTML extraction — it will fail gracefully
        return False


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


async def _crawl_with_retry(
    url: str,
    timeout: int,
    extractor: str,
) -> CrawlResult:
    """
    Attempt extraction up to _MAX_RETRY_ATTEMPTS times with exponential backoff.
    """
    last_result: Optional[CrawlResult] = None

    for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
        if attempt > 1:
            backoff = 2 ** (attempt - 1)  # 2s, 4s, ...
            logger.debug("Retry %d for %s (backoff %ds)", attempt, url, backoff)
            await asyncio.sleep(backoff)

        # Determine extraction method
        is_pdf = await _is_pdf_content(url, timeout=min(timeout, 10))

        if is_pdf:
            result = await _extract_pdf(url, timeout)
        elif extractor == "crawl4ai":
            result = await _extract_with_crawl4ai(url, timeout)
        else:
            result = await _extract_with_trafilatura(url, timeout)

        if result.success:
            return result

        last_result = result
        logger.debug(
            "Attempt %d/%d failed for %s: %s",
            attempt,
            _MAX_RETRY_ATTEMPTS,
            url,
            result.error,
        )

    # All attempts exhausted
    assert last_result is not None
    logger.warning(
        "All %d attempts failed for %s: %s",
        _MAX_RETRY_ATTEMPTS,
        url,
        last_result.error,
    )
    return last_result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def crawl_url(url: str, timeout: int = CRAWLER_TIMEOUT) -> CrawlResult:
    """
    Crawl a single URL and extract its content.

    Automatically selects the appropriate extraction backend:
    - PDF files use PyMuPDF
    - HTML pages use trafilatura (default) or crawl4ai (if CRAWLER_ENGINE=crawl4ai)

    Includes built-in retry (2 attempts with exponential backoff) and
    per-domain rate limiting (max 3 concurrent requests per domain).

    Args:
        url: The URL to crawl.
        timeout: Request timeout in seconds (default from CRAWLER_TIMEOUT env var).

    Returns:
        CrawlResult with extracted content or error details.
    """
    if not url or not url.startswith(("http://", "https://")):
        return _make_error_result(
            url=url or "",
            error="Invalid URL: must start with http:// or https://",
        )

    domain = _get_domain(url)
    semaphore = await _get_domain_semaphore(domain)

    async with semaphore:
        logger.info("Crawling %s (engine=%s)", url, CRAWLER_ENGINE)
        start_time = time.monotonic()

        result = await _crawl_with_retry(url, timeout, CRAWLER_ENGINE)

        elapsed = time.monotonic() - start_time
        if result.success:
            logger.info(
                "Crawled %s — %d words in %.1fs (engine=%s)",
                url,
                result.word_count,
                elapsed,
                result.source_engine,
            )
        else:
            logger.warning(
                "Failed to crawl %s after %.1fs: %s", url, elapsed, result.error
            )

        return result


async def crawl_urls(
    urls: List[str],
    max_concurrent: int = 5,
    timeout: int = CRAWLER_TIMEOUT,
) -> List[CrawlResult]:
    """
    Crawl multiple URLs concurrently with controlled parallelism.

    Results are returned in the same order as the input URLs.
    Failed URLs receive a CrawlResult with success=False rather than
    raising exceptions.

    Args:
        urls: List of URLs to crawl.
        max_concurrent: Maximum number of concurrent crawl operations.
        timeout: Per-request timeout in seconds.

    Returns:
        List of CrawlResult objects in the same order as input URLs.
    """
    if not urls:
        return []

    logger.info("Batch crawling %d URLs (max_concurrent=%d)", len(urls), max_concurrent)
    global_semaphore = asyncio.Semaphore(max_concurrent)

    async def _crawl_one(url: str) -> CrawlResult:
        async with global_semaphore:
            try:
                return await crawl_url(url, timeout)
            except Exception as exc:
                logger.warning("Unexpected error crawling %s: %s", url, exc)
                return _make_error_result(
                    url=url,
                    error=f"Unexpected error: {exc}",
                )

    # Preserve input order using gather
    results = await asyncio.gather(*[_crawl_one(u) for u in urls])

    succeeded = sum(1 for r in results if r.success)
    logger.info("Batch crawl complete: %d/%d succeeded", succeeded, len(urls))

    return list(results)
