"""
autofill.py

Playwright-based job application autofiller.
Supports: Greenhouse, Lever, Workday, LinkedIn Easy Apply, and generic fallback.

Fills fields then pauses — you review and submit manually.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


# ------------------------------------------------------------------ #
# Profile loader                                                       #
# ------------------------------------------------------------------ #

def load_profile(profile_text: str) -> dict[str, Any]:
    return json.loads(profile_text)


# ------------------------------------------------------------------ #
# Platform detection                                                   #
# ------------------------------------------------------------------ #

def detect_platform(url: str) -> str:
    """Identify the ATS platform from the URL."""
    url_lower = url.lower()
    if "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
        return "greenhouse"
    if "lever.co" in url_lower or "jobs.lever" in url_lower:
        return "lever"
    if "myworkdayjobs.com" in url_lower or "workday.com" in url_lower:
        return "workday"
    if "linkedin.com/jobs" in url_lower:
        return "linkedin"
    if "ultipro.com" in url_lower or "recruiting2.ultipro" in url_lower:
        return "ultipro"
    return "generic"


# ------------------------------------------------------------------ #
# Low-level fill helpers                                               #
# ------------------------------------------------------------------ #

def _safe_fill(page: Page, selector: str, value: str, timeout: int = 3000) -> bool:
    """Fill a field if it exists. Returns True on success."""
    try:
        el = page.wait_for_selector(selector, timeout=timeout, state="visible")
        if el:
            el.click()
            el.fill(value)
            return True
    except Exception:
        pass
    return False


def _safe_select(page: Page, selector: str, value: str, timeout: int = 3000) -> bool:
    """Select an option in a <select> element. Returns True on success."""
    try:
        el = page.wait_for_selector(selector, timeout=timeout, state="visible")
        if el:
            el.select_option(label=value)
            return True
    except Exception:
        pass
    return False


def _safe_check_radio(page: Page, selector: str, timeout: int = 3000) -> bool:
    """Check a radio button or checkbox. Returns True on success."""
    try:
        el = page.wait_for_selector(selector, timeout=timeout, state="visible")
        if el:
            el.check()
            return True
    except Exception:
        pass
    return False


def _fill_generic_field(page: Page, label_text: str, value: str) -> bool:
    """
    Try to fill an input by finding it near a label that contains label_text.
    Works for most custom forms where selectors aren't predictable.
    """
    try:
        filled = page.evaluate(
            """([labelText, val]) => {
                const labels = Array.from(document.querySelectorAll('label'));
                const label = labels.find(l =>
                    l.textContent.toLowerCase().includes(labelText.toLowerCase())
                );
                if (!label) return false;

                // Try for= attribute first
                if (label.htmlFor) {
                    const el = document.getElementById(label.htmlFor);
                    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                        el.focus();
                        el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    }
                }

                // Try next sibling input
                const sibling = label.nextElementSibling;
                if (sibling && (sibling.tagName === 'INPUT' || sibling.tagName === 'TEXTAREA')) {
                    sibling.focus();
                    sibling.value = val;
                    sibling.dispatchEvent(new Event('input', { bubbles: true }));
                    sibling.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }

                // Try input inside label
                const inner = label.querySelector('input, textarea');
                if (inner) {
                    inner.focus();
                    inner.value = val;
                    inner.dispatchEvent(new Event('input', { bubbles: true }));
                    inner.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }

                return false;
            }""",
            [label_text, value],
        )
        return bool(filled)
    except Exception:
        return False


# ------------------------------------------------------------------ #
# Platform handlers                                                    #
# ------------------------------------------------------------------ #

class _BaseFiller:
    """Shared logic for all platform fillers."""

    def __init__(self, page: Page, profile: dict[str, Any], resume_path: str | None = None) -> None:
        self.page = page
        self.p = profile
        self.resume_path = resume_path
        self.filled: list[str] = []
        self.skipped: list[str] = []

    def _log_filled(self, field: str) -> None:
        self.filled.append(field)
        print(f"    ✓ {field}")

    def _log_skipped(self, field: str, reason: str = "not found") -> None:
        self.skipped.append(field)
        print(f"    ~ {field} ({reason})")

    def _try_fill(self, selector: str, value: str, label: str) -> None:
        if _safe_fill(self.page, selector, value):
            self._log_filled(label)
        else:
            self._log_skipped(label)

    def _try_select(self, selector: str, value: str, label: str) -> None:
        if _safe_select(self.page, selector, value):
            self._log_filled(label)
        else:
            self._log_skipped(label)

    def _upload_resume(self, file_input_selector: str) -> None:
        if not self.resume_path:
            self._log_skipped("Resume", "no path provided")
            return
        try:
            el = self.page.wait_for_selector(file_input_selector, timeout=4000)
            if el:
                el.set_input_files(self.resume_path)
                self._log_filled("Resume upload")
        except Exception:
            self._log_skipped("Resume upload")

    def fill(self) -> None:
        raise NotImplementedError

    def print_summary(self) -> None:
        print(f"\n  Filled {len(self.filled)} field(s), skipped {len(self.skipped)}.")
        if self.skipped:
            print(f"  Skipped: {', '.join(self.skipped)}")


class GreenhouseFiller(_BaseFiller):
    """Filler for Greenhouse (boards.greenhouse.io)."""

    def fill(self) -> None:
        p = self.p
        loc = p.get("location", {})
        auth = p.get("work_authorization", {})

        self._try_fill("#first_name", p.get("first_name", ""), "First name")
        self._try_fill("#last_name", p.get("last_name", ""), "Last name")
        self._try_fill("#email", p.get("email", ""), "Email")
        self._try_fill("#phone", p.get("phone", ""), "Phone")
        self._try_fill("#job_application_location", loc.get("city", ""), "Location")
        self._try_fill("#job_application_urls_0", p.get("linkedin_url", ""), "LinkedIn URL")
        self._try_fill("#job_application_urls_1", p.get("portfolio_url", ""), "Portfolio URL")

        self._upload_resume("input[type='file']")

        # Work authorization — Greenhouse uses yes/no radio buttons
        if auth.get("authorized_to_work"):
            _safe_check_radio(self.page, "input[name*='authorized'][value='Yes']")
            _safe_check_radio(self.page, "input[name*='work_authorization'][value='1']")
            self._log_filled("Work authorization: Yes")

        if not auth.get("requires_sponsorship"):
            _safe_check_radio(self.page, "input[name*='sponsorship'][value='No']")
            _safe_check_radio(self.page, "input[name*='visa'][value='0']")
            self._log_filled("Requires sponsorship: No")


class LeverFiller(_BaseFiller):
    """Filler for Lever (jobs.lever.co)."""

    def fill(self) -> None:
        p = self.p
        auth = p.get("work_authorization", {})

        self._try_fill("input[name='name']", f"{p.get('first_name', '')} {p.get('last_name', '')}", "Full name")
        self._try_fill("input[name='email']", p.get("email", ""), "Email")
        self._try_fill("input[name='phone']", p.get("phone", ""), "Phone")
        self._try_fill("input[name='org']", "", "Current company")  # intentionally blank
        self._try_fill("input[name='urls[LinkedIn]']", p.get("linkedin_url", ""), "LinkedIn URL")
        self._try_fill("input[name='urls[Portfolio]']", p.get("portfolio_url", ""), "Portfolio URL")

        self._upload_resume("input[type='file']")

        # Lever work auth dropdowns vary — try common selectors
        if auth.get("authorized_to_work"):
            _safe_check_radio(self.page, "input[name*='authorized'][value='Yes']")
            self._log_filled("Work authorization: Yes")

        if not auth.get("requires_sponsorship"):
            _safe_check_radio(self.page, "input[name*='sponsorship'][value='No']")
            self._log_filled("Requires sponsorship: No")


class WorkdayFiller(_BaseFiller):
    """
    Filler for Workday (myworkdayjobs.com).
    Workday uses heavily dynamic React — we use label-based JS injection.
    """

    def fill(self) -> None:
        p = self.p
        loc = p.get("location", {})
        auth = p.get("work_authorization", {})

        # Workday loads lazily; give it a moment
        time.sleep(2)

        fields = [
            ("First Name", p.get("first_name", "")),
            ("Last Name", p.get("last_name", "")),
            ("Email Address", p.get("email", "")),
            ("Phone Number", p.get("phone", "")),
            ("City", loc.get("city", "")),
            ("State", loc.get("state", "")),
            ("Postal Code", loc.get("zip", "")),
            ("LinkedIn", p.get("linkedin_url", "")),
        ]

        for label, value in fields:
            if _fill_generic_field(self.page, label, value):
                self._log_filled(label)
            else:
                self._log_skipped(label)

        self._upload_resume("input[type='file']")

        # Work auth is usually a dropdown in Workday
        if auth.get("authorized_to_work"):
            _fill_generic_field(self.page, "authorized to work", "Yes")
            self._log_filled("Work authorization: Yes")

        if not auth.get("requires_sponsorship"):
            _fill_generic_field(self.page, "sponsorship", "No")
            self._log_filled("Requires sponsorship: No")


class LinkedInFiller(_BaseFiller):
    """
    Filler for LinkedIn Easy Apply.
    LinkedIn's modal is multi-step; we fill the first screen (contact info).
    """

    def fill(self) -> None:
        p = self.p
        loc = p.get("location", {})
        auth = p.get("work_authorization", {})

        # Click Easy Apply button to open modal
        try:
            btn = self.page.wait_for_selector(
                "button.jobs-apply-button, button[aria-label*='Easy Apply']",
                timeout=8000,
            )
            if btn:
                btn.click()
                time.sleep(1.5)
                print("    ✓ Opened Easy Apply modal")
        except Exception:
            print("    ~ Could not find Easy Apply button — fill manually")

        # LinkedIn pre-fills most contact info from your profile.
        # We check/correct the phone field which often needs updating.
        self._try_fill("input[id*='phoneNumber']", p.get("phone", ""), "Phone")
        self._try_fill("input[id*='city']", loc.get("city", ""), "City")

        # Work auth
        if auth.get("authorized_to_work"):
            _fill_generic_field(self.page, "authorized to work", "Yes")
            _fill_generic_field(self.page, "legally authorized", "Yes")
            self._log_filled("Work authorization: Yes")

        if not auth.get("requires_sponsorship"):
            _fill_generic_field(self.page, "require sponsorship", "No")
            _fill_generic_field(self.page, "visa sponsorship", "No")
            self._log_filled("Requires sponsorship: No")


class UltiproFiller(_BaseFiller):
    """Filler for UKG/Ultipro (recruiting2.ultipro.com)."""

    def fill(self) -> None:
        p = self.p
        loc = p.get("location", {})
        auth = p.get("work_authorization", {})

        self._try_fill("input[name*='firstName'], #firstName", p.get("first_name", ""), "First name")
        self._try_fill("input[name*='lastName'], #lastName", p.get("last_name", ""), "Last name")
        self._try_fill("input[name*='email'], input[type='email']", p.get("email", ""), "Email")
        self._try_fill("input[name*='phone'], input[type='tel']", p.get("phone", ""), "Phone")
        self._try_fill("input[name*='city']", loc.get("city", ""), "City")
        self._try_fill("input[name*='zip'], input[name*='postal']", loc.get("zip", ""), "ZIP")

        self._upload_resume("input[type='file']")

        if auth.get("authorized_to_work"):
            _safe_check_radio(self.page, "input[value='Yes'][name*='authorized']")
            self._log_filled("Work authorization: Yes")

        if not auth.get("requires_sponsorship"):
            _safe_check_radio(self.page, "input[value='No'][name*='sponsor']")
            self._log_filled("Requires sponsorship: No")


class GenericFiller(_BaseFiller):
    """
    Fallback filler for unknown ATSes and company websites.
    Uses label text matching and common input name patterns.
    """

    FIELD_MAP = [
        # (label hint, input name/id hints, profile key path)
        ("first name",  ["first_name", "firstName", "fname"],     ["first_name"]),
        ("last name",   ["last_name",  "lastName",  "lname"],     ["last_name"]),
        ("email",       ["email"],                                  ["email"]),
        ("phone",       ["phone", "telephone", "mobile"],          ["phone"]),
        ("linkedin",    ["linkedin"],                               ["linkedin_url"]),
        ("portfolio",   ["portfolio", "website"],                   ["portfolio_url"]),
        ("city",        ["city"],                                   ["location", "city"]),
        ("state",       ["state"],                                  ["location", "state"]),
        ("zip",         ["zip", "postal"],                          ["location", "zip"]),
    ]

    def _get(self, key_path: list[str]) -> str:
        val = self.p
        for k in key_path:
            if not isinstance(val, dict):
                return ""
            val = val.get(k, "")
        return str(val) if val else ""

    def fill(self) -> None:
        auth = self.p.get("work_authorization", {})

        for label_hint, name_hints, key_path in self.FIELD_MAP:
            value = self._get(key_path)
            if not value:
                continue

            # Try label-based injection first
            if _fill_generic_field(self.page, label_hint, value):
                self._log_filled(label_hint.title())
                continue

            # Fall back to name/id attribute guesses
            filled = False
            for hint in name_hints:
                selector = (
                    f"input[name*='{hint}' i], "
                    f"input[id*='{hint}' i], "
                    f"textarea[name*='{hint}' i]"
                )
                if _safe_fill(self.page, selector, value):
                    self._log_filled(label_hint.title())
                    filled = True
                    break
            if not filled:
                self._log_skipped(label_hint.title())

        self._upload_resume("input[type='file']")

        # Work auth
        if auth.get("authorized_to_work"):
            _fill_generic_field(self.page, "authorized to work", "Yes")
            _fill_generic_field(self.page, "legally authorized", "Yes")
            self._log_filled("Work authorization: Yes")

        if not auth.get("requires_sponsorship"):
            _fill_generic_field(self.page, "sponsorship", "No")
            self._log_filled("Requires sponsorship: No")


# ------------------------------------------------------------------ #
# Filler factory                                                       #
# ------------------------------------------------------------------ #

_FILLER_MAP: dict[str, type[_BaseFiller]] = {
    "greenhouse": GreenhouseFiller,
    "lever":      LeverFiller,
    "workday":    WorkdayFiller,
    "linkedin":   LinkedInFiller,
    "ultipro":    UltiproFiller,
    "generic":    GenericFiller,
}


def get_filler(
    platform: str,
    page: Page,
    profile: dict[str, Any],
    resume_path: str | None = None,
) -> _BaseFiller:
    cls = _FILLER_MAP.get(platform, GenericFiller)
    return cls(page, profile, resume_path)


# ------------------------------------------------------------------ #
# Main entry point                                                     #
# ------------------------------------------------------------------ #

def autofill_application(
    url: str,
    profile_text: str,
    resume_path: str | None = None,
) -> None:
    """
    Open the application URL in a visible browser, autofill known fields,
    then pause so you can review and submit manually.

    Args:
        url:          Direct link to the job application form.
        resume_path:  Optional path to your resume PDF/DOCX to upload.
        profile_path: Path to your profile.json.
    """
    profile = load_profile(profile_text)
    platform = detect_platform(url)

    print(f"\n  Platform detected: {platform.upper()}")
    print(f"  Opening: {url}")

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(
            headless=False,          # Visible so you can review
            slow_mo=120,             # Slight delay so fills look natural
            args=["--start-maximized"],
        )
        context: BrowserContext = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            no_viewport=True,        # Use the maximized window size
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as e:
            print(f"  ✗ Could not load page: {e}")
            browser.close()
            return

        # Extra wait for JS-heavy ATSes
        try:
            page.wait_for_function(
                "document.body.innerText.trim().length > 200",
                timeout=10_000,
            )
        except Exception:
            pass

        print("  Please log in or navigate to the actual application form.")
        print("  Once you are on the page where fields should be filled:")
        print("  -> Press ENTER here to start the autofill.")
        input()

        print("\n  Filling fields...")
        filler = get_filler(platform, page, profile, resume_path)
        filler.fill()
        filler.print_summary()

        print("\n" + "=" * 60)
        print("  PAUSED — Review the form in the browser.")
        print("  Make any corrections, attach your resume if needed,")
        print("  then press ENTER here when you're ready to close.")
        print("=" * 60)
        input()

        browser.close()
        print("  Browser closed.")