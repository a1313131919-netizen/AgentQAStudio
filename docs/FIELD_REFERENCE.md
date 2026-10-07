# Field Reference

This page explains the major UI fields and what to enter.

## API Auto

| Field | Meaning | Example | Notes |
|---|---|---|---|
| URL | API endpoint under test | `https://staging.example.com/api/chat` | Use the QA/staging endpoint supplied by the system owner. |
| Method | HTTP request method | POST | AI chat APIs commonly use POST. |
| Bearer Token / API Key | Authorization token | hidden | Not persisted by Agent QA Studio's API config saver. |
| Timeout (sec) | Maximum API wait time | 30 | Increase for slow models; do not hide real performance problems by setting it excessively high. |
| Headers JSON | HTTP headers | `{"Content-Type":"application/json"}` | Must be a JSON object. |
| Body Template | Request body template | `{"message":"{{input}}"}` | `{{input}}` becomes the Test Case Input. |
| Answer Path | Dot path to answer | `data.answer` | Arrays use numeric indexes, e.g. `choices.0.message.content`. |
| Tool Path | Dot path to tool name | `data.tool` | Leave blank if the API does not expose tool usage. |
| Arguments Path | Dot path to tool arguments | `data.arguments` | Used for Expected Arguments comparison. |
| Sources Path | Dot path to RAG sources | `data.sources` | List length becomes source count. |

## Browser Auto

| Field | Meaning | Example | Required? |
|---|---|---|---|
| Target URL | Web UI under test | `https://staging.example.com/agent` | Yes |
| Browser | Installed browser channel | `msedge` | Yes |
| Timeout (ms) | Max wait for UI/response | `60000` | Yes |
| Response settle (ms) | How long response text must stop changing before it is considered complete | `1200` | Yes |
| Input selector | CSS selector for prompt input | `textarea` | Yes |
| Send button selector | CSS selector for Send | `button[type="submit"]` | No; blank = press Enter |
| Response selector | CSS selector matching assistant responses | `.agent-response` | Yes |
| New Chat selector | Starts an isolated conversation before each case | `.new-chat` | Optional |
| Tool selector | Visible tool name element | `.tool-name` | Optional |
| Arguments selector | Visible tool arguments element | `.tool-arguments` | Optional |
| Sources selector | Each visible source/citation element | `.source-item` | Optional |
| Ready/Login selector | Element indicating logged-in/ready state | `textarea` | Optional |

### How CSS selectors work

Examples:

```text
#prompt                element with id="prompt"
.agent-response        element with class="agent-response"
textarea               any textarea
button[type="submit"]  submit button
[data-testid="send"]   element with data-testid="send"
```

Selectors are product-specific and may change when the UI changes.

## Test Case fields

| Field | Meaning | Example |
|---|---|---|
| Case ID | Stable identifier | T001 |
| Name | Human-readable purpose | 查詢訂單 |
| Category | Test grouping | Tool Calling |
| Input | Prompt/user request | 幫我查訂單 A001 |
| Expected HTTP Status | Valid API status(es) | 200 or `200,201` |
| Expected Tool | Tool/function the agent should select | get_order_status |
| Expected Arguments JSON | Required subset of arguments | `{"order_id":"A001"}` |
| Must contain | Required answer terms, separated by `|` | `配送|A001` |
| Must not contain | Forbidden terms | `不存在|失敗` |
| Extra JSON Path | Extra response field to inspect in API mode | `meta.safe` |
| JSON Path Expected Value | Expected value at that path | `true` |
| Min Sources | Minimum RAG/source count | 1 |
| Max Latency (ms) | Performance gate; 0 = no gate | 3000 |
| Enabled | Include case in batch execution | checked |

### Expected Arguments uses subset matching

If Expected is:

```json
{"order_id":"A001"}
```

Actual can still pass when it contains extra fields:

```json
{"order_id":"A001","locale":"zh-TW"}
```

because the required subset is correct.

## Manual UI fields

| Field | Meaning |
|---|---|
| Actual Response | Visible response copied from the system under test. |
| Observed Tool | Tool name only when the UI exposes it. |
| Observed Arguments JSON | Arguments only when visible. |
| Sources count | Number of visible citations/sources. |
| Latency ms | Manually measured/observed latency. 0 means not evaluated. |
| HTTP status | Optional; usually not visible in a normal UI. |

Never invent hidden fields just to make a Test Case pass.

## Execution fields

| Field | Meaning |
|---|---|
| Mode | API Auto or Browser Auto. |
| Concurrent Workers | Parallel API requests. Browser Auto remains sequential. |
| Repeats | Runs each enabled case N times. Useful for non-determinism and regression. |

## Metrics

- **Pass Rate** = passed cases / total cases.
- **Avg Latency** = arithmetic mean of recorded latency.
- **P95 Latency** = 95% of recorded cases are at or below this latency.
- **Failure Type** groups failures such as Tool Calling, Tool Arguments, RAG/Sources, Answer Quality, Performance, API/Network, and Response Schema.
