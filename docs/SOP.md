# QA SOP

## SOP 1 — New Agent feature acceptance

```mermaid
flowchart TD
    A[Receive feature specification] --> B[Identify expected behavior]
    B --> C[Create positive Test Cases]
    C --> D[Create negative / Edge Cases]
    D --> E{Interface available?}
    E -->|API| F[API Auto]
    E -->|Web UI only| G[Browser Auto]
    E -->|Manual-only UI| H[Manual UI]
    F --> I[Collect Actual Results]
    G --> I
    H --> I
    I --> J[Unified Evaluation]
    J --> K{PASS?}
    K -->|Yes| L[Record evidence / report]
    K -->|No| M[Classify failure]
    M --> N[Reproduce]
    N --> O[Bug report to developer]
    O --> P[Fix / prompt / RAG / flow update]
    P --> Q[Regression test]
    Q --> J
```

## SOP 2 — Tool Calling evaluation

```mermaid
flowchart LR
    A[User request] --> B[Expected Tool]
    A --> C[Expected Arguments]
    D[Actual Agent result] --> E[Actual Tool]
    D --> F[Actual Arguments]
    B --> G{Tool equal?}
    E --> G
    C --> H{Expected args subset of Actual?}
    F --> H
    G --> I[Result]
    H --> I
```

Checklist:

1. Is the tool selected for the correct intent?
2. Are required arguments present?
3. Are identifiers copied correctly?
4. Does missing input trigger clarification instead of hallucination?
5. Does tool failure produce a safe response?
6. Is the agent prevented from silently pretending the tool succeeded?

## SOP 3 — RAG evaluation

```mermaid
flowchart TD
    A[Question] --> B[Retrieval]
    B --> C{Relevant context found?}
    C -->|No| D[Retrieval failure]
    C -->|Yes| E[Generation]
    E --> F{Answer grounded?}
    F -->|No| G[Generation / hallucination failure]
    F -->|Yes| H[Check citation/source]
    H --> I[PASS / further quality review]
```

When the answer is wrong, separate:

- Retrieval problem
- Generation problem
- source/knowledge problem
- prompt/instruction problem
- tool-routing problem

## SOP 4 — Regression suite

```mermaid
flowchart LR
    A[Baseline Test Cases] --> B[New build]
    B --> C[Smoke Suite]
    C -->|Fail| D[Stop / investigate]
    C -->|Pass| E[Regression Suite]
    E --> F[Compare pass rate + failure categories]
    F --> G[Performance / P95]
    G --> H[Release evidence]
```

Recommended layers:

- Smoke: critical happy paths
- Functional regression
- Edge/corner cases
- RAG/tool-calling cases
- performance/latency cases

## SOP 5 — Failure triage

```mermaid
flowchart TD
    A[Test FAIL] --> B{HTTP / network?}
    B -->|Yes| C[API / Network]
    B -->|No| D{Wrong tool?}
    D -->|Yes| E[Tool Calling]
    D -->|No| F{Wrong args?}
    F -->|Yes| G[Tool Arguments]
    F -->|No| H{Missing sources?}
    H -->|Yes| I[RAG / Sources]
    H -->|No| J{Answer rule failed?}
    J -->|Yes| K[Answer Quality]
    J -->|No| L{Latency threshold failed?}
    L -->|Yes| M[Performance]
    L -->|No| N[Schema / Other]
```

## Bug report template

```text
Title:
[Agent][Tool Calling] Wrong tool selected for order cancellation

Environment:
Staging / build version

Case ID:
T042

Input:
取消訂單 A002

Expected:
Tool = cancel_order
Arguments = {"order_id":"A002"}

Actual:
Tool = get_order_status

Result:
FAIL

Reproduction:
1. Start new chat.
2. Submit the input.
3. Observe tool trace.

Evidence:
Agent QA Studio HTML/JSON report

Notes:
Reproducible 5/5 times.
```
