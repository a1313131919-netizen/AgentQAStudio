from pathlib import Path

from browser_runner import BrowserConfig, run_browser_suite
from engine import TestCase

url = Path("browser_fixture.html").resolve().as_uri()
config = BrowserConfig(
    url=url,
    browser_channel="msedge",
    input_selector="#prompt",
    send_selector="#send",
    response_selector=".agent-response",
    timeout_ms=10000,
    settle_ms=300,
    user_data_dir=str(Path(".browser-smoke-profile").resolve()),
    headless=True,
)
case = TestCase(
    "B001",
    "Browser smoke",
    "幫我查 A001",
    must_contain="配送",
    max_latency_ms=5000,
)
results = run_browser_suite(config, [case])
assert len(results) == 1, results
assert results[0].passed, results[0].failures
print("BROWSER_SMOKE_OK")
print(results[0].answer)
print(round(results[0].latency_ms, 1))
