from __future__ import annotations

import csv
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from engine import (
    ApiConfig,
    StopRequested,
    TestCase,
    TestResult,
    evaluate_case,
    generate_edge_cases,
    run_suite,
    summarize_results,
)
from browser_runner import BrowserConfig, open_login_session, run_browser_suite
from manual_eval import Observation, evaluate_observation
from reports import export_csv, export_html, export_json
from storage import (
    APP_DIR,
    init_db,
    list_runs,
    load_browser_settings,
    load_cases,
    load_config,
    load_run,
    save_browser_settings,
    save_cases,
    save_config,
    save_run,
)


APP_TITLE = "Agent QA Studio"
APP_VERSION = "0.2.0"


class CaseEditor(tk.Toplevel):
    def __init__(self, master, case: TestCase | None = None):
        super().__init__(master)
        self.title("Test Case")
        self.geometry("760x690")
        self.minsize(650, 580)
        self.transient(master)
        self.grab_set()
        self.result: TestCase | None = None
        self.original = case

        self.vars = {
            "case_id": tk.StringVar(value=case.case_id if case else ""),
            "name": tk.StringVar(value=case.name if case else ""),
            "expected_status": tk.StringVar(value=case.expected_status if case else "200"),
            "expected_tool": tk.StringVar(value=case.expected_tool if case else ""),
            "expected_args_json": tk.StringVar(value=case.expected_args_json if case else ""),
            "must_contain": tk.StringVar(value=case.must_contain if case else ""),
            "must_not_contain": tk.StringVar(value=case.must_not_contain if case else ""),
            "expected_json_path": tk.StringVar(value=case.expected_json_path if case else ""),
            "expected_json_value": tk.StringVar(value=case.expected_json_value if case else ""),
            "min_sources": tk.StringVar(value=str(case.min_sources if case else 0)),
            "max_latency_ms": tk.StringVar(value=str(case.max_latency_ms if case else 0)),
            "category": tk.StringVar(value=case.category if case else "Functional"),
            "enabled": tk.BooleanVar(value=case.enabled if case else True),
        }

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        fields = [
            ("Case ID", "case_id"),
            ("名稱", "name"),
            ("分類", "category"),
            ("預期 HTTP Status", "expected_status"),
            ("預期 Tool", "expected_tool"),
            ("預期 Arguments JSON", "expected_args_json"),
            ("答案必須包含（用 | 分隔）", "must_contain"),
            ("答案不得包含（用 | 分隔）", "must_not_contain"),
            ("額外 JSON Path", "expected_json_path"),
            ("JSON Path 預期值", "expected_json_value"),
            ("最少 Sources 數", "min_sources"),
            ("最大 Latency (ms，0=不限制)", "max_latency_ms"),
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            if key == "category":
                widget = ttk.Combobox(
                    root,
                    textvariable=self.vars[key],
                    values=["Functional", "Tool Calling", "RAG", "Boundary", "Encoding", "Conversation", "Safety", "Performance", "Other"],
                    state="normal",
                )
            else:
                widget = ttk.Entry(root, textvariable=self.vars[key])
            widget.grid(row=row, column=1, sticky="ew", pady=4)

        row = len(fields)
        ttk.Label(root, text="Input / 使用者問題").grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=4)
        self.input_text = tk.Text(root, height=8, wrap="word")
        self.input_text.grid(row=row, column=1, sticky="nsew", pady=4)
        self.input_text.insert("1.0", case.input_text if case else "")
        root.rowconfigure(row, weight=1)

        row += 1
        ttk.Checkbutton(root, text="啟用此 Case", variable=self.vars["enabled"]).grid(
            row=row, column=1, sticky="w", pady=4
        )

        row += 1
        buttons = ttk.Frame(root)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="儲存", command=self._save).pack(side="right", padx=4)

    def _save(self):
        try:
            case_id = self.vars["case_id"].get().strip() or f"T-{int(time.time())}"
            name = self.vars["name"].get().strip() or case_id
            expected_args = self.vars["expected_args_json"].get().strip()
            if expected_args:
                parsed = json.loads(expected_args)
                if not isinstance(parsed, (dict, list)):
                    raise ValueError("Arguments 必須是 JSON object 或 array")
            self.result = TestCase(
                case_id=case_id,
                name=name,
                input_text=self.input_text.get("1.0", "end").rstrip("\n"),
                expected_status=self.vars["expected_status"].get().strip(),
                expected_tool=self.vars["expected_tool"].get().strip(),
                expected_args_json=expected_args,
                must_contain=self.vars["must_contain"].get().strip(),
                must_not_contain=self.vars["must_not_contain"].get().strip(),
                expected_json_path=self.vars["expected_json_path"].get().strip(),
                expected_json_value=self.vars["expected_json_value"].get().strip(),
                min_sources=max(0, int(self.vars["min_sources"].get() or 0)),
                max_latency_ms=max(0, int(self.vars["max_latency_ms"].get() or 0)),
                enabled=bool(self.vars["enabled"].get()),
                category=self.vars["category"].get().strip() or "Functional",
            )
            self.destroy()
        except Exception as exc:
            messagebox.showerror("資料錯誤", str(exc), parent=self)


class AgentQAStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} {APP_VERSION}")
        self.geometry("1380x860")
        self.minsize(1100, 720)

        self.style = ttk.Style(self)
        if "vista" in self.style.theme_names():
            self.style.theme_use("vista")
        self.style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        self.style.configure("Subtitle.TLabel", foreground="#5d6678")
        self.style.configure("Metric.TLabel", font=("Segoe UI", 17, "bold"))
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        self.config_obj = load_config()
        self.browser_settings = load_browser_settings()
        self.cases: list[TestCase] = load_cases()
        self.results: list[TestResult] = []
        self.result_by_iid: dict[str, TestResult] = {}
        self.stop_event = threading.Event()
        self.ui_queue: queue.Queue = queue.Queue()
        self.running = False
        self.current_run_origin = ""
        self.manual_case_index = 0

        init_db()
        self._build_header()
        self._build_tabs()
        self._load_demo_if_empty()
        self._refresh_cases()
        self._refresh_history()
        self.after(100, self._drain_ui_queue)

    def _build_header(self):
        header = ttk.Frame(self, padding=(18, 14, 18, 8))
        header.pack(fill="x")
        left = ttk.Frame(header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="Agent QA Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="No-code AI Agent / LLM / RAG QA · API Auto · Browser Auto · Manual UI",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(header, text="API Key 不會寫入設定檔", style="Subtitle.TLabel").pack(side="right")

    def _build_tabs(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.tab_api = ttk.Frame(self.tabs, padding=14)
        self.tab_browser = ttk.Frame(self.tabs, padding=14)
        self.tab_manual = ttk.Frame(self.tabs, padding=14)
        self.tab_cases = ttk.Frame(self.tabs, padding=14)
        self.tab_run = ttk.Frame(self.tabs, padding=14)
        self.tab_reports = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(self.tab_api, text="1  API Auto")
        self.tabs.add(self.tab_browser, text="2  Browser Auto")
        self.tabs.add(self.tab_manual, text="3  Manual UI")
        self.tabs.add(self.tab_cases, text="4  Test Cases")
        self.tabs.add(self.tab_run, text="5  執行與結果")
        self.tabs.add(self.tab_reports, text="6  報告與歷史")

        self._build_api_tab()
        self._build_browser_tab()
        self._build_manual_tab()
        self._build_cases_tab()
        self._build_run_tab()
        self._build_reports_tab()

    def _build_api_tab(self):
        tab = self.tab_api
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        connection = ttk.LabelFrame(tab, text="連線設定", padding=12)
        mapping = ttk.LabelFrame(tab, text="Response Mapping（告訴工具回覆欄位在哪）", padding=12)
        connection.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        mapping.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        connection.columnconfigure(1, weight=1)
        mapping.columnconfigure(1, weight=1)

        self.api_url = tk.StringVar(value=self.config_obj.url)
        self.api_method = tk.StringVar(value=self.config_obj.method)
        self.api_token = tk.StringVar(value="")
        self.api_timeout = tk.StringVar(value=str(self.config_obj.timeout_sec))
        self.answer_path = tk.StringVar(value=self.config_obj.answer_path)
        self.tool_path = tk.StringVar(value=self.config_obj.tool_path)
        self.arguments_path = tk.StringVar(value=self.config_obj.arguments_path)
        self.sources_path = tk.StringVar(value=self.config_obj.sources_path)

        ttk.Label(connection, text="URL").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(connection, textvariable=self.api_url).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(connection, text="Method").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            connection,
            textvariable=self.api_method,
            values=["POST", "GET", "PUT", "PATCH", "DELETE"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=5)
        ttk.Label(connection, text="Bearer Token / API Key").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(connection, textvariable=self.api_token, show="•").grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(connection, text="Timeout (sec)").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(connection, textvariable=self.api_timeout, width=12).grid(row=3, column=1, sticky="w", pady=5)

        ttk.Label(mapping, text="Answer Path").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(mapping, textvariable=self.answer_path).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(mapping, text="Tool Path").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(mapping, textvariable=self.tool_path).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(mapping, text="Arguments Path").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(mapping, textvariable=self.arguments_path).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(mapping, text="Sources Path").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(mapping, textvariable=self.sources_path).grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Label(
            mapping,
            text="支援 dot path，例如 data.answer、choices.0.message.content",
            style="Subtitle.TLabel",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        advanced = ttk.LabelFrame(tab, text="Request 設定", padding=12)
        advanced.grid(row=1, column=0, columnspan=2, sticky="nsew")
        advanced.columnconfigure(0, weight=1)
        advanced.columnconfigure(1, weight=1)
        advanced.rowconfigure(1, weight=1)

        left = ttk.Frame(advanced)
        right = ttk.Frame(advanced)
        left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
        left.rowconfigure(1, weight=1)
        right.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(left, text='Headers JSON').grid(row=0, column=0, sticky="w")
        self.headers_text = tk.Text(left, height=9, wrap="none")
        self.headers_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.headers_text.insert("1.0", self.config_obj.headers_json)

        ttk.Label(right, text='Body Template（{{input}} 會換成每個 Test Case 的問題）').grid(row=0, column=0, sticky="w")
        self.body_text = tk.Text(right, height=9, wrap="none")
        self.body_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.body_text.insert("1.0", self.config_obj.body_template)

        controls = ttk.Frame(tab)
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(controls, text="載入 Demo", command=self.load_demo).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="儲存設定", command=self.save_current_config).pack(side="left", padx=6)
        ttk.Button(controls, text="測試連線", command=self.test_connection, style="Accent.TButton").pack(side="left", padx=6)
        self.connection_status = ttk.Label(controls, text="尚未測試", style="Subtitle.TLabel")
        self.connection_status.pack(side="left", padx=12)

    def _build_browser_tab(self):
        tab = self.tab_browser
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        bs = self.browser_settings
        self.browser_url = tk.StringVar(value=str(bs.get("url", "")))
        self.browser_channel = tk.StringVar(value=str(bs.get("browser_channel", "msedge")))
        self.browser_input_selector = tk.StringVar(value=str(bs.get("input_selector", "textarea")))
        self.browser_send_selector = tk.StringVar(value=str(bs.get("send_selector", "")))
        self.browser_response_selector = tk.StringVar(value=str(bs.get("response_selector", "")))
        self.browser_new_chat_selector = tk.StringVar(value=str(bs.get("new_chat_selector", "")))
        self.browser_tool_selector = tk.StringVar(value=str(bs.get("tool_selector", "")))
        self.browser_arguments_selector = tk.StringVar(value=str(bs.get("arguments_selector", "")))
        self.browser_sources_selector = tk.StringVar(value=str(bs.get("sources_selector", "")))
        self.browser_ready_selector = tk.StringVar(value=str(bs.get("ready_selector", "")))
        self.browser_timeout_ms = tk.StringVar(value=str(bs.get("timeout_ms", "60000")))
        self.browser_settle_ms = tk.StringVar(value=str(bs.get("settle_ms", "1200")))

        target = ttk.LabelFrame(tab, text="目標網站 / Browser", padding=12)
        selectors = ttk.LabelFrame(tab, text="CSS Selectors", padding=12)
        target.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        selectors.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0), pady=(0, 8))
        target.columnconfigure(1, weight=1)
        selectors.columnconfigure(1, weight=1)

        ttk.Label(target, text="Target URL").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(target, textvariable=self.browser_url).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(target, text="Browser").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            target,
            textvariable=self.browser_channel,
            values=["msedge", "chrome"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=5)
        ttk.Label(target, text="Timeout (ms)").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(target, textvariable=self.browser_timeout_ms, width=12).grid(row=2, column=1, sticky="w", pady=5)
        ttk.Label(target, text="Response settle (ms)").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(target, textvariable=self.browser_settle_ms, width=12).grid(row=3, column=1, sticky="w", pady=5)

        selector_fields = [
            ("Input selector *", self.browser_input_selector),
            ("Send button selector", self.browser_send_selector),
            ("Response selector *", self.browser_response_selector),
            ("New Chat selector", self.browser_new_chat_selector),
            ("Tool selector", self.browser_tool_selector),
            ("Arguments selector", self.browser_arguments_selector),
            ("Sources selector", self.browser_sources_selector),
            ("Ready/Login selector", self.browser_ready_selector),
        ]
        for row, (label, var) in enumerate(selector_fields):
            ttk.Label(selectors, text=label).grid(row=row, column=0, sticky="w", pady=5, padx=(0, 8))
            ttk.Entry(selectors, textvariable=var).grid(row=row, column=1, sticky="ew", pady=5)

        helper = ttk.LabelFrame(tab, text="Browser Auto SOP", padding=12)
        helper.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        helper.columnconfigure(0, weight=1)
        ttk.Label(
            helper,
            text=(
                "1. 填 Target URL 與 Input / Response selector。\n"
                "2. 按「開啟登入 Browser」；第一次登入後關閉 Browser，登入狀態會保存在 Agent QA Studio 專用 profile。\n"
                "3. 到 Test Cases 建立測試資料。\n"
                "4. 到「執行與結果」選 Browser Auto 後批次執行。\n\n"
                "Send selector 留空時會按 Enter。Tool / Arguments / Sources selector 沒有顯示在 UI 時可留空。"
            ),
            justify="left",
            wraplength=620,
        ).grid(row=0, column=0, sticky="nw")

        actions = ttk.Frame(helper)
        actions.grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Button(actions, text="開啟登入 Browser", command=self.open_browser_login).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="載入 Selector 範例", command=self.load_browser_example).pack(side="left", padx=6)
        self.browser_status = ttk.Label(actions, text="尚未開啟", style="Subtitle.TLabel")
        self.browser_status.pack(side="left", padx=10)

    def _build_manual_tab(self):
        tab = self.tab_manual
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(2, weight=1)

        top = ttk.Frame(tab)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(top, text="Test Case").pack(side="left")
        self.manual_case_var = tk.StringVar(value="")
        self.manual_case_combo = ttk.Combobox(top, textvariable=self.manual_case_var, state="readonly", width=42)
        self.manual_case_combo.pack(side="left", padx=8)
        self.manual_case_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_manual_case())
        ttk.Button(top, text="複製 Input", command=self.copy_manual_input).pack(side="left", padx=4)
        ttk.Button(top, text="下一題", command=self.next_manual_case).pack(side="left", padx=4)

        expected = ttk.LabelFrame(tab, text="Expected / Test Case", padding=10)
        actual = ttk.LabelFrame(tab, text="Actual / 從 Agent UI 觀察到的結果", padding=10)
        expected.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        actual.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
        expected.columnconfigure(0, weight=1)
        expected.rowconfigure(1, weight=1)
        actual.columnconfigure(1, weight=1)
        actual.rowconfigure(1, weight=1)

        ttk.Label(expected, text="Input").grid(row=0, column=0, sticky="w")
        self.manual_input_text = tk.Text(expected, height=8, wrap="word")
        self.manual_input_text.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
        self.manual_input_text.config(state="disabled")
        self.manual_expected_label = ttk.Label(expected, text="", justify="left", wraplength=570)
        self.manual_expected_label.grid(row=2, column=0, sticky="nw")

        ttk.Label(actual, text="Actual Response").grid(row=0, column=0, columnspan=2, sticky="w")
        self.manual_response_text = tk.Text(actual, height=10, wrap="word")
        self.manual_response_text.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 8))

        manual_fields = [
            ("Observed Tool", "manual_tool_var"),
            ("Observed Arguments JSON", "manual_args_var"),
            ("Sources count", "manual_sources_var"),
            ("Latency ms", "manual_latency_var"),
            ("HTTP status (可空白)", "manual_status_var"),
        ]
        defaults = ["", "", "0", "0", ""]
        for i, ((label, attr), default) in enumerate(zip(manual_fields, defaults), start=2):
            var = tk.StringVar(value=default)
            setattr(self, attr, var)
            ttk.Label(actual, text=label).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 8))
            ttk.Entry(actual, textvariable=var).grid(row=i, column=1, sticky="ew", pady=4)

        actions = ttk.Frame(actual)
        actions.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Evaluate → PASS / FAIL", command=self.evaluate_manual, style="Accent.TButton").pack(side="left")
        ttk.Button(actions, text="清空 Actual", command=self.clear_manual_actual).pack(side="left", padx=8)
        ttk.Label(
            actions,
            text="UI 看不到的 Tool / Arguments / Sources 可留空；不要猜測隱藏資訊。",
            style="Subtitle.TLabel",
        ).pack(side="right")

    def _build_cases_tab(self):
        tab = self.tab_cases
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        controls = ttk.Frame(tab)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="新增 Case", command=self.add_case).pack(side="left", padx=(0, 5))
        ttk.Button(controls, text="編輯", command=self.edit_case).pack(side="left", padx=5)
        ttk.Button(controls, text="刪除", command=self.delete_case).pack(side="left", padx=5)
        ttk.Separator(controls, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(controls, text="匯入 CSV", command=self.import_cases_csv).pack(side="left", padx=5)
        ttk.Button(controls, text="匯出 CSV", command=self.export_cases_csv).pack(side="left", padx=5)
        ttk.Button(controls, text="產生 Edge Cases", command=self.add_edge_cases).pack(side="left", padx=5)
        self.case_count_label = ttk.Label(controls, text="")
        self.case_count_label.pack(side="right")

        columns = ("enabled", "id", "name", "category", "input", "status", "tool", "latency")
        self.case_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        headings = {
            "enabled": "On",
            "id": "ID",
            "name": "名稱",
            "category": "分類",
            "input": "Input",
            "status": "HTTP",
            "tool": "Expected Tool",
            "latency": "Max Latency",
        }
        widths = {"enabled": 45, "id": 90, "name": 150, "category": 110, "input": 390, "status": 70, "tool": 180, "latency": 100}
        for c in columns:
            self.case_tree.heading(c, text=headings[c])
            self.case_tree.column(c, width=widths[c], anchor="w")
        self.case_tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.case_tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.case_tree.configure(yscrollcommand=scroll.set)
        self.case_tree.bind("<Double-1>", lambda _e: self.edit_case())

        help_box = ttk.LabelFrame(tab, text="你不需要寫 assert", padding=10)
        help_box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(
            help_box,
            text="每個 Case 直接填 Expected Status / Tool / Arguments / 必須包含文字 / Sources 數 / Max Latency；程式會自動做 Expected vs Actual 判斷。",
            wraplength=1100,
        ).pack(anchor="w")

    def _build_run_tab(self):
        tab = self.tab_run
        tab.rowconfigure(2, weight=1)
        tab.columnconfigure(0, weight=1)

        controls = ttk.Frame(tab)
        controls.grid(row=0, column=0, sticky="ew")
        self.run_mode_var = tk.StringVar(value="API Auto")
        self.workers_var = tk.StringVar(value="1")
        self.repeats_var = tk.StringVar(value="1")
        ttk.Label(controls, text="Mode").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.run_mode_var,
            values=["API Auto", "Browser Auto"],
            state="readonly",
            width=14,
        ).pack(side="left", padx=(5, 14))
        ttk.Label(controls, text="Concurrent Workers").pack(side="left")
        ttk.Spinbox(controls, from_=1, to=32, width=6, textvariable=self.workers_var).pack(side="left", padx=(5, 14))
        ttk.Label(controls, text="Repeats").pack(side="left")
        ttk.Spinbox(controls, from_=1, to=100, width=6, textvariable=self.repeats_var).pack(side="left", padx=(5, 14))
        self.run_button = ttk.Button(controls, text="▶ 開始測試", command=self.start_run, style="Accent.TButton")
        self.run_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(controls, text="■ 停止", command=self.stop_run, state="disabled")
        self.stop_button.pack(side="left", padx=4)
        self.progress = ttk.Progressbar(controls, mode="determinate", length=260)
        self.progress.pack(side="right", padx=(10, 0))
        self.progress_label = ttk.Label(controls, text="Ready")
        self.progress_label.pack(side="right")

        metrics = ttk.Frame(tab)
        metrics.grid(row=1, column=0, sticky="ew", pady=12)
        self.metric_vars = {
            "total": tk.StringVar(value="0"),
            "pass_rate": tk.StringVar(value="0%"),
            "failed": tk.StringVar(value="0"),
            "avg": tk.StringVar(value="0 ms"),
            "p95": tk.StringVar(value="0 ms"),
        }
        labels = [("Total", "total"), ("Pass Rate", "pass_rate"), ("Failed", "failed"), ("Avg Latency", "avg"), ("P95 Latency", "p95")]
        for i, (label, key) in enumerate(labels):
            card = ttk.LabelFrame(metrics, text=label, padding=(18, 8))
            card.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 5, 0))
            ttk.Label(card, textvariable=self.metric_vars[key], style="Metric.TLabel").pack()

        paned = ttk.Panedwindow(tab, orient="vertical")
        paned.grid(row=2, column=0, sticky="nsew")

        results_frame = ttk.Frame(paned)
        detail_frame = ttk.LabelFrame(paned, text="選取結果明細", padding=8)
        paned.add(results_frame, weight=3)
        paned.add(detail_frame, weight=2)
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)
        detail_frame.columnconfigure(0, weight=1)

        cols = ("id", "name", "result", "status", "latency", "expected_tool", "actual_tool", "error")
        self.result_tree = ttk.Treeview(results_frame, columns=cols, show="headings", selectmode="browse")
        heads = {
            "id": "ID", "name": "Name", "result": "Result", "status": "HTTP",
            "latency": "Latency", "expected_tool": "Expected Tool", "actual_tool": "Actual Tool", "error": "Failure Type"
        }
        widths = {"id": 90, "name": 160, "result": 75, "status": 70, "latency": 90, "expected_tool": 170, "actual_tool": 170, "error": 130}
        for c in cols:
            self.result_tree.heading(c, text=heads[c])
            self.result_tree.column(c, width=widths[c], anchor="w")
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        rscroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.result_tree.yview)
        rscroll.grid(row=0, column=1, sticky="ns")
        self.result_tree.configure(yscrollcommand=rscroll.set)
        self.result_tree.tag_configure("fail")
        self.result_tree.bind("<<TreeviewSelect>>", self.show_result_detail)

        self.detail_text = tk.Text(detail_frame, wrap="word", height=10)
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        dscroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        dscroll.grid(row=0, column=1, sticky="ns")
        self.detail_text.configure(yscrollcommand=dscroll.set)

    def _build_reports_tab(self):
        tab = self.tab_reports
        tab.rowconfigure(2, weight=1)
        tab.columnconfigure(0, weight=1)

        exports = ttk.LabelFrame(tab, text="目前結果匯出", padding=10)
        exports.grid(row=0, column=0, sticky="ew")
        ttk.Button(exports, text="匯出 CSV", command=lambda: self.export_results("csv")).pack(side="left", padx=4)
        ttk.Button(exports, text="匯出 HTML 報告", command=lambda: self.export_results("html")).pack(side="left", padx=4)
        ttk.Button(exports, text="匯出 JSON", command=lambda: self.export_results("json")).pack(side="left", padx=4)
        ttk.Button(exports, text="開啟資料夾", command=self.open_app_dir).pack(side="right", padx=4)

        ttk.Label(tab, text="歷史 Run", font=("Segoe UI", 11, "bold")).grid(row=1, column=0, sticky="w", pady=(12, 5))
        cols = ("id", "started", "endpoint", "total", "passed", "failed", "rate", "avg", "p95")
        self.history_tree = ttk.Treeview(tab, columns=cols, show="headings")
        names = {"id": "#", "started": "Time", "endpoint": "Endpoint", "total": "Total", "passed": "Passed", "failed": "Failed", "rate": "Pass Rate", "avg": "Avg ms", "p95": "P95 ms"}
        widths = {"id": 55, "started": 145, "endpoint": 330, "total": 70, "passed": 70, "failed": 70, "rate": 90, "avg": 90, "p95": 90}
        for c in cols:
            self.history_tree.heading(c, text=names[c])
            self.history_tree.column(c, width=widths[c], anchor="w")
        self.history_tree.grid(row=2, column=0, sticky="nsew")
        self.history_tree.bind("<Double-1>", self.load_history_into_results)

        footer = ttk.Frame(tab)
        footer.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(
            footer,
            text="HTML 報告包含 Pass Rate、Avg/P95 Latency、失敗分類與每筆 Case 明細。",
            style="Subtitle.TLabel",
        ).pack(side="left")
        ttk.Button(footer, text="重新整理歷史", command=self._refresh_history).pack(side="right")

    def _config_from_ui(self) -> ApiConfig:
        config = ApiConfig(
            url=self.api_url.get().strip(),
            method=self.api_method.get().strip() or "POST",
            headers_json=self.headers_text.get("1.0", "end").strip(),
            bearer_token=self.api_token.get().strip(),
            body_template=self.body_text.get("1.0", "end").strip(),
            timeout_sec=float(self.api_timeout.get() or 30),
            answer_path=self.answer_path.get().strip(),
            tool_path=self.tool_path.get().strip(),
            arguments_path=self.arguments_path.get().strip(),
            sources_path=self.sources_path.get().strip(),
        )
        json.loads(config.headers_json or "{}")
        if config.method in {"POST", "PUT", "PATCH", "DELETE"} and "json" in config.headers_json.lower():
            # Validate template with a harmless sample.
            json.loads(config.body_template.replace("{{input}}", "sample"))
        return config

    def save_current_config(self):
        try:
            self.config_obj = self._config_from_ui()
            save_config(self.config_obj)
            messagebox.showinfo("已儲存", "設定已儲存；Bearer Token / API Key 不會寫入硬碟。")
        except Exception as exc:
            messagebox.showerror("設定錯誤", str(exc))

    def _load_demo_if_empty(self):
        if not self.cases and (not self.config_obj.url or self.config_obj.url == "mock://agent"):
            self.load_demo(show_message=False)

    def load_demo(self, show_message=True):
        self.api_url.set("mock://agent")
        self.api_method.set("POST")
        self.api_token.set("")
        self.api_timeout.set("5")
        self.answer_path.set("answer")
        self.tool_path.set("tool")
        self.arguments_path.set("arguments")
        self.sources_path.set("sources")
        self.headers_text.delete("1.0", "end")
        self.headers_text.insert("1.0", '{"Content-Type": "application/json"}')
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", '{"message": "{{input}}"}')
        self.cases = [
            TestCase("T001", "查詢訂單", "幫我查訂單 A001", "200", "get_order_status", '{"order_id":"A001"}', "配送", "", "", "", 1, 1500, True, "Tool Calling"),
            TestCase("T002", "取消訂單", "請取消訂單 A002", "200", "cancel_order", '{"order_id":"A002"}', "取消", "", "", "", 0, 1500, True, "Tool Calling"),
            TestCase("T003", "不存在訂單", "幫我查訂單 BAD999", "200", "get_order_status", '{"order_id":"BAD999"}', "找不到", "", "", "", 0, 1500, True, "Boundary"),
            TestCase("T004", "缺少編號", "幫我查訂單", "200", "", "", "提供|訂單", "", "", "", 0, 1500, True, "Missing Data"),
        ]
        self._refresh_cases()
        if show_message:
            messagebox.showinfo("Demo 已載入", "現在可直接到「執行與結果」按「開始測試」，不需要任何 API Key。")

    def test_connection(self):
        try:
            config = self._config_from_ui()
            self.connection_status.config(text="Testing...")
            self.update_idletasks()
            probe = TestCase("PROBE", "Connection Probe", "幫我查訂單 A001", expected_status="200")
            result = evaluate_case(config, probe)
            if result.status_code == 200:
                self.connection_status.config(text=f"✓ Connected · {result.latency_ms:.0f} ms")
            else:
                self.connection_status.config(text=f"✗ HTTP {result.status_code} · {result.error_category or 'Error'}")
                if result.failures:
                    messagebox.showwarning("連線測試", "\n".join(result.failures))
        except Exception as exc:
            self.connection_status.config(text="✗ Failed")
            messagebox.showerror("連線失敗", str(exc))

    def _browser_config_from_ui(self) -> BrowserConfig:
        url = self.browser_url.get().strip()
        if not url:
            raise ValueError("Browser Auto 的 Target URL 尚未設定")
        if not self.browser_input_selector.get().strip():
            raise ValueError("Input selector 不可空白")
        if not self.browser_response_selector.get().strip():
            raise ValueError("Response selector 不可空白")
        config = BrowserConfig(
            url=url,
            browser_channel=self.browser_channel.get().strip() or "msedge",
            input_selector=self.browser_input_selector.get().strip(),
            send_selector=self.browser_send_selector.get().strip(),
            response_selector=self.browser_response_selector.get().strip(),
            new_chat_selector=self.browser_new_chat_selector.get().strip(),
            tool_selector=self.browser_tool_selector.get().strip(),
            arguments_selector=self.browser_arguments_selector.get().strip(),
            sources_selector=self.browser_sources_selector.get().strip(),
            ready_selector=self.browser_ready_selector.get().strip(),
            timeout_ms=max(1000, int(self.browser_timeout_ms.get() or 60000)),
            settle_ms=max(250, int(self.browser_settle_ms.get() or 1200)),
        )
        save_browser_settings(asdict(config))
        self.browser_settings = asdict(config)
        return config

    def open_browser_login(self):
        try:
            config = self._browser_config_from_ui()
        except Exception as exc:
            messagebox.showerror("Browser 設定錯誤", str(exc))
            return

        self.browser_status.config(text="Browser 已開啟；完成登入後請直接關閉 Browser")

        def worker():
            try:
                open_login_session(config)
                self.ui_queue.put(("browser_login_done",))
            except Exception as exc:
                self.ui_queue.put(("browser_login_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def load_browser_example(self):
        self.browser_url.set("https://your-agent.example.com/")
        self.browser_input_selector.set("textarea")
        self.browser_send_selector.set('button[type="submit"]')
        self.browser_response_selector.set(".agent-response")
        self.browser_new_chat_selector.set(".new-chat")
        self.browser_tool_selector.set(".tool-name")
        self.browser_arguments_selector.set(".tool-arguments")
        self.browser_sources_selector.set(".source-item")
        self.browser_ready_selector.set("textarea")
        messagebox.showinfo(
            "Selector 範例",
            "已填入示意 selector。這些不是任何特定網站的固定值，請用目標 Agent 網頁的實際 DOM selector 取代。",
        )

    def _manual_case_from_selection(self) -> TestCase | None:
        value = self.manual_case_var.get().strip()
        if not value:
            return None
        case_id = value.split(" — ", 1)[0]
        for case in self.cases:
            if case.case_id == case_id:
                return case
        return None

    def _refresh_manual_cases(self):
        if not hasattr(self, "manual_case_combo"):
            return
        values = [f"{c.case_id} — {c.name}" for c in self.cases if c.enabled]
        self.manual_case_combo["values"] = values
        if values:
            current = self.manual_case_var.get()
            if current not in values:
                self.manual_case_var.set(values[0])
            self._load_manual_case()
        else:
            self.manual_case_var.set("")
            self.manual_input_text.config(state="normal")
            self.manual_input_text.delete("1.0", "end")
            self.manual_input_text.config(state="disabled")
            self.manual_expected_label.config(text="尚無啟用的 Test Case")

    def _load_manual_case(self):
        case = self._manual_case_from_selection()
        if not case:
            return
        self.manual_input_text.config(state="normal")
        self.manual_input_text.delete("1.0", "end")
        self.manual_input_text.insert("1.0", case.input_text)
        self.manual_input_text.config(state="disabled")
        expected = [
            f"Expected Tool: {case.expected_tool or 'N/A'}",
            f"Expected Arguments: {case.expected_args_json or 'N/A'}",
            f"Must contain: {case.must_contain or 'N/A'}",
            f"Must not contain: {case.must_not_contain or 'N/A'}",
            f"Min sources: {case.min_sources}",
            f"Max latency: {case.max_latency_ms or 'N/A'} ms",
        ]
        self.manual_expected_label.config(text="\n".join(expected))

    def copy_manual_input(self):
        case = self._manual_case_from_selection()
        if not case:
            return
        self.clipboard_clear()
        self.clipboard_append(case.input_text)
        self.update()
        messagebox.showinfo("已複製", "Test Case Input 已複製到剪貼簿。")

    def next_manual_case(self):
        values = list(self.manual_case_combo["values"])
        if not values:
            return
        try:
            index = values.index(self.manual_case_var.get())
        except ValueError:
            index = -1
        self.manual_case_var.set(values[(index + 1) % len(values)])
        self._load_manual_case()
        self.clear_manual_actual()

    def clear_manual_actual(self):
        self.manual_response_text.delete("1.0", "end")
        self.manual_tool_var.set("")
        self.manual_args_var.set("")
        self.manual_sources_var.set("0")
        self.manual_latency_var.set("0")
        self.manual_status_var.set("")

    def evaluate_manual(self):
        case = self._manual_case_from_selection()
        if not case:
            messagebox.showinfo("沒有 Test Case", "請先建立並啟用 Test Case。")
            return
        try:
            status_text = self.manual_status_var.get().strip()
            obs = Observation(
                answer=self.manual_response_text.get("1.0", "end").rstrip("\n"),
                tool=self.manual_tool_var.get().strip(),
                arguments_json=self.manual_args_var.get().strip(),
                source_count=max(0, int(self.manual_sources_var.get() or 0)),
                latency_ms=max(0.0, float(self.manual_latency_var.get() or 0)),
                status_code=int(status_text) if status_text else None,
                origin="manual-ui",
            )
            result = evaluate_observation(case, obs)
        except Exception as exc:
            messagebox.showerror("Manual Evaluate 錯誤", str(exc))
            return

        self.results = [result]
        self.result_by_iid.clear()
        for iid in self.result_tree.get_children():
            self.result_tree.delete(iid)
        self._append_result_to_tree(result)
        self._update_metrics()
        save_run(time.strftime("%Y-%m-%d %H:%M:%S"), "manual-ui", [result])
        self._refresh_history()
        self.tabs.select(self.tab_run)
        messagebox.showinfo(
            "Evaluation 完成",
            "PASS" if result.passed else "FAIL\n\n" + "\n".join(result.failures),
        )

    def _refresh_cases(self):
        if not hasattr(self, "case_tree"):
            return
        for iid in self.case_tree.get_children():
            self.case_tree.delete(iid)
        for idx, case in enumerate(self.cases):
            self.case_tree.insert(
                "", "end", iid=str(idx),
                values=(
                    "✓" if case.enabled else "",
                    case.case_id,
                    case.name,
                    case.category,
                    case.input_text.replace("\n", " ")[:120],
                    case.expected_status,
                    case.expected_tool,
                    f"{case.max_latency_ms} ms" if case.max_latency_ms else "-",
                )
            )
        enabled = sum(1 for c in self.cases if c.enabled)
        self.case_count_label.config(text=f"{enabled} enabled / {len(self.cases)} total")
        save_cases(self.cases)
        self._refresh_manual_cases()

    def _selected_case_index(self) -> int | None:
        sel = self.case_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def add_case(self):
        editor = CaseEditor(self)
        self.wait_window(editor)
        if editor.result:
            self.cases.append(editor.result)
            self._refresh_cases()

    def edit_case(self):
        idx = self._selected_case_index()
        if idx is None:
            messagebox.showinfo("請選擇", "先選一個 Test Case。")
            return
        editor = CaseEditor(self, self.cases[idx])
        self.wait_window(editor)
        if editor.result:
            self.cases[idx] = editor.result
            self._refresh_cases()

    def delete_case(self):
        idx = self._selected_case_index()
        if idx is None:
            return
        case = self.cases[idx]
        if messagebox.askyesno("刪除 Case", f"刪除 {case.case_id} - {case.name}？"):
            self.cases.pop(idx)
            self._refresh_cases()

    def add_edge_cases(self):
        base = self.cases[0] if self.cases else TestCase("BASE", "Base", "測試")
        edge = generate_edge_cases(base, start_index=len(self.cases) + 1)
        self.cases.extend(edge)
        self._refresh_cases()
        messagebox.showinfo("Edge Cases", f"已新增 {len(edge)} 個常見邊界/異常案例；請依公司規格調整 Expected Result。")

    def import_cases_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            imported = []
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=1):
                    imported.append(TestCase(
                        case_id=row.get("case_id") or row.get("id") or f"CSV-{i:03d}",
                        name=row.get("name") or f"Case {i}",
                        input_text=row.get("input_text") or row.get("input") or row.get("question") or "",
                        expected_status=row.get("expected_status") or "200",
                        expected_tool=row.get("expected_tool") or "",
                        expected_args_json=row.get("expected_args_json") or "",
                        must_contain=row.get("must_contain") or "",
                        must_not_contain=row.get("must_not_contain") or "",
                        expected_json_path=row.get("expected_json_path") or "",
                        expected_json_value=row.get("expected_json_value") or "",
                        min_sources=int(row.get("min_sources") or 0),
                        max_latency_ms=int(row.get("max_latency_ms") or 0),
                        enabled=str(row.get("enabled", "true")).lower() not in {"0", "false", "no"},
                        category=row.get("category") or "Functional",
                    ))
            self.cases.extend(imported)
            self._refresh_cases()
            messagebox.showinfo("匯入完成", f"已匯入 {len(imported)} 個 Test Cases。")
        except Exception as exc:
            messagebox.showerror("匯入失敗", str(exc))

    def export_cases_csv(self):
        if not self.cases:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="test_cases.csv")
        if not path:
            return
        fields = list(asdict(self.cases[0]).keys())
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for case in self.cases:
                writer.writerow(asdict(case))
        messagebox.showinfo("完成", f"已輸出：\n{path}")

    def _append_result_to_tree(self, result: TestResult) -> None:
        iid = str(len(self.result_by_iid))
        self.result_by_iid[iid] = result
        self.result_tree.insert(
            "", "end", iid=iid,
            values=(
                result.case_id,
                result.name,
                "PASS" if result.passed else "FAIL",
                "" if result.status_code is None else result.status_code,
                f"{result.latency_ms:.0f} ms",
                result.expected_tool,
                result.actual_tool,
                result.error_category,
            ),
            tags=("pass" if result.passed else "fail",),
        )

    def start_run(self):
        if self.running:
            return

        mode = self.run_mode_var.get().strip() or "API Auto"
        try:
            workers = max(1, int(self.workers_var.get()))
            repeats = max(1, int(self.repeats_var.get()))
            if mode == "Browser Auto":
                browser_config = self._browser_config_from_ui()
                api_config = None
                self.current_run_origin = f"browser:{browser_config.url}"
            else:
                api_config = self._config_from_ui()
                browser_config = None
                self.config_obj = api_config
                save_config(api_config)
                self.current_run_origin = api_config.url
        except Exception as exc:
            messagebox.showerror("設定錯誤", str(exc))
            return

        enabled_cases = [c for c in self.cases if c.enabled]
        if not enabled_cases:
            messagebox.showinfo("沒有 Case", "請至少啟用一個 Test Case。")
            return

        self.results = []
        self.result_by_iid.clear()
        for iid in self.result_tree.get_children():
            self.result_tree.delete(iid)
        self.detail_text.delete("1.0", "end")
        self.stop_event.clear()
        self.running = True
        self.run_button.config(state="disabled")
        self.stop_button.config(state="normal")
        total = len(enabled_cases) * repeats
        self.progress.config(maximum=total, value=0)
        self.progress_label.config(text=f"{mode} · 0 / {total}")
        self._update_metrics()

        started_at = time.strftime("%Y-%m-%d %H:%M:%S")

        def worker():
            try:
                def on_result(result, done, total_count):
                    self.ui_queue.put(("result", result, done, total_count))
                if mode == "Browser Auto":
                    results = run_browser_suite(
                        browser_config,
                        enabled_cases,
                        repeats=repeats,
                        on_result=on_result,
                        should_stop=self.stop_event.is_set,
                    )
                else:
                    results = run_suite(
                        api_config,
                        enabled_cases,
                        workers=workers,
                        repeats=repeats,
                        on_result=on_result,
                        should_stop=self.stop_event.is_set,
                    )
                self.ui_queue.put(("done", started_at, results))
            except StopRequested:
                self.ui_queue.put(("stopped",))
            except Exception as exc:
                self.ui_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def stop_run(self):
        self.stop_event.set()
        self.progress_label.config(text="Stopping...")

    def _drain_ui_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                kind = item[0]
                if kind == "result":
                    _, result, done, total = item
                    self.results.append(result)
                    self._append_result_to_tree(result)
                    self.progress.config(value=done)
                    self.progress_label.config(text=f"{done} / {total}")
                    self._update_metrics()
                elif kind == "done":
                    _, started_at, results = item
                    self.results = results
                    self.running = False
                    self.run_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.progress_label.config(text="Completed")
                    save_run(started_at, self.current_run_origin or "unknown", results)
                    self._update_metrics()
                    self._refresh_history()
                    self.tabs.select(self.tab_run)
                elif kind == "stopped":
                    self.running = False
                    self.run_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.progress_label.config(text="Stopped")
                elif kind == "error":
                    self.running = False
                    self.run_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.progress_label.config(text="Error")
                    messagebox.showerror("測試失敗", item[1])
                elif kind == "browser_login_done":
                    self.browser_status.config(text="登入 Browser 已關閉；Session 已保存")
                elif kind == "browser_login_error":
                    self.browser_status.config(text="Browser 啟動失敗")
                    messagebox.showerror("Browser Auto", item[1])
        except queue.Empty:
            pass
        self.after(100, self._drain_ui_queue)

    def _update_metrics(self):
        s = summarize_results(self.results)
        self.metric_vars["total"].set(str(s["total"]))
        self.metric_vars["pass_rate"].set(f'{s["pass_rate"]:.1f}%')
        self.metric_vars["failed"].set(str(s["failed"]))
        self.metric_vars["avg"].set(f'{s["avg_latency_ms"]:.0f} ms')
        self.metric_vars["p95"].set(f'{s["p95_latency_ms"]:.0f} ms')

    def show_result_detail(self, _event=None):
        sel = self.result_tree.selection()
        if not sel:
            return
        r = self.result_by_iid.get(sel[0])
        if not r:
            return
        payload = {
            "case": {"id": r.case_id, "name": r.name, "category": r.category, "input": r.input_text},
            "result": "PASS" if r.passed else "FAIL",
            "status_code": r.status_code,
            "latency_ms": round(r.latency_ms, 2),
            "expected_tool": r.expected_tool,
            "actual_tool": r.actual_tool,
            "source_count": r.source_count,
            "failure_category": r.error_category,
            "failures": r.failures,
            "request_url": r.request_url,
            "request_body": r.request_body,
            "answer": r.answer,
            "response": r.response_json if r.response_json is not None else r.response_text,
        }
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2))

    def export_results(self, kind: str):
        if not self.results:
            messagebox.showinfo("沒有結果", "請先執行測試或從歷史紀錄載入結果。")
            return
        exts = {"csv": ".csv", "html": ".html", "json": ".json"}
        path = filedialog.asksaveasfilename(
            defaultextension=exts[kind],
            filetypes=[(kind.upper(), f"*{exts[kind]}")],
            initialfile=f"agent_qa_report_{time.strftime('%Y%m%d_%H%M%S')}{exts[kind]}",
        )
        if not path:
            return
        if kind == "csv":
            export_csv(path, self.results)
        elif kind == "html":
            export_html(path, self.results)
        else:
            export_json(path, self.results)
        if messagebox.askyesno("報告完成", f"已輸出：\n{path}\n\n要現在開啟嗎？"):
            os.startfile(path)

    def _refresh_history(self):
        if not hasattr(self, "history_tree"):
            return
        for iid in self.history_tree.get_children():
            self.history_tree.delete(iid)
        for row in list_runs():
            self.history_tree.insert(
                "", "end", iid=str(row["id"]),
                values=(
                    row["id"], row["started_at"], row["endpoint"], row["total"],
                    row["passed"], row["failed"], f'{row["pass_rate"]:.1f}%',
                    f'{row["avg_latency_ms"]:.0f}', f'{row["p95_latency_ms"]:.0f}',
                )
            )

    def load_history_into_results(self, _event=None):
        sel = self.history_tree.selection()
        if not sel:
            return
        rows = load_run(int(sel[0]))
        loaded = []
        for d in rows:
            allowed = TestResult.__dataclass_fields__.keys()
            loaded.append(TestResult(**{k: d.get(k) for k in allowed}))
        self.results = loaded
        self.result_by_iid.clear()
        for iid in self.result_tree.get_children():
            self.result_tree.delete(iid)
        for i, r in enumerate(self.results):
            iid = str(i)
            self.result_by_iid[iid] = r
            self.result_tree.insert(
                "", "end", iid=iid,
                values=(r.case_id, r.name, "PASS" if r.passed else "FAIL", r.status_code, f"{r.latency_ms:.0f} ms", r.expected_tool, r.actual_tool, r.error_category)
            )
        self._update_metrics()
        self.tabs.select(self.tab_run)

    def open_app_dir(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(APP_DIR)


def _packaged_browser_self_test() -> int:
    fixture = Path(os.getenv("TEMP", str(Path.home()))) / "agent_qa_studio_browser_self_test.html"
    fixture.write_text(
        """<!doctype html><meta charset="utf-8">
<textarea id="prompt"></textarea><button id="send">Send</button><div id="responses"></div>
<script>
document.getElementById("send").addEventListener("click", () => {
  const q = document.getElementById("prompt").value;
  setTimeout(() => {
    const d = document.createElement("div");
    d.className = "agent-response";
    d.textContent = q.includes("A001") ? "訂單 A001 目前配送中" : "收到：" + q;
    document.getElementById("responses").appendChild(d);
  }, 100);
});
</script>""",
        encoding="utf-8",
    )
    try:
        config = BrowserConfig(
            url=fixture.resolve().as_uri(),
            browser_channel="msedge",
            input_selector="#prompt",
            send_selector="#send",
            response_selector=".agent-response",
            timeout_ms=10000,
            settle_ms=300,
            user_data_dir=str(Path(os.getenv("TEMP", str(Path.home()))) / "AgentQAStudioSelfTestProfile"),
            headless=True,
        )
        case = TestCase(
            "SELFTEST",
            "Packaged Browser Auto self-test",
            "幫我查 A001",
            must_contain="配送",
            max_latency_ms=5000,
        )
        results = run_browser_suite(config, [case])
        return 0 if len(results) == 1 and results[0].passed else 2
    except Exception:
        return 3
    finally:
        try:
            fixture.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    if "--self-test-browser" in sys.argv:
        raise SystemExit(_packaged_browser_self_test())
    app = AgentQAStudio()
    app.mainloop()
