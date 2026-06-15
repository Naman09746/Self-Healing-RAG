# Wireframes — Self-Healing RAG Pipeline

## Overview

This document describes the key UI screens for the Self-Healing RAG Pipeline application. Each screen is described textually with layout specifications suitable for implementation.

---

## Screen 1: Login / Signup

### Layout

```
┌─────────────────────────────────┐
│  ┌───────────────────────────┐   │
│  │   🔄 Self-Healing RAG    │   │
│  │                           │   │
│  │   ┌─────────────────┐     │   │
│  │   │ [Tab: Login │    │     │   │
│  │   │  Signup]        │     │   │
│  │   └─────────────────┘     │   │
│  │                           │   │
│  │   Email:                  │   │
│  │   ┌─────────────────┐     │   │
│  │   │ user@example.com │     │   │
│  │   └─────────────────┘     │   │
│  │                           │   │
│  │   Password:               │   │
│  │   ┌─────────────────┐     │   │
│  │   │ ********        │     │   │
│  │   └─────────────────┘     │   │
│  │                           │   │
│  │   ┌─────────────────┐     │   │
│  │   │   Sign In        │     │   │
│  │   └─────────────────┘     │   │
│  │                           │   │
│  │   Forgot password?        │   │
│  └───────────────────────────┘   │
└─────────────────────────────────┘
```

### Behavior

| Element | Action |
|---------|--------|
| Tab: Login | Shows email + password fields |
| Tab: Signup | Adds `Full Name` field, `Confirm Password` |
| "Sign In" button | Validates → calls `POST /auth/login` → redirects to `/chat` |
| "Forgot password?" | Placeholder — shows toast "Coming soon" |
| Error state | Red border on fields, error message below form |

---

## Screen 2: Chat / Query Interface

### Layout

```
┌─────────────────────────────────────────────────┐
│ 🔄 Self-Healing RAG         👤 admin@...  ⚙️  │ ← Header
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│                                                 │
│   ┌─────────────────────────────────────────┐   │
│   │  Welcome! Ask a question about your     │   │
│   │  documents.                             │   │
│   └─────────────────────────────────────────┘   │
│                                                 │
│   ┌─────────────────────────────────────────┐   │
│   │  User: What is the summary of           │   │
│   │  Project Omega?                         │   │
│   └─────────────────────────────────────────┘   │
│                                                 │
│   ┌── Phase Progress ─────────────────────┐   │
│   │  [✓ Intake] [✓ Plan] [● Retrieve]    │   │
│   │  [○ Generate] [○ Critic] [○ Output]  │   │
│   └─────────────────────────────────────────┘   │
│                                                 │
│   ┌── Response ─────────────────────────────┐   │
│   │  │ Project Omega is a strategic          │   │
│   │  │ initiative focused on...              │   │
│   │  │                                       │   │
│   │  │ Sources:                              │   │
│   │  │ 📄 project_omega_spec.pdf (score:  │   │
│   │  │ 0.89) · Chunk 4                      │   │
│   │  │ 📄 project_omega_spec.pdf (score:  │   │
│   │  │ 0.76) · Chunk 7                      │   │
│   │  │                                       │   │
│   │  │ Confidence: 85%   Healing: None    │   │
│   │  │ Latency: 3.4s                        │   │
│   │  └─────────────────────────────────────┘   │
│   │                                            │
│   │  [👍]  [👎]  [📋 Copy]                    │
│   └─────────────────────────────────────────┘   │
│                                                 │
│   ┌─────────────────────────────────────────┐   │
│   │  Ask a follow-up question...      [📤] │   │
│   └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Behavior

| Element | Action |
|---------|--------|
| Input | Type query, press Enter or click Send |
| Phase progress bar | Shows real-time phases as they complete (see phases below) |
| Response | Streams in token-by-token if WebSocket, or appears fully |
| Sources | Expandable — click to see full chunk text |
| Feedback | 👍 logs positive, 👎 opens feedback modal |
| Copy | Copies answer text to clipboard |

### Phase Progress States

```css
○ = Waiting (gray pill)
● = Active (blue pill with pulse animation)
✓ = Complete (green pill)
✗ = Error (red pill)
```

### States

| State | Visual |
|-------|--------|
| **Empty** | Welcome message with example queries |
| **Loading** | Phase progress bar animating, skeleton response card |
| **Streaming** | Phases completing, text appearing character-by-character |
| **Complete** | Full response with sources, feedback buttons enabled |
| **Error** | Red error banner with retry button |
| **Sidebar open** | History panel slides in from left |

---

## Screen 3: Dashboard

### Layout

```
┌─────────────────────────────────────────────────┐
│ 🔄 Self-Healing RAG    Dashboard   Admin  👤    │
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐│
│ │Queries  │ │Avg Conf │ │Avg Faith│ │Avg Lat ││
│ │  1,234  │ │  82%    │ │  0.87   │ │  2.1s  ││
│ │ +12%    │ │ +3%     │ │ +0.02   │ │ -8%    ││
│ └─────────┘ └─────────┘ └─────────┘ └────────┘│
│                                                 │
│ ┌── Performance Over Time ───────────────────┐  │
│ │                                             │  │
│ │  Confidence ───  Faithfulness ──·──        │  │
│ │  ▁▃▄▆▇█▇▆▅▄▃▂▁                             │  │
│ │  └───────────────────────────►              │  │
│ │  Last 30 days                               │  │
│ └─────────────────────────────────────────────┘  │
│                                                 │
│ ┌── Recent Queries ──────────────────────────┐  │
│ │  What is Project Omega?          85%  2.3s │  │
│ │  Who is the CEO?                 79%  1.8s │  │
│ │  When was Q4 report published?  92%  3.1s │  │
│ └─────────────────────────────────────────────┘  │
│                                                 │
│ ┌── Evaluation Results (Latest) ──────────────┐  │
│ │  Metric             Score    ──▌▌▌▌▌▌──    │  │
│ │  Faithfulness       0.87    ████████░░ 87% │  │
│ │  Answer Relevancy   0.92    █████████░ 92% │  │
│ │  Context Precision  0.81    ████████░░ 81% │  │
│ │  Run: eval_abc123 · 100 samples            │  │
│ └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Behavior

| Element | Action |
|---------|--------|
| Metric cards | Click to filter chart below |
| Performance chart | Line chart with toggles for metrics |
| Recent queries | Click to expand or re-run |
| Eval results | Click row to see per-sample breakdown |

---

## Screen 4: Admin Panel

### Layout

```
┌─────────────────────────────────────────────────┐
│ 🔄 Admin Panel    Users  Audit  Eval  Docs       │
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│ ┌── Tab: Users ───────────────────────────────┐│
│ │  Email               Role        Status     ││
│ │  ────────────────────────────────────────── ││
│ │  admin@example.com   Admin       ● Active  ││
│ │  editor@example.com  Editor      ● Active  ││
│ │  viewer@example.com  Viewer      ○ Inactive││
│ │  auditor@example.com Auditor     ● Active  ││
│ │                                            ││
│ │  [+ Add User]                              ││
│ └──────────────────────────────────────────────│
│                                                 │
│ ┌── Tab: Eval ───────────────────────────────┐ │
│ │  Run ID        Dataset        Status  Score │ │
│ │  ─────────────────────────────────────────  │ │
│ │  eval_abc123   default        ✓ Comp  0.87 │ │
│ │  eval_def456   custom_v1      ● Run...  —  │ │
│ │  eval_ghi789   regression     ✗ Fail   —   │ │
│ │                                            │ │
│ │  [Run Evaluation]                          │ │
│ └──────────────────────────────────────────────│
│                                                 │
│ ┌── Tab: Documents ──────────────────────────┐ │
│ │  File                    Chunks  Uploaded  │ │
│ │  ─────────────────────────────────────────  │ │
│ │  project_omega_spec.pdf    24    2h ago   │ │
│ │  incident_report.pdf      12    1d ago   │ │
│ │  q4_strategic_intel.pdf   31    3d ago   │ │
│ │                                            │ │
│ │  [Upload Document]                         │ │
│ └──────────────────────────────────────────────│
└─────────────────────────────────────────────────┘
```

### Tabs

| Tab | Content |
|-----|---------|
| **Users** | User table with role badges, add/edit/disable actions |
| **Audit** | Filterable audit log with event type, actor, timestamp |
| **Eval** | Evaluation runs table, run/rerun/compare actions |
| **Docs** | Document inventory with delete action |

---

## Responsive Breakpoints

| Breakpoint | Layout Changes |
|------------|----------------|
| < 640px (Mobile) | Single column, hamburger menu, full-width inputs |
| 640-1024px (Tablet) | 2-column metric grid, compact sidebar |
| > 1024px (Desktop) | Full layout as shown above |
| > 1280px (Wide) | Max-width container, extra padding |

---

## Color Coding

| Element | Color | CSS Variable |
|---------|-------|-------------|
| Phase: Waiting | Gray | `--text-muted` |
| Phase: Active | Blue | `--accent` |
| Phase: Complete | Green | `--success` |
| Phase: Error | Red | `--error` |
| Confidence high (≥85%) | Green | `--success` |
| Confidence medium (70-84%) | Amber | `--warning` |
| Confidence low (<70%) | Red | `--error` |
| Healing triggered | Amber badge | `--warning` |