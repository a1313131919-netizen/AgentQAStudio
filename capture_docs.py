from pathlib import Path
import time

from PIL import ImageGrab

import app


OUT = Path("docs/images")
OUT.mkdir(parents=True, exist_ok=True)

ui = app.AgentQAStudio()
ui.geometry("1380x860+40+40")
ui.attributes("-topmost", True)
ui.lift()
ui.focus_force()
ui.update()
time.sleep(0.5)
ui.load_demo(show_message=False)

# Fill browser example without opening message boxes.
ui.browser_url.set("https://staging.example.com/agent")
ui.browser_channel.set("msedge")
ui.browser_input_selector.set("textarea")
ui.browser_send_selector.set('button[type="submit"]')
ui.browser_response_selector.set(".agent-response")
ui.browser_new_chat_selector.set(".new-chat")
ui.browser_tool_selector.set(".tool-name")
ui.browser_arguments_selector.set(".tool-arguments")
ui.browser_sources_selector.set(".source-item")
ui.browser_ready_selector.set("textarea")

# Prepare manual example.
ui._refresh_manual_cases()
ui.manual_response_text.insert("1.0", "訂單 A001 目前配送中。")
ui.manual_tool_var.set("get_order_status")
ui.manual_args_var.set('{"order_id":"A001"}')
ui.manual_sources_var.set("1")
ui.manual_latency_var.set("1280")

# Prepare results view with demo results.
from engine import ApiConfig, evaluate_case
cfg = ApiConfig(url="mock://agent", method="POST")
ui.results = [evaluate_case(cfg, c) for c in ui.cases[:4]]
ui.result_by_iid.clear()
for iid in ui.result_tree.get_children():
    ui.result_tree.delete(iid)
for result in ui.results:
    ui._append_result_to_tree(result)
ui._update_metrics()

# Replace local history rows in the screenshot with synthetic demo history only.
for iid in ui.history_tree.get_children():
    ui.history_tree.delete(iid)
ui.history_tree.insert(
    "", "end", iid="demo-2",
    values=(2, "2026-10-07 22:45:00", "browser:https://staging.example.com/agent", 12, 11, 1, "91.7%", "1480", "2620"),
)
ui.history_tree.insert(
    "", "end", iid="demo-1",
    values=(1, "2026-10-07 22:40:00", "mock://agent", 4, 4, 0, "100.0%", "31", "35"),
)

names = [
    (0, "01_api_auto.png"),
    (1, "02_browser_auto.png"),
    (2, "03_manual_ui.png"),
    (3, "04_test_cases.png"),
    (4, "05_results.png"),
    (5, "06_reports.png"),
]

for index, filename in names:
    ui.tabs.select(index)
    ui.lift()
    ui.focus_force()
    ui.update()
    time.sleep(0.5)
    x = ui.winfo_rootx()
    y = ui.winfo_rooty()
    w = ui.winfo_width()
    h = ui.winfo_height()
    image = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    image.save(OUT / filename)

ui.destroy()
print("CAPTURE_OK")
