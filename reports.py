from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from engine import TestResult, summarize_results


def export_csv(path: str, results: list[TestResult]) -> None:
    fields = [
        "case_id", "name", "category", "input_text", "passed", "status_code",
        "latency_ms", "expected_tool", "actual_tool", "answer", "source_count",
        "error_category", "failures", "request_url", "request_body", "response_text", "timestamp"
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            d = r.to_dict()
            d["failures"] = " | ".join(r.failures)
            writer.writerow({k: d.get(k, "") for k in fields})


def export_json(path: str, results: list[TestResult]) -> None:
    payload = {
        "summary": summarize_results(results),
        "results": [r.to_dict() for r in results],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_html(path: str, results: list[TestResult], title: str = "Agent QA Evaluation Report") -> None:
    s = summarize_results(results)
    rows = []
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        failures = "<br>".join(html.escape(x) for x in r.failures) or "-"
        rows.append(
            "<tr>"
            f"<td>{html.escape(r.case_id)}</td>"
            f"<td>{html.escape(r.name)}</td>"
            f"<td>{status}</td>"
            f"<td>{'' if r.status_code is None else r.status_code}</td>"
            f"<td>{r.latency_ms:.0f}</td>"
            f"<td>{html.escape(r.expected_tool)}</td>"
            f"<td>{html.escape(r.actual_tool)}</td>"
            f"<td>{html.escape(r.error_category)}</td>"
            f"<td>{failures}</td>"
            "</tr>"
        )

    cats = "".join(
        f"<li>{html.escape(k)}: <b>{v}</b></li>"
        for k, v in sorted(s["failure_categories"].items(), key=lambda kv: (-kv[1], kv[0]))
    ) or "<li>None</li>"

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#f5f7fb;color:#172033;margin:0;padding:28px}}
.wrap{{max-width:1200px;margin:auto}}
h1{{margin:0 0 20px}}
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0}}
.card{{background:white;border-radius:12px;padding:16px;box-shadow:0 2px 12px #00000010}}
.label{{color:#667085;font-size:13px}} .value{{font-size:24px;font-weight:700;margin-top:4px}}
section{{background:white;border-radius:12px;padding:18px;margin-top:14px;box-shadow:0 2px 12px #00000010}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:9px;border-bottom:1px solid #e8ecf3;text-align:left;vertical-align:top}}
th{{background:#f8fafc;position:sticky;top:0}}
</style>
</head>
<body><div class="wrap">
<h1>{html.escape(title)}</h1>
<div class="cards">
<div class="card"><div class="label">Total</div><div class="value">{s['total']}</div></div>
<div class="card"><div class="label">Pass Rate</div><div class="value">{s['pass_rate']:.1f}%</div></div>
<div class="card"><div class="label">Failed</div><div class="value">{s['failed']}</div></div>
<div class="card"><div class="label">Avg Latency</div><div class="value">{s['avg_latency_ms']:.0f} ms</div></div>
<div class="card"><div class="label">P95 Latency</div><div class="value">{s['p95_latency_ms']:.0f} ms</div></div>
</div>
<section><h2>Failure Categories</h2><ul>{cats}</ul></section>
<section><h2>Case Details</h2><table>
<thead><tr><th>ID</th><th>Name</th><th>Result</th><th>Status</th><th>Latency</th><th>Expected Tool</th><th>Actual Tool</th><th>Category</th><th>Failure Detail</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></section>
</div></body></html>"""
    Path(path).write_text(doc, encoding="utf-8")
