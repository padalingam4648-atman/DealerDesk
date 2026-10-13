# Frontend Redesign Notes — VIKMO DealerDesk

This document analyzes the reference design inspiration (Stodio agency layout) and details how its layout composition, typography hierarchy, component language, and palette were translated into the VIKMO DealerDesk B2B trade portal while respecting all hard project constraints (Light theme only, anti-AI look, system fonts, zero external dependencies).

---

## 1. Reference Design Analysis

### Layout Structure
- **Viewport Canvas & Framing:** The entire page canvas is anchored within an architectural outer perimeter (deep crimson/burgundy border `#7F1D1D`), framing a large, curved inner canvas (radius ~24px) with crisp 1px borders.
- **Hero Area:** Asymmetric, editorial split layout:
  - Top header with brand mark on the left (geometric multi-dot star icon + wordmark), clean horizontal nav in the center with a micro pill badge counter (`25`), and a pill CTA button on the right.
  - Left hero column features an eyebrow badge with a red square indicator (`■`), followed by a massive, bold display headline.
  - Right hero column features a concise descriptive subhead and a dual-button call to action: primary vibrant crimson pill (`↗`) and secondary crisp white pill.
  - Bottom-left hero features horizontal feature pillars (`+ Define`, `+ Design`, `+ Development`).
- **Partner / Social Proof Strip:** Clean horizontal strip immediately below the hero, featuring an icon mark + bold uppercase network counter on the left, and a horizontal row of clean monochrome partner logos on the right.
- **Editorial Statement & Feature Cards:**
  - Section eyebrow (`■ WHO WE ARE` / `■ WHAT DEALERDESK DOES`).
  - Large two-tone headline: primary dark solid charcoal transitioning into muted slate gray for the secondary clause.
  - Right-aligned text link with arrow (`→ ABOUT THE STUDIO` / `→ ABOUT THE PLATFORM`).
  - 4-column card grid showcasing core capabilities with clean rounded corners.
- **"By the Numbers" Metric Ledger:**
  - Section eyebrow (`■ BY THE NUMBERS`).
  - 4-column metric layout divided by subtle horizontal dotted lines (`1px dotted #D1D5DB`), featuring oversized bold tabular numerals, title, and descriptive microcopy.
- **Services / Architecture Section:**
  - Section eyebrow (`■ HOW IT IS BUILT`).
  - Contrasting section layout detailing the engineering stack and operational guarantees.
- **Footer:** Restrained single-line footer with clean links and system metadata.

### Grid and Spacing Rhythm
- **8px Base Spacing Grid:** Strict tokenized multiples:
  - `4px` (`--space-1`) — micro gaps, badge padding.
  - `8px` (`--space-2`) — button inline gaps, item padding.
  - `12px` (`--space-3`) — table cell padding, form gaps.
  - `16px` (`--space-4`) — card padding, toolbar gaps.
  - `24px` (`--space-6`) — section internal spacing.
  - `32px` (`--space-8`) — grid gaps, container margins.
  - `48px` (`--space-12`) — major section padding.
  - `64px` (`--space-16`) — hero section vertical rhythm.
- **Responsive Breakpoints:** 1280px standard desktop grid gracefully collapses to single-column stacking at 960px and 390px mobile viewports.

### Colour Palette (Sampled Hex Values)
- **Primary Brand Crimson:** `#991B1B` (deep dark crimson), `#B91C1C` (rich crimson), `#DC2626` (vibrant tomato red indicator & CTA).
- **Dark Text & Accents:** `#0F172A` (deep ink black), `#1E293B` (charcoal headline).
- **Secondary / Two-Tone Muted Text:** `#64748B` (slate gray), `#94A3B8` (subtle muted gray for two-tone headline).
- **Surfaces & Backgrounds (Light Theme):**
  - `--bg-page`: `#F8F9FA` (calm porcelain page backdrop).
  - `--bg-surface`: `#FFFFFF` (crisp white card surface).
  - `--bg-surface-subtle`: `#F1F5F9` (table headers, pill backgrounds).
  - `--bg-surface-hover`: `#F8FAFC` (row and button hover states).
- **Hairline Borders & Hairlines:**
  - `--border-color`: `#E2E8F0` (clean 1px solid border).
  - `--border-subtle`: `#F1F5F9` (inner table divider).
  - `--border-dotted`: `#CBD5E1` (metric strip dotted divider).
- **Accent Tints (Selected & Active States):**
  - `--accent-subtle`: `#FEF2F2` (soft red/rose background tint).
  - `--accent-border`: `#FEE2E2` (active pill/link border).

### Typography Feel
- **Font Stack:** Bundled system font stack without runtime CDN or Google Fonts requests (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif`).
- **Monospace Stack:** `ui-monospace, "SF Mono", "Cascadia Code", "Segoe UI Mono", Menlo, Consolas, monospace`.
- **Weights:** 400 (regular body), 500 (medium labels/table data), 600 (semi-bold headers and badges), 700 (bold display hero and metrics).
- **Type Scale:** 11px (micro badges), 12px (`--font-size-xs`), 14px (`--font-size-sm`), 16px (`--font-size-md`), 20px (`--font-size-lg`), 28px (`--font-size-xl`), 36px-40px (`--font-size-hero`).
- **Letter Spacing:** Tight `-0.025em` for display headlines; wide `0.06em` tracked uppercase for section eyebrows and micro tags.

### Component Styles
- **Eyebrow Badges:** Small vibrant red square indicator (`■` ~6px) followed by tracked uppercase text.
- **Buttons:**
  - Hero CTAs: Crisp pill buttons (`border-radius: 9999px`) with diagonal arrow indicator (`↗`).
  - Portal buttons: Precision 32-34px height with 4px radius, 1px border, high-contrast hover.
- **Dense Ledger Tables:**
  - 40px row height, sticky header with uppercase tracked labels, tabular numerals, right-aligned currency (`Rs. 1,459.50`), monospace SKU chips.
  - Zero layout shift with matching skeleton loading rows.
- **Real Product-UI Crop:**
  - Replaces stock photography with a live catalogue table crop framed in a browser window container with title bar and "Live API sample" badge.
- **Badges & Pills:**
  - 11px font size, 1px border, subtle tint background with semantic status colors (in-stock, low-stock, out-of-stock, draft, confirmed).

### Overall Mood
Architectural, confident, institutional, and calm. Adheres to strict anti-AI guidelines by eschewing neon glows, glassmorphism, emoji, and purple gradients in favor of razor-sharp typography, authentic domain microcopy, and ledger-like data density.

---

## 2. Adaptation to Hard Constraints & Rule Precedence

| Feature | Reference Design | DealerDesk Implementation | Reason for Adaptation |
|---|---|---|---|
| **Theme** | Dark hero + dark services section | Clean, calm Light Theme throughout | Hard Constraint: "Light theme only. Professional, calm... If reference conflicts, rules win." |
| **Color Scheme** | Crimson framing + dark slate + white cards | Deep crimson (`#991B1B` / `#B91C1C`) accents + white cards + slate typography | Preserves the reference's crimson brand identity while maintaining full WCAG AA contrast on light backgrounds. |
| **Hero Image** | Moody portrait photography | Live catalogue window crop (`GET /api/products/`) | Constraint: "a real product-UI crop (live catalogue rows inside a window frame) instead of stock art." |
| **Fonts** | Custom agency web font | Clean system sans-serif + monospace stack | Constraint: "No external requests at runtime: no CDN, no Google Fonts." |
| **Animations** | Agency-style hover micro-animations | Restrained transitions (120-160ms), <= 200ms hero motion, disabled under `prefers-reduced-motion` | Constraint: Anti-AI rules and strict accessibility motion compliance. |
