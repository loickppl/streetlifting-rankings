# Streetlifting Platform — Design System

## 1. Design Vision

This application is a modern platform dedicated to competitive streetlifting data, rankings and competition results.

The visual identity must communicate: **Strength. Performance. Precision. Competition. Simplicity.**

The interface must feel modern and distinctive without becoming visually complex.
The product should feel like a professional international sports platform, not a generic SaaS dashboard.

The design must always prioritize:

1. Readability
2. Simplicity
3. Data clarity
4. Fast navigation
5. Visual consistency
6. Streetlifting identity

## 2. Core Design Direction

**Light First** — The primary interface must use a light visual theme.

Prefer: white, off-white, very light neutral grey, near-black typography, subtle borders, restrained use of accent colors.

Dark sections may occasionally be used intentionally to create contrast, but the overall experience must remain predominantly light. Avoid turning the application into a dark dashboard.

## 3. Visual Personality

The design should feel: athletic, clean, precise, premium, minimal, international, competitive, modern, fast.

It should NOT feel: corporate SaaS, generic admin dashboard, gaming, bodybuilding cliché, aggressive, futuristic / sci-fi, over-designed, artificially "AI-generated".

Streetlifting identity should emerge naturally through typography, movement, competition data, imagery and subtle visual references to the sport.

## 4. Simplicity First

UX must remain extremely intuitive. Users should immediately understand: where they are, what they are looking at, what can be clicked, how to search, how to filter, how to navigate.

Avoid unnecessary layers of interaction. Prefer direct interactions over: nested menus, unnecessary modals, hidden actions, excessive dropdowns, complicated navigation patterns.

If an interaction can be made simpler, prefer the simpler version.

## 5. Data First

Data is the main content of the application. Never sacrifice readability for decoration.

Important information and performance numbers should have strong visual hierarchy. Large numerical values may become visual elements themselves. For example:

```
#1    +72.5 KG    412.5 KG
```

Numbers, rankings and performances are part of the visual identity. Dense data interfaces should remain efficient and easy to scan.

## 6. Color Philosophy

The interface should be predominantly neutral.

| Role | Value |
|---|---|
| Primary background | `#FFFFFF` |
| Secondary background | `#F7F7F5` |
| Alternative subtle surface | `#F1F2F0` |
| Primary text | `#171717` |
| Secondary text | `#686868` |
| Subtle text | `#929292` |
| Borders | `#E6E6E3` |

These values are starting points, not immutable requirements.

**Accent color** — Use one primary accent color to establish the product identity. The accent should feel energetic and athletic without dominating the interface. Possible directions: electric blue, competition red, vivid orange, performance green.

The accent color should be used intentionally for: active states, important actions, selected filters, important statistics, links, records, significant competitive information.

Avoid introducing many unrelated colors. The majority of the interface should remain neutral.

## 7. Typography

Typography is a major part of the visual identity. Use a clean, modern sans-serif with excellent readability.

The typography should work particularly well for: names, rankings, numbers, weights, tables, statistics, competition information. Large numerical values may use stronger typography.

Avoid: futuristic fonts, stereotypical gym fonts, overly aggressive condensed fonts, decorative fonts that reduce readability.

Typography should communicate sport through confidence and hierarchy rather than clichés.

## 8. Spacing & Layout

Use whitespace intentionally. The interface should feel clean and breathable without wasting space.

Content-heavy areas may use higher information density. Editorial or visually important areas may use significantly more whitespace.

Hierarchy should primarily come from: spacing, typography, alignment, scale, subtle surface differences.

Do not automatically create containers around everything.

## 9. Cards

Avoid excessive use of cards. Do NOT wrap every section inside a rounded rectangle.

Prefer: whitespace, alignment, typography, separators, subtle background changes.

Cards should only be used when they represent a meaningful standalone object or improve comprehension. Avoid generic layouts composed entirely of `[ Card ] [ Card ] [ Card ] [ Card ]`.

## 10. Corners

Use restrained corner radii: small controls `4px`, buttons / inputs `6px`, larger containers `8px`.

Avoid excessive `12px`, `16px`, `20px` or `24px` rounded containers. Pill-shaped elements should only be used when their semantic purpose justifies them.

## 11. Shadows

Use shadows very sparingly. Prefer: borders, whitespace, surface contrast.

Shadows are appropriate for elements that physically appear above the interface: dropdowns, floating menus, overlays, modals. Do not add shadows to every component.

## 12. Tables & Dense Data

Tables and data-heavy components are important elements of the product. They should feel: clean, fast, precise, compact, highly readable.

Avoid excessive visual decoration inside tables. Do not automatically transform values into colored badges. Use typography, spacing and alignment to establish hierarchy.

Hover states should be subtle. Headers should remain easy to distinguish. Numbers should align consistently. Important performance data should be easy to scan vertically and horizontally.

## 13. Icons & Emojis

**Emojis** — Use very sparingly. The interface should NOT rely on emojis as its primary visual language.

Do not add emojis automatically to: titles, navigation, buttons, filters, table headers, empty states, notifications, section headings. Avoid the common AI-generated pattern of adding an emoji before every label or section title.

Emojis may occasionally be appropriate when they communicate something naturally and immediately — e.g. 🥇 🥈 🥉. Medals are universally understood and directly related to competition. Even then, use restraint.

Default rule: if an emoji is not clearly useful, do not use it.

**Icons** — Prefer a coherent icon system over emojis for interface actions. Icons should be: minimal, consistent, functional, visually lightweight.

Do not add icons merely to make the interface appear more designed. Not every button needs an icon. Not every label needs an icon. Not every statistic needs an illustration.

## 14. Streetlifting Visual Identity

Streetlifting should be present in the visual language without becoming cliché.

Potential visual elements: minimal athlete silhouettes, bar geometry, weight plates, movement trajectories, competition markings, subtle references to the four lifts, strong numerical typography.

Avoid generic gym imagery: flames, lightning everywhere, aggressive bodybuilding silhouettes, skulls, excessive chalk effects, fake metal textures.

The identity should feel like competitive sport, not gym merchandise.

## 15. Motion Identity

Animation should reinforce the identity of the product. Animations must be: subtle, smooth, purposeful, lightweight.

Animation should never interfere with navigation or data consumption. Avoid animations simply because they look impressive.

## 16. Signature Athlete Animation

A potential signature visual element is a minimalist athlete performing a streetlifting movement.

For example, a thin horizontal bar may naturally become part of the page composition. A minimal athlete silhouette could interact with it. During scrolling, the athlete could progressively perform a movement such as:

Dead hang → Pull → Transition → Muscle-up → Lockout

The animation should be tied smoothly to scroll progression. The visual style should resemble a sophisticated animated sports pictogram.

It should NOT feel: cartoonish, photorealistic, gimmicky, distracting.

This should be treated as a signature visual moment, not something repeated everywhere. Similar movement concepts could eventually be explored for Pull-Up, Muscle-Up, Dip, Squat. Do not use all movement animations simultaneously. Restraint makes the animation more memorable.

## 17. Microinteractions

Use subtle interaction feedback where it improves comprehension: row hover, active navigation transition, filter transitions, number changes, chart entrance, selection feedback, loading transitions.

Typical transitions should remain relatively fast: `120ms – 300ms`.

Avoid excessive: bouncing, scaling, spring effects, glowing, pulsing, movement without functional purpose. The interface should feel responsive, not animated for the sake of animation.

## 18. Responsive Design

Mobile must be considered a first-class experience. Do not simply shrink desktop layouts.

Complex data should adapt intelligently. Prioritize essential information on smaller screens and progressively expose secondary information. Touch targets must remain comfortable. Filters and navigation should remain easy to operate with one hand.

## 19. Accessibility

Maintain strong text contrast. Never communicate important information exclusively through color.

Interactive elements must have clear hover / focus / active / disabled states. Support keyboard navigation where relevant.

Animations must respect `prefers-reduced-motion`. Accessibility and readability always take priority over visual effects.

## 20. Anti-Generic-AI Design Rules

**This section is mandatory.** When designing or generating UI, NEVER automatically fall back to generic AI-generated dashboard patterns.

Avoid: excessive rounded cards, giant border radii, random gradients, purple/blue SaaS gradients, glassmorphism, unnecessary shadows, generic admin sidebars, colored badges everywhere, excessive icons, excessive emojis, excessive pill buttons, putting every statistic inside a card, generic stock illustrations, decorative charts without analytical value, unnecessary floating panels, identical layouts repeated on every page.

Do not assume that "modern" means: rounded cards + icons + gradients + shadows.

Before adding a visual element, ask: **does this improve readability, usability, hierarchy or streetlifting identity?** If not, remove it.

## 21. Component Consistency

Before creating a new UI pattern:

1. Search for an existing equivalent.
2. Reuse existing patterns whenever possible.
3. Extend the design language only when necessary.
4. Avoid creating slightly different versions of the same component.
5. Keep spacing, typography, interactions and visual hierarchy consistent.

New components should feel naturally related to existing ones.

## 22. Design Review

Before considering any UI implementation complete, review it against these questions:

- **Identity** — Could this interface belong to any generic SaaS product? If yes, improve its identity.
- **Readability** — Can the important information be understood within seconds?
- **Hierarchy** — Is it immediately obvious what matters most?
- **Simplicity** — Could anything be removed or simplified?
- **Consistency** — Does it follow the existing visual language?
- **Streetlifting** — Does the interface subtly communicate competitive streetlifting?
- **Restraint** — Is anything decorative without improving the experience? If yes, consider removing it.
- **Emojis** — Were emojis added where they are genuinely useful, or simply for decoration? If they are decorative, remove them.

## 23. Final Principle

The platform should not impress users because it contains many visual effects. It should impress users because it feels: **obvious, fast, precise, premium and unmistakably built for streetlifting.**

The interface should allow the sport, athletes, performances, rankings and competition data to provide the personality.

Design the platform around the sport — not around current UI trends.
