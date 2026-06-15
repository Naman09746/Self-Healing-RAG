# Design System — Self-Healing RAG Pipeline

## Brand Identity

### Logo & Wordmark

The Self-Healing RAG Pipeline uses a simple, modern identity centered around the concept of **self-repair** and **knowledge flow**.

| Element | Specification |
|---------|---------------|
| **Icon** | Interlocking circles forming an infinity loop with a GPU node at center |
| **Wordmark** | "Self-Healing RAG" in Inter SemiBold, tracked at -0.02em |
| **Tagline** | "Autonomous Retrieval-Augmented Generation" |
| **Primary Color** | #2563EB (Blue 600) — Trust, intelligence |
| **Secondary Color** | #059669 (Emerald 600) — Healing, growth |
| **Accent Color** | #D97706 (Amber 500) — Warning, attention |

### Usage Guidelines

- Always use the full brand name "Self-Healing RAG Pipeline" in first mentions; abbreviate to "SHRAG" in constrained UI
- Do not modify the brand colors or icon proportions
- Maintain 2x spacing around the logo at all times

---

## Color System

### Core Palette

```css
/* Primary — Trust & Intelligence */
--primary-50:   #EFF6FF
--primary-100:  #DBEAFE
--primary-200:  #BFDBFE
--primary-300:  #93C5FD
--primary-400:  #60A5FA
--primary-500:  #3B82F6
--primary-600:  #2563EB
--primary-700:  #1D4ED8
--primary-800:  #1E40AF
--primary-900:  #1E3A8A

/* Emerald — Healing & Success */
--emerald-50:   #ECFDF5
--emerald-100:  #D1FAE5
--emerald-200:  #A7F3D0
--emerald-300:  #6EE7B7
--emerald-400:  #34D399
--emerald-500:  #10B981
--emerald-600:  #059669
--emerald-700:  #047857
--emerald-800:  #065F46
--emerald-900:  #064E3B

/* Amber — Warning */
--amber-50:     #FFFBEB
--amber-100:    #FEF3C7
--amber-200:    #FDE68A
--amber-300:    #FCD34D
--amber-400:    #FBBF24
--amber-500:    #F59E0B
--amber-600:    #D97706
--amber-700:    #B45309
--amber-800:    #92400E
--amber-900:    #78350F

/* Red — Error */
--red-50:       #FEF2F2
--red-100:      #FEE2E2
--red-200:      #FECACA
--red-300:      #FCA5A5
--red-400:      #F87171
--red-500:      #EF4444
--red-600:      #DC2626
--red-700:      #B91C1C
--red-800:      #991B1B
--red-900:      #7F1D1D

/* Slate — Neutral */
--slate-50:     #F8FAFC
--slate-100:    #F1F5F9
--slate-200:    #E2E8F0
--slate-300:    #CBD5E1
--slate-400:    #94A3B8
--slate-500:    #64748B
--slate-600:    #475569
--slate-700:    #334155
--slate-800:    #1E293B
--slate-900:    #0F172A
```

### Semantic Colors

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bg-primary` | #FFFFFF | #0F172A | Page background |
| `--bg-secondary` | #F8FAFC | #1E293B | Card/section background |
| `--bg-tertiary` | #F1F5F9 | #334155 | Input/hover backgrounds |
| `--text-primary` | #0F172A | #F8FAFC | Primary text |
| `--text-secondary` | #475569 | #94A3B8 | Secondary text |
| `--text-muted` | #94A3B8 | #64748B | Disabled/muted text |
| `--border` | #E2E8F0 | #334155 | Borders and dividers |
| `--accent` | #2563EB | #60A5FA | Interactive elements |
| `--success` | #059669 | #34D399 | Success states |
| `--warning` | #D97706 | #FBBF24 | Warning states |
| `--error` | #DC2626 | #F87171 | Error states |
| `--info` | #2563EB | #60A5FA | Informational |

---

## Typography

### Font Family

| Usage | Font Stack | Weight |
|-------|-----------|--------|
| **Headings** | `Inter, system-ui, sans-serif` | 600–700 |
| **Body** | `Inter, system-ui, sans-serif` | 400–500 |
| **Code** | `JetBrains Mono, Fira Code, monospace` | 400–500 |
| **UI Elements** | `Inter, system-ui, sans-serif` | 500 |

### Type Scale

```css
/* Headings */
--font-size-h1: 2.25rem   (36px)  — line-height: 2.5rem
--font-size-h2: 1.875rem  (30px)  — line-height: 2.25rem
--font-size-h3: 1.5rem    (24px)  — line-height: 2rem
--font-size-h4: 1.25rem   (20px)  — line-height: 1.75rem
--font-size-h5: 1.125rem  (18px)  — line-height: 1.75rem

/* Body */
--font-size-base:   0.875rem (14px) — line-height: 1.5rem
--font-size-lg:     1rem     (16px) — line-height: 1.5rem
--font-size-sm:     0.75rem  (12px) — line-height: 1.25rem
--font-size-xs:     0.625rem (10px) — line-height: 1rem

/* Code */
--font-size-code:   0.8125rem (13px) — line-height: 1.25rem
```

### Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| `--font-normal` | 400 | Body text, labels |
| `--font-medium` | 500 | Buttons, navigation |
| `--font-semibold` | 600 | Subheadings |
| `--font-bold` | 700 | Main headings |

---

## Spacing System

### Base Unit: 4px

```css
--space-0:   0px
--space-1:   4px
--space-2:   8px
--space-3:   12px
--space-4:   16px
--space-5:   20px
--space-6:   24px
--space-8:   32px
--space-10:  40px
--space-12:  48px
--space-16:  64px
--space-20:  80px
--space-24:  96px
```

### Layout Grid

| Breakpoint | Min Width | Columns | Gutter | Margin |
|------------|-----------|---------|--------|--------|
| Mobile | 0px | 4 | 16px | 16px |
| Tablet | 640px | 8 | 24px | 24px |
| Desktop | 1024px | 12 | 32px | 32px |
| Wide | 1280px | 12 | 40px | auto |

---

## Components

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: var(--accent);
  color: #FFFFFF;
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 500;
  transition: all 150ms ease;
}
.btn-primary:hover {
  background: var(--primary-700);
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}
.btn-primary:active {
  transform: scale(0.97);
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: 8px;
}

/* Ghost Button */
.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  padding: 8px 12px;
  border-radius: 8px;
}
.btn-ghost:hover {
  background: var(--bg-tertiary);
}

/* Danger Button */
.btn-danger {
  background: var(--error);
  color: #FFFFFF;
  padding: 8px 16px;
  border-radius: 8px;
}
```

### Inputs

```css
.input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: var(--font-size-base);
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}
.input::placeholder {
  color: var(--text-muted);
}
.input-error {
  border-color: var(--error);
}
.input-error:focus {
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15);
}
```

### Cards

```css
.card {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card-hover:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  border-color: var(--primary-200);
}
```

### Phase Indicator

```css
.phase-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: var(--font-size-sm);
  font-weight: 500;
}
.phase-pill--waiting {
  background: var(--bg-tertiary);
  color: var(--text-muted);
}
.phase-pill--active {
  background: rgba(37, 99, 235, 0.1);
  color: var(--accent);
  animation: pulse 2s infinite;
}
.phase-pill--complete {
  background: rgba(5, 150, 105, 0.1);
  color: var(--success);
}
.phase-pill--error {
  background: rgba(220, 38, 38, 0.1);
  color: var(--error);
}
```

### Metric Card (Dashboard)

```css
.metric-card {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.metric-card__label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.metric-card__value {
  font-size: var(--font-size-h2);
  font-weight: 700;
  color: var(--text-primary);
}
.metric-card__change {
  font-size: var(--font-size-sm);
  font-weight: 500;
}
.metric-card__change--positive {
  color: var(--success);
}
.metric-card__change--negative {
  color: var(--error);
}
```

### Chat Bubble

```css
.chat-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 16px;
  line-height: 1.5;
  font-size: var(--font-size-base);
}
.chat-bubble--user {
  align-self: flex-end;
  background: var(--accent);
  color: #FFFFFF;
  border-bottom-right-radius: 4px;
}
.chat-bubble--assistant {
  align-self: flex-start;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}
.chat-bubble--streaming {
  border-left: 3px solid var(--accent);
}
```

---

## Dark Mode

The design system uses CSS custom properties with a `.dark` class toggle:

```css
:root {
  --bg-primary: #FFFFFF;
  --text-primary: #0F172A;
  /* ... */
}
.dark {
  --bg-primary: #0F172A;
  --text-primary: #F8FAFC;
  /* ... */
}
```

Apply via:
- System preference: `prefers-color-scheme: dark`
- Manual toggle: User clicks moon/sun icon in header
- Persisted in `localStorage('theme')`

---

## Accessibility

| Requirement | Implementation |
|-------------|----------------|
| **Color contrast** | All text meets WCAG AA (4.5:1 ratio for body, 3:1 for large text) |
| **Focus indicators** | 3px ring using `box-shadow` with `outline: none` |
| **Keyboard navigation** | All interactive elements reachable via Tab/Space/Enter |
| **ARIA labels** | Icons use `aria-label`, interactive elements describe action |
| **Reduced motion** | Respects `prefers-reduced-motion` — disable animations |
| **Screen reader** | Phase progress announced via `aria-live="polite"` |

---

## Animation

### Timing

```css
--transition-fast:  100ms ease
--transition-base:  150ms ease
--transition-slow:  300ms ease
--transition-xslow: 500ms ease
```

### Keyframes

```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideInUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes skeleton {
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
}
```

### Usage Guidelines

- Use `fadeIn` for initial content loads (100–200ms)
- Use `slideInUp` for list items and cards (stagger by 50ms)
- Use `skeleton` for loading states (1.5s infinite)
- Use `pulse` for active phase indicators (2s infinite)
- Use `spin` for loading spinners (1s infinite linear)

---

## Shadows

```css
--shadow-sm:    0 1px 2px rgba(0,0,0,0.05)
--shadow-base:  0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)
--shadow-md:    0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.06)
--shadow-lg:    0 10px 15px rgba(0,0,0,0.1), 0 4px 6px rgba(0,0,0,0.05)
--shadow-xl:    0 20px 25px rgba(0,0,0,0.1), 0 8px 10px rgba(0,0,0,0.06)
```

---

## Icons

Use [Lucide Icons](https://lucide.dev/icons/) (MIT license) — provided via `lucide-react` package.

### Common Icons

| Component | Icon | Size |
|-----------|------|------|
| Send message | `Send` | 20px |
| Upload document | `Upload` | 20px |
| Settings | `Settings` | 20px |
| User | `User` | 20px |
| Shield | `Shield` | 20px |
| Search | `Search` | 20px |
| Check | `Check` | 16px |
| X | `X` | 16px |
| Alert triangle | `AlertTriangle` | 20px |
| Loader | `Loader2` (animated) | 20px |
| Copy | `Copy` | 16px |
| External link | `ExternalLink` | 14px |