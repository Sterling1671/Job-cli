"""
job_scraper.py

General-purpose job description scraper that handles JavaScript-rendered pages.
Requires: pip install playwright && playwright install chromium

Usage:
    from job_scraper import get_url_content
    text = get_url_content("https://...")
"""

import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# CSS selectors that typically wrap job description content.
# Tried in order; first match wins.
JOB_CONTENT_SELECTORS = [
    # Ultipro / UKG
    "[class*='opportunity-detail']",
    "[id*='opportunityDetail']",
    # Greenhouse
    "#content",
    ".job__description",
    # Lever
    ".posting-description",
    ".posting",
    # Workday
    "[data-automation-id='jobPostingDescription']",
    # iCIMS
    "[id*='iCIMS_JobContent']",
    ".iCIMS_JobContent",
    # SmartRecruiters
    ".job-description",
    "[class*='jobDescription']",
    # LinkedIn
    ".description__text",
    # Indeed
    "#jobDescriptionText",
    # Taleo / Oracle
    "[id*='JDContent']",
    # ADP
    "[class*='jobDescription']",
    # Generic fallbacks (ordered from most to least specific)
    "article",
    "main",
    "[role='main']",
    ".content",
    "#content",
    "body",
]

# Boilerplate tags to remove before extracting text
NOISE_TAGS = [
    "script", "style", "noscript", "iframe",
    "nav", "header", "footer",
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
    ".cookie-banner", "#cookie-banner",
    ".site-header", ".site-footer",
    ".breadcrumb", ".breadcrumbs",
    ".social-share", ".share-links",
]

MAX_CHARS = 24_000  # ~8k tokens at ~3 chars/token


def get_url_content(url: str) -> str:
    """
    Fetch and return the job description text from a URL.

    Handles JavaScript-rendered pages via a headless Chromium browser.
    Aggressively strips boilerplate so the result fits within an LLM context window.

    Args:
        url: Full URL of the job posting.

    Returns:
        Cleaned plain-text job description, truncated to ~8k tokens if needed.

    Raises:
        RuntimeError: If the page could not be loaded or no content found.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightTimeout:
            raise RuntimeError(f"Page load timed out: {url}")

        # Wait for JS to hydrate — poll until body text grows meaningfully
        try:
            page.wait_for_function(
                "document.body.innerText.trim().length > 400",
                timeout=15_000,
            )
        except PlaywrightTimeout:
            pass  # Proceed anyway; static pages are fine

        # Remove noise elements from the DOM before extracting text
        for selector in NOISE_TAGS:
            try:
                page.eval_on_selector_all(
                    selector,
                    "els => els.forEach(el => el.remove())",
                )
            except Exception:
                pass

        # Try each content selector in priority order
        raw_text = ""
        for selector in JOB_CONTENT_SELECTORS:
            try:
                element = page.query_selector(selector)
                if element:
                    candidate = element.inner_text()
                    if len(candidate.strip()) > 200:  # ignore tiny/empty matches
                        raw_text = candidate
                        break
            except Exception:
                continue

        browser.close()

    if not raw_text.strip():
        raise RuntimeError(
            f"Could not extract job content from {url}. "
            "The page may require authentication or use an unsupported rendering method."
        )

    return _clean_text(raw_text)


def _clean_text(text: str) -> str:
    """Normalize whitespace, remove junk lines, and truncate."""
    # Collapse runs of whitespace/blank lines
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Drop lines that are just punctuation / single chars / URLs
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        # Skip lines that are pure symbols or navigation artifacts
        if re.fullmatch(r"[^a-zA-Z0-9]{0,5}", stripped):
            continue
        # Skip bare URLs
        if re.fullmatch(r"https?://\S+", stripped):
            continue
        lines.append(stripped)

    text = "\n".join(lines).strip()

    # Truncate to token budget (rough: 3 chars ≈ 1 token)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[... truncated to fit context window ...]"

    return text


# ── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    test_url = (
        sys.argv[1] if len(sys.argv) > 1
        else (
            "https://recruiting2.ultipro.com/DIG1008DIGI/JobBoard/"
            "bf7d79dc-5bb9-447e-be77-bc5713185792/OpportunityDetail"
            "?opportunityId=bd4e8acf-6f09-4098-bc2b-f97b7988126f"
        )
    )

    print(f"Fetching: {test_url}\n{'─' * 60}")
    content = get_url_content(test_url)
    print(content)
    print(f"\n{'─' * 60}\nTotal chars: {len(content)}")