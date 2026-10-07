# User Guide

## Concept

Each Test Case contains:

```text
Input
+ Expected Result
= Test specification
```

An execution mode produces Actual Result:

```text
API / Browser / Manual
        ↓
Actual Result
        ↓
Expected vs Actual
        ↓
PASS / FAIL
```

You do not need to write Python `assert` statements.

## SOP A — Create a Test Case

1. Open **4 Test Cases**.
2. Click **新增 Case**.
3. Fill:
   - Case ID
   - Name
   - Category
   - Input
   - Expected fields that are relevant
4. Save.
5. Repeat or import CSV.

Recommended categories:

- Functional
- Tool Calling
- RAG
- Boundary
- Encoding
- Conversation
- Safety
- Performance
- Other

### Example

```text
Case ID: T001
Name: 查詢訂單
Input: 幫我查訂單 A001
Expected Tool: get_order_status
Expected Arguments JSON: {"order_id":"A001"}
Must contain: 配送
Min sources: 1
Max latency: 3000
```

## SOP B — API Auto

1. Open **1 API Auto**.
2. Enter URL and HTTP Method.
3. Enter Bearer Token if required.
4. Enter Headers JSON.
5. Enter Body Template.
6. Configure Response Mapping.
7. Click **測試連線**.
8. Open **5 執行與結果**.
9. Select **API Auto**.
10. Choose Concurrent Workers and Repeats.
11. Click **開始測試**.

### Body Template

```json
{"message": "{{input}}"}
```

`{{input}}` is replaced with the Test Case Input.

### Response Mapping example

API response:

```json
{
  "data": {
    "answer": "配送中",
    "tool": "get_order_status",
    "arguments": {"order_id": "A001"},
    "sources": [{"id": "db-1"}]
  }
}
```

Set:

```text
Answer Path     data.answer
Tool Path       data.tool
Arguments Path  data.arguments
Sources Path    data.sources
```

## SOP C — Browser Auto

Use Browser Auto when the system is available as an authorized web UI but there is no API endpoint for QA.

1. Open **2 Browser Auto**.
2. Enter Target URL.
3. Choose Edge or Chrome.
4. Configure Input Selector.
5. Configure Response Selector.
6. Configure Send selector if Enter is not enough.
7. Optionally configure New Chat, Tool, Arguments, Sources, and Ready selectors.
8. Click **開啟登入 Browser**.
9. Log in manually if needed.
10. Close the browser window after login.
11. Open **5 執行與結果**.
12. Select **Browser Auto**.
13. Set Repeats.
14. Click **開始測試**.

Browser Auto is intentionally sequential because one persistent browser session should not be driven by multiple worker threads at the same time.

## SOP D — Manual UI

Use Manual UI when:

- there is no API,
- browser automation is not authorized or not stable,
- the UI uses canvas/remote desktop/non-DOM controls,
- a human judgment is required.

1. Open **3 Manual UI**.
2. Select a Test Case.
3. Click **複製 Input**.
4. Paste it into the AI system under test.
5. Copy the visible response back to **Actual Response**.
6. Fill Tool / Arguments / Sources / Latency only if visible or measured.
7. Leave hidden information blank.
8. Click **Evaluate → PASS / FAIL**.
9. Review the result under **5 執行與結果**.
10. Press **下一題**.

## SOP E — Edge Cases

In **4 Test Cases**, click **產生 Edge Cases**.

The generated starter cases include patterns such as:

- empty input
- whitespace
- very long input
- Unicode/emoji
- special characters
- conflicting correction
- missing identifier
- unknown identifier
- ambiguous request
- prompt-injection probe

These are templates. Adjust Expected Results to match the actual product specification before using them as release gates.

## Results

The result page shows:

- Total
- Pass Rate
- Failed
- Avg Latency
- P95 Latency
- Expected Tool
- Actual Tool
- Failure Type

Click a result row to inspect:

- Input
- status code
- latency
- expected/actual tool
- source count
- failures
- request URL
- request body
- answer
- raw response

## Reports

Open **6 報告與歷史**.

Available exports:

- CSV
- HTML
- JSON

Double-click a history row to reload a previous run into Results.

## Recommended regression practice

For a stable product, maintain three Test Case groups:

1. **Smoke** — 5–20 critical flows, runs on every change.
2. **Regression** — broad functional and edge coverage.
3. **Performance** — latency/repeat tests with controlled workload.

Do not mix destructive production actions into automated regression tests unless the environment and test data are specifically designed for it.
