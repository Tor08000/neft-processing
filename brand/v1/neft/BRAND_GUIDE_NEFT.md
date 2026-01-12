# NEFT — Brand Guidelines v1.0

**Brand:** NEFT  
**Domain:** FinTech / Processing / Enterprise platform  
**Mood:** cold confidence · control · predictability  
**Do:** infrastructure-grade UI · strict states · readable data  
**Don’t:** decorative gradients · noisy backgrounds · “startup fun” tone

---

## 1. Brand idea

NEFT is **infrastructure**, not “a friendly service”.
Everything is built around:
- invariants
- states
- auditability
- operational clarity

Tone: short, factual, calm.

Examples:
- ✅ “Invoice generated. Status: ISSUED.”
- ✅ “Settlement completed. SLA: OK.”
- ❌ “Great news! We are happy to announce…”

---

## 2. Color system (canonical)

### 2.1 Surfaces
- **Core Dark:** `#0B1F2A`
- **Surface:** `#111827`
- **Card:** `#1F2937`
- **Border:** `#2C3E50`

### 2.2 Text
- **Text / Primary:** `#E5E7EB`
- **Text / Secondary:** `#9CA3AF`
- **Text / Muted:** `#6B7280`
- **Text / Inverse (on light):** `#0B1F2A`

### 2.3 Accents & states
- **Primary Accent:** `#15A1C7`
- **Info:** `#3B82F6`
- **Success:** `#0EE8A8`
- **Warning:** `#FFB020`
- **Error:** `#E5484D`

Rules:
- Accent is used for **actions, links, active states, key highlights** only.
- Do not use multiple accents in the same small block.
- Keep charts calm: one primary + state colors.

---

## 3. Typography

### 3.1 Primary font (UI/Web/App)
**Inter**
- Regular: body text
- Medium: table labels, forms, metadata
- SemiBold: headings
- Bold: KPI, totals, money values

Fallback:
`system-ui, -apple-system, Segoe UI, Roboto, Arial`

### 3.2 Sizes (recommended)
- H1: 28–32 / 1.2
- H2: 20–24 / 1.25
- H3: 16–18 / 1.3
- Body: 14–15 / 1.5
- Caption: 12–13 / 1.4
- Table: 13–14 / 1.4 (monospace for ids optional)

---

## 4. Logo usage

### 4.1 Formats
- SVG (primary)
- PNG (light/dark variants)
- Monochrome (white/black)

### 4.2 Safe area
Minimum safe area: **0.5× logo height** on all sides.

### 4.3 Minimum size
- Web: min 24px height
- Print: min 15mm height

### 4.4 Forbidden
- stretching
- shadows/3D
- gradients inside logo
- placing on noisy photo backgrounds

---

## 5. UI principles (dashboard)

### 5.1 Layout
- grid-based, avoid chaos
- data density > decoration
- consistent spacing: 4/8/12/16/24

### 5.2 Cards
- background: Card
- border: 1px Border (subtle)
- radius: 10–12px
- shadows: minimal

### 5.3 Tables
- dense tables
- subtle hover
- readable columns; money values aligned right
- ids can be monospace

### 5.4 Controls
- Buttons: solid primary or outline
- Inputs: clear focus ring with Primary Accent
- Links: Primary Accent, underlined on hover

---

## 6. Status mapping

Canonical statuses (example):
- CREATED → `#6B7280`
- IN_PROGRESS → `#3B82F6`
- ACCEPTED/OK → `#0EE8A8`
- WARNING → `#FFB020`
- ERROR/BREACH → `#E5484D`

---

## 7. Icons

- style: outline/mono
- consistent stroke
- minimal detail

Recommended: Lucide/Heroicons (outline)

---

## 8. Email signature (NEFT)

Structure:
- logo (96×24)
- name (semi-bold)
- role/company
- phone / site / email
- confidentiality line

No heavy banners, no marketing blocks.

---

## 9. Assets structure

```
/brand/v1/neft/
├─ BRAND_GUIDE_NEFT.md
├─ colors/
│  ├─ tokens.css
│  └─ palette-neft.svg
├─ logo/
├─ fonts/
├─ ui/
├─ favicon/
└─ email/
```

---

## 10. Quick “DoD” (brand compliance)

UI is compliant if:
- uses canonical colors
- typography uses Inter + weights
- cards/tables/forms follow radius/border rules
- status colors map is consistent everywhere
- tone is short and factual

---

## 11. How to use (implementation)

1. Import `brand/v1/neft/colors/tokens.css` into the app root styles (or via `brand.css`).
2. Add `class="neft-app"` to the app shell/root wrapper.
3. Use UI classes:
   - Cards: `neft-card`
   - Tables: `neft-table`
   - Buttons: `neft-btn` + `neft-btn-primary|neft-btn-outline`
   - Inputs: `neft-input`
   - Status: `neft-chip` + `neft-chip-ok|info|warn|err|muted`
4. Apply theme early in the app with `applyTheme(getInitialTheme())` and provide a toggle.

---

## 12. Smoke check (required)

- Run admin and client frontends.
- Open dashboard, analytics, and orders/transactions pages.
- Verify:
  - Light theme is default.
  - Theme switch toggles dark/light and persists in `localStorage`.
  - Cards/tables/buttons/inputs use NEFT styles.
  - Statuses appear as chips with canonical colors.
