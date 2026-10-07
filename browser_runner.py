from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from engine import StopRequested, TestCase, TestResult
from manual_eval import Observation, evaluate_observation


@dataclass
class BrowserConfig:
    url: str
    browser_channel: str = "msedge"
    input_selector: str = "textarea"
    send_selector: str = ""
    response_selector: str = ""
    new_chat_selector: str = ""
    tool_selector: str = ""
    arguments_selector: str = ""
    sources_selector: str = ""
    ready_selector: str = ""
    timeout_ms: int = 60000
    settle_ms: int = 1200
    user_data_dir: str = ""
    headless: bool = False


class BrowserDependencyError(RuntimeError):
    pass


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise BrowserDependencyError(
            "Browser Auto 需要 Playwright。請使用官方 Setup EXE；開發環境請執行 pip install playwright。"
        ) from exc
    return sync_playwright


def _default_profile_dir() -> str:
    from storage import APP_DIR

    profile = APP_DIR / "browser_profile"
    profile.mkdir(parents=True, exist_ok=True)
    return str(profile)


def open_login_session(config: BrowserConfig) -> None:
    sync_playwright = _load_playwright()
    profile = config.user_data_dir.strip() or _default_profile_dir()
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile,
            channel=config.browser_channel or "msedge",
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        if config.ready_selector.strip():
            try:
                page.locator(config.ready_selector).first.wait_for(state="visible", timeout=config.timeout_ms)
            except Exception:
                pass
        try:
            while context.pages:
                time.sleep(0.4)
        except KeyboardInterrupt:
            pass
        finally:
            context.close()


def _latest_text(page, selector: str) -> str:
    if not selector.strip():
        return ""
    loc = page.locator(selector)
    count = loc.count()
    if count <= 0:
        return ""
    try:
        return loc.nth(count - 1).inner_text(timeout=3000).strip()
    except Exception:
        try:
            value = loc.nth(count - 1).text_content(timeout=3000)
            return (value or "").strip()
        except Exception:
            return ""


def _latest_count(page, selector: str) -> int:
    if not selector.strip():
        return 0
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


def _wait_for_response(page, selector: str, previous_count: int, previous_text: str, timeout_ms: int, settle_ms: int) -> str:
    if not selector.strip():
        raise ValueError("Browser Auto 必須設定 Response Selector")

    deadline = time.time() + timeout_ms / 1000.0
    last_text = ""
    stable_since = None

    while time.time() < deadline:
        count = _latest_count(page, selector)
        text = _latest_text(page, selector)
        changed = (count > previous_count) or (text and text != previous_text)
        if changed and text:
            if text != last_text:
                last_text = text
                stable_since = time.time()
            elif stable_since and (time.time() - stable_since) * 1000 >= settle_ms:
                return text
        time.sleep(0.25)

    if last_text:
        return last_text
    raise TimeoutError(f"等待 Response Selector '{selector}' 超時")


def run_browser_suite(
    config: BrowserConfig,
    cases: list[TestCase],
    *,
    repeats: int = 1,
    on_result: Callable[[TestResult, int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[TestResult]:
    sync_playwright = _load_playwright()
    enabled = [c for c in cases if c.enabled]
    expanded = [c for _ in range(max(1, repeats)) for c in enabled]
    total = len(expanded)
    if total == 0:
        return []

    profile = config.user_data_dir.strip() or _default_profile_dir()
    results: list[TestResult] = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile,
            channel=config.browser_channel or "msedge",
            headless=config.headless,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.url, wait_until="domcontentloaded", timeout=config.timeout_ms)

        if config.ready_selector.strip():
            page.locator(config.ready_selector).first.wait_for(state="visible", timeout=config.timeout_ms)

        for index, case in enumerate(expanded, start=1):
            if should_stop and should_stop():
                context.close()
                raise StopRequested()

            if config.new_chat_selector.strip():
                try:
                    page.locator(config.new_chat_selector).first.click(timeout=5000)
                    time.sleep(0.4)
                except Exception:
                    pass

            input_box = page.locator(config.input_selector).first
            input_box.wait_for(state="visible", timeout=config.timeout_ms)
            previous_count = _latest_count(page, config.response_selector)
            previous_text = _latest_text(page, config.response_selector)

            input_box.fill(case.input_text)
            started = time.perf_counter()

            if config.send_selector.strip():
                page.locator(config.send_selector).first.click(timeout=10000)
            else:
                input_box.press("Enter")

            answer = _wait_for_response(
                page,
                config.response_selector,
                previous_count,
                previous_text,
                config.timeout_ms,
                config.settle_ms,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0

            actual_tool = _latest_text(page, config.tool_selector)
            arguments_text = _latest_text(page, config.arguments_selector)
            source_count = _latest_count(page, config.sources_selector)

            obs = Observation(
                answer=answer,
                tool=actual_tool,
                arguments_json=arguments_text,
                source_count=source_count,
                latency_ms=latency_ms,
                status_code=None,
                raw_text=answer,
                raw_json=None,
                origin=f"browser:{config.url}",
            )
            result = evaluate_observation(case, obs)
            results.append(result)
            if on_result:
                on_result(result, index, total)

        context.close()

    return results
