# Phase 4D — Memory Analysis: BoundedList

## Problem

Before this change, `retrieved_chunks` and `error_log` in `RAGState` were
plain Python lists with no growth limit. Over repeated healing retries
(up to `max_retries=3` per cycle, across many cycles) these lists could grow
without bound, causing:

| Field | Before | Risk |
|---|---|---|
| `retrieved_chunks` | `List[RetrievedChunk]` | Each retry appended N chunks. After many sessions the list grows large. |
| `error_log` | `Annotated[List[str], operator.add]` | Each error appended a string. Repeated healing cycles → unbounded entries. |

## Solution

`BoundedList[T]` — a `UserList` subclass with a configurable `maxlen`.
Oldest items are evicted when the list exceeds capacity.

### Capacity Selections

| Field | Maxlen | Rationale |
|---|---|---|
| `retrieved_chunks` | 20 | Most retrievals return ≤ 10 chunks. Across 2–3 retries, 20 is ample headroom. |
| `error_log` | 50 | Healing cycles produce a handful of errors per cycle. 50 entries captures full trace without unbounded growth. |

Both constants are defined in `backend/graph/state.py` and can be tuned
without code changes.

## Memory Bound Proof

Let **M** = maxlen. Each item is a Python object pointer (8 bytes on 64-bit)
plus the object itself. For strings (error_log) this is ~49 + len(str) bytes
per entry. For `RetrievedChunk` (dataclass with 5 fields) ~200–500 bytes per
entry depending on string content.

| Field | M | Worst-case per-field memory |
|---|---|---|
| `retrieved_chunks` | 20 | 20 × ~500B = ~10 KB |
| `error_log` | 50 | 50 × ~200B = ~10 KB |

**Total worst-case**: ~20 KB per state object — **bounded and constant**,
independent of session duration or retry count.

## Without BoundedList

- A session with 100 retries would accumulate:
  - `retrieved_chunks`: 100 × 5 chunks = 500 entries (~250 KB)
  - `error_log`: 100 × 2 errors = 200 entries (~40 KB)
  - **Total**: ~290 KB and growing linearly with retries.

With `BoundedList`, both fields are **O(M)** where M is a small constant.

## Impact on Other Fields

Other list fields (`citations`, `long_term_insights`, `planner_plan` sub-lists)
are small by nature and remain plain lists. If they show growth patterns in
production they should be migrated similarly.