"""Shared frontend design guidelines injected into agent prompts.

This is the orchestrator's "design memory" — a single, versioned source of
truth for what a *premium* user-facing UI looks like. The CoderAgent injects it
when building anything user-facing, and the DesignerAgent uses it to specify a
design language. Update this file to raise the design bar across every project
the orchestrator generates.

Distilled from modern design-system practice (Tailwind + shadcn/ui design
tokens, Mobbin UI pattern libraries, Wix Studio layout systems) and current
high-craft landing-page conventions (Stripe / Linear / Vercel / Apple, Awwwards
winners): token-driven styling, restrained palettes with strong contrast,
expressive typography on generous whitespace, real imagery, and tasteful motion.
"""
from __future__ import annotations

FRONTEND_DESIGN_GUIDELINES = """\
## Frontend design standard (MANDATORY for any user-facing product)

If the product has ANY user-facing surface, you MUST ship a polished, modern
web UI — never a backend/API-only deliverable. The UI is the product's first
impression; it should look like it belongs on Awwwards or Mobbin, or like it
was built in Wix Studio — NOT like a basic student template. Aim for the visual
quality of Stripe, Linear, Vercel, or Apple.

SCOPE — BUILD A COMPLETE, FUNCTIONAL FRONTEND (not a single hero or landing).
Ship a full, working multi-section website for the product, with REAL
interactivity — the kind a user could actually click around in:
- Multiple sections tailored to what the software does. For a typical product:
  a hero, a features/how-it-works section, the product's core UI or a showcase
  (e.g. a dashboard mock, a product/work grid, pricing), social proof
  (testimonials/stats/logos), an FAQ or journal, a contact/sign-up section, and
  a real footer. Adapt the section set to the PRD — a SaaS app, a store, a
  portfolio and a booking tool each need different sections.
- WORKING NAVIGATION: a sticky nav whose links smooth-scroll to sections and
  highlight the active section; a functioning mobile hamburger → slide-in menu.
- REAL INTERACTIVITY (vanilla JS or React state): forms that VALIDATE and show
  success/error feedback (contact, sign-up, search); tabs/filters that actually
  filter content; toggles, modals, accordions, a cart, count-up stats — whatever
  the product implies. Handle loading/empty/error states. No dead buttons.
- Seed believable demo data (products, posts, projects, plans) so every section
  is populated and the interactions have something to act on.
A lone hero section, or static sections with no working behavior, does NOT meet
this bar. The output should feel like a finished, usable front end.

Follow these principles:

1. DESIGN TOKENS FIRST. Define a small token system as CSS custom properties
   (or a Tailwind theme) and reuse it everywhere — never hardcode ad-hoc values:
   - color: 1 neutral base (light *or* a dark-dominant palette) + 1–2 saturated
     accent colors used sparingly for CTAs/highlights. High contrast. Cohesive,
     never a rainbow.
   - spacing: a consistent 4/8px rhythm scale.
   - radius, shadow, and a type scale — all as tokens.

2. TYPOGRAPHY. Use at most TWO font families (load from Google Fonts): one
   expressive display face (a characterful serif or distinctive sans) for
   headings + one clean, legible sans for body. Establish clear hierarchy:
   large `clamp()`-scaled headlines, comfortable line-height, and small,
   letter-spaced uppercase eyebrows/labels. Let typography carry the design.

3. GENEROUS WHITESPACE & LAYOUT. Center content in a max-width container
   (~1100–1200px). Use airy section padding, a clear grid, strong visual
   hierarchy, and ONE prominent call-to-action per section. Reduce clutter so
   the page is effortless to scan.

4. REAL CONTENT, NOT MOCKUPS. Use real imagery (e.g. Unsplash
   `https://images.unsplash.com/...` URLs) with a graceful fallback (a tasteful
   gradient/emoji tile) via `onerror`, so it never looks broken. Use a crisp
   inline SVG or emoji icon set. Write believable copy, not "lorem ipsum".

5. COMPONENT POLISH. Cards with hairline borders and soft shadows; consistent
   rounded radii; clear primary vs. ghost buttons; visible :hover and :focus
   states (keyboard-accessible focus rings). Inputs styled to match the system.

6. TASTEFUL MOTION. Subtle scroll-reveal fade-ins, smooth hover micro-
   interactions, and 200–500ms transitions. Optionally light parallax or a
   count-up stat. Keep it elegant — and respect `prefers-reduced-motion`.

7. A COMPLETE PAGE. For a landing/storefront, include the expected sections:
   sticky nav, a hero (headline + subcopy + CTA + light social proof), a
   features/value strip, the core content (products/menu/feature grid),
   supporting sections (how-it-works, testimonials, gallery), a closing CTA, and
   a real footer.

8. RESPONSIVE & ACCESSIBLE. Mobile-first; layouts reflow cleanly. Semantic HTML,
   `alt` text, form labels, and AA color contrast.

9. WIRE IT TO THE BACKEND. The UI must actually call the project's real API
   endpoints (fetch products, submit forms, place orders) and handle loading,
   empty, and error states — not a dead static mockup.

10. RUNNABLE & SELF-CONTAINED. Strongly prefer a SINGLE `index.html` with inline
    CSS/JS that runs by just opening it (no build step), served from the app's
    root route. Do NOT emit bundler-only React (`import`/`export`) unless you
    also provide a working build config — an un-runnable scaffold is a failure.

11. MOTION & DEPTH (modern feel). Add tasteful motion: scroll-reveal fade/translate
    on sections, a hero entrance animation, hover lifts on cards, a nav that
    frosts on scroll, and optionally a marquee, count-up stats, or subtle
    parallax. Use depth via glassmorphism (translucent blurred surfaces over
    gradients/imagery) and soft shadows. ALWAYS guard with
    `@media (prefers-reduced-motion: reduce)`.

12. LAYOUT SYSTEMS. Reach for modern structures: a bento grid (mixed-size cells
    for instant hierarchy), an asymmetric split hero, glassmorphism pricing/
    feature cards, a gradient-mesh or gradient backdrop. Avoid flat, evenly-sized
    boxes in a single boring row.

QUALITY BAR — this is non-negotiable. The output must look like a real, designed
product, comparable to a hand-built premium page: on the order of HUNDREDS of
lines of CSS, multiple distinct sections, a cohesive token system, real imagery,
and motion. A ~10-line stylesheet, a dark box with default fonts, or placeholder
content like "Item 1 / Item 2" is a FAILURE — never ship that. A polished
single-page frontend is naturally long; that is expected — never truncate the UI.

ANTI-PATTERNS to avoid: tiny/empty CSS; unstyled default browser look; one
cramped column; lorem ipsum or "Roast 1/Roast 2" placeholders; broken images;
React that needs a build step you didn't provide; ignoring the brand's vibe.

CONTENT MUST FIT THE REQUESTED PRODUCT — this is critical. The component library
and any example snippets below are STRUCTURE ONLY: reusable scaffolding to lift
and then refill. Every section, heading, feature, label, button, and demo data
item MUST be derived from THIS project's PRD and brief — the product's real name,
its actual features, its domain language, and copy that fits what it does. A
password manager, a coffee store, a clinic booking app and a SaaS dashboard must
each read completely differently. NEVER ship the library's example names, brands,
or copy (e.g. "Velorah", "Rouxbean", "Plan Pro", lorem ipsum) — those are
placeholders to replace. The structure/motion are reusable; the words and content
are bespoke to the user's request every time.

Assemble the page from the COMPONENT LIBRARY (and the premium/functional patterns)
below — lift each pattern's structure, then restyle it to the product's brand
(colors, fonts) AND refill it with the product's own content. The library is your
shortcut to the quality bar; the content is yours to write from the PRD."""
