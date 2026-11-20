# MusicMind UX guidelines

These guidelines apply to user-facing interface changes throughout MusicMind. Read them alongside the relevant page brief and the current implementation. They capture the product direction and the user's feedback; a specific later user instruction takes precedence.

## Design direction

- Aim for a warm, quiet editorial feel, like record-sleeve notes: clear hierarchy, ink and parchment tones, restrained accents, fine rules, and generous but deliberate spacing.
- Use the existing theme tokens and typography. Page titles use the established serif; controls and supporting text use the application sans serif. Avoid adding font dependencies or decorative elements without a purpose.
- Use one clear page heading and a concise introduction. Put the main action and useful information ahead of secondary tools. Reveal specialist controls progressively without hiding primary actions.
- Keep content centered and readable, approximately 1200px wide, with desktop and mobile gutters. Body text should normally be 16px; captions should remain readable and no smaller than 13px. Use tabular numerals for counts.

## Layout and visual continuity

- Preserve distinctive, liked components when reorganizing a page. In particular, retain Synapse's dark tile, network illustration, and prominent counters. Its artwork is decorative, still at rest, and respects reduced motion.
- Avoid unnecessary boxes and repeated horizontal rules. Check neighboring components for inherited borders before adding a divider. Do not place multiple lines between the same sections. Keep spacing proportional; in particular, avoid an oversized gap above Synapse.
- Keep Scan Plex folders and Refresh an album visually consistent, aligned and readable without awkward individual background blocks. Keep the Library tools section on the page background. Do not add a divider between those controls and Synapse unless requested.
- When a section intentionally changes background, extend that background to both viewport edges while keeping its content aligned with the main column. Data transfers uses this treatment. Verify the result in every theme: Midnight must not show mismatched panel-colored blocks inside the band.
- Place contextual instructions where they are needed. The Apple Music/iTunes export instructions belong in the XML file drop area. Do not bury essential file-selection guidance in a separate disclosure.
- Reuse existing component styles where they fit. Scope changes to the intended section and reconcile conflicting or duplicate CSS rules instead of accumulating overrides. Preserve existing user customizations and unrelated work.

## Interaction and content

- Use direct labels that describe the action and its consequences. Navigation must navigate, and disclosure triggers must not execute jobs. Provide useful descriptions near the relevant controls.
- Make running work visible without forcing a modal. Prevent duplicate submissions, show pending states and meaningful errors near the originating action, and offer details separately.
- Show only states and results supported by real data. Distinguish loading, running, success, failure, stopped, unavailable and unknown where the underlying contract supports them. Never invent progress, estimates, history, counts or a successful result.
- Preserve backend behavior during presentation work. Describe data sources, write direction and existing-data handling accurately. For Admin, Full sync includes a Plex scan and wait; ratings remain Plex-first; iTunes aggregate plays must not be assigned invented dates.
- A preview must be distinguishable from applying changes. If it is only a log, say so; do not imply an atomic or structured diff. Invalidate a preview when its inputs change.

## Accessibility, themes and responsive behavior

- Support keyboard navigation, visible focus, meaningful labels, semantic headings and native or established accessible primitives. Do not nest interactive controls. Use text as well as color to convey state.
- Keep interactive targets at least 44px where practical. Wrap actions and content on narrow screens, preserve readable text, and avoid page-level horizontal scrolling. Respect reduced-motion preferences.
- Check Light, Parchment, Midnight, Ocean and Forest when changing shared styles. Use theme tokens and verify contrast, including nested panels, dropdown portals and focus indicators. Do not assume a light-theme background rule works in Midnight.
- Inspect desktop and mobile layouts, including long labels and short viewports. For significant layout changes, check 320, 390, 768, 1024 and 1440px and 200% zoom when tooling permits.

## Verification and handoff

- Review the current page and relevant CSS before changing it; distinguish observed behavior from assumptions. Check adjacent sections and existing overrides for unintended effects.
- Use controlled fixtures or mocks for operation states and errors. Do not run maintenance jobs, imports or rating writes merely to validate presentation.
- Check the rendered result in a browser when available, including keyboard operation, theme changes and responsive widths. Capture screenshots when requested. If a browser or check is unavailable, say exactly what remains unverified; do not describe a source inspection as a visual check.
- Keep page-specific requirements and unresolved backend contracts in their respective briefs: [Admin](admin-ux-redesign.md), [Collection](stats-ux-redesign.md), and [theme review](theme-ux-review.md). Reconcile older briefs with current backend behavior before implementing them.
