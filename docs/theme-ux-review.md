# Theme UX review and implementation brief

**Scope:** shared application themes, including Admin, menus, Collection, and playlist UI.
**User direction:** Midnight is approved. Improve Light, Parchment, Ocean, and Forest.
**Review basis:** current `assets/reflex.css` and shared theme selector. Source-based findings; rendered screenshots and measured contrast remain required before sign-off.

## Review comments — 20 November 2026

Source validation against the latest implementation supports the overall token-first direction. The following clarifications should be incorporated before development. No theme changes or measured visual/contrast audit were performed in this review.

- **High — treat persistence as new functionality, not existing behavior to preserve.** `UI.theme` is currently a plain Reflex state string initialized to `light`; `set_theme()` changes that state, with no explicit browser-storage persistence or startup restoration. Specify the persistence mechanism, default/fallback for unknown stored IDs, and initial theme application before requiring flash-free reloads. Verify reload, new tab, and direct route entry separately from navigation within the current session.
- **Medium — correct the outer-background finding.** CSS already sets body backgrounds for Parchment, Ocean, and Forest through `body:has(...)` rules. Midnight additionally covers `.radix-themes`. The remaining issue is inconsistent scope and duplicated values, rather than an absence of outer-background treatment for every light theme. Consolidate those existing rules when moving tokens to a common ancestor.
- **Medium — make Light's selector explicit.** `shell()` currently renders plain `app-shell` for Light, while the stylesheet also defines `.app-shell.theme-light`; that selector is not reached by the current renderer. Adopt one explicit theme attribute/class for all five IDs and ensure Light receives its revised tokens, including portaled components and the initial render.
- **Medium — preserve source identities in the latest listening charts.** The implementation now defines distinct Last.fm, Plex, and iTunes colors (`--collection-lastfm`, `--collection-plex`, `--collection-itunes`) as well as listening/composition roles. Include those source tokens in the specification and QA matrix. Keep source identity stable across theme changes and pair colors with labels; avoid collapsing the three sources into one generic listening accent.
- **Medium — Synapse's dark surface is already deliberate.** The current stylesheet explicitly documents the cross-theme dark treatment and scopes foreground/accent tokens inside the panel. The user has explicitly requested preserving the original dark teal tile, compact controls, and network illustration. The Admin brief now agrees. Treat this as an approved feature surface across all themes; do not recolor it into the surrounding theme palette. Keep its text, status badges, focus, and disabled controls in the contrast audit.
- **Medium — separate disabled readability from conformance claims.** The acceptance criterion should explicitly identify disabled controls as a usability target; inactive controls are exempt from the usual WCAG text/non-text contrast requirements. Likewise, assess chart marks that are essential to understanding data against relevant adjacent colors, rather than requiring every decorative chart mark to meet 3:1. Keep the existing stricter readability goal where practical.

### Follow-up review after Admin changes

- **High — include the Radix theme configuration in scope.** `rxconfig.py` fixes Radix to light appearance, brown accent, and sand gray. CSS tokens alone do not configure every primitive or portaled component. Define how the selected theme reaches Radix appearance/accent roles and its portal layer, while preserving Midnight and Synapse. Include `rxconfig.py`, the shared shell, and theme state in the implementation inventory; avoid relying on increasingly broad `!important` overrides.
- **Medium — preserve the approved Admin structure during theming.** Admin now uses horizontal separators and open tool/transfer sections, with a compact Activity strip and a right-aligned Library Operations chevron. Map decorative rules to the divider token and interactive focus to the focus token. Do not reintroduce generic bordered cards, alter the disclosure affordance, or change Synapse while improving the four light palettes.
- **Medium — broaden the actual QA targets.** Include native file inputs/upload dropzones, inline Activity status, disclosure chevrons, Full sync's tinted band, open sections, and the existing log/console surfaces. Check direct route entry and overlays that are already open during a theme switch. Fixed dark log/feature surfaces need their own foreground/background tokens rather than inheriting light-theme body text.

The proposed palette values remain candidates. “Ready for development” is appropriate for infrastructure work, but visual approval still depends on rendered comparisons, measured state-specific contrast, and a Midnight regression check. Retain the existing requirement to validate before sign-off.

## Assessment

Midnight has a coherent dark canvas, clear surfaces, warm highlights, and deliberate component overrides. Preserve its existing palette and visual character. Use its level of completeness as the quality benchmark; do not make the other themes copies of its dark treatment.

The four light themes mostly change a small set of variables while many components retain brown, cream, or dark teal constants. This makes the choices feel like background tints rather than complete themes. Light and Parchment also occupy very similar visual territory. The main issue is consistency across the whole interface, followed by stronger distinction between themes.

| Finding in current CSS | Required response |
| --- | --- |
| Theme variables live on `.app-shell`; Parchment/Ocean/Forest have body overrides, while Midnight also covers the Radix wrapper. Scope and duplicated values remain inconsistent | Apply the selected theme to the full page, including gutters and overscroll, without waiting for component-specific exceptions |
| Charts, metric accents, hover states, badges, and several input styles use literal colors | Replace UI constants with semantic theme tokens; keep status meaning consistent |
| Home hero and Synapse use contrasting dark surfaces; the original Synapse tile is explicitly approved | Preserve Synapse’s dark teal palette and artwork; define feature-surface tokens without changing its appearance. Evaluate the hero separately |
| Admin menu duplicates theme colors outside the shell | Supply the same theme tokens to portaled menus, dialogs, selects, and tooltips |
| Palette previews define colors separately from actual theme values | Generate previews from the real palette; selected preview must match the page |
| Midnight has extensive component treatment; other themes have fewer equivalent rules | Audit full component coverage for each light theme rather than adding more isolated overrides |

## Theme direction

These are proposed palette starting points, not verified accessible combinations. Measure actual foreground/background pairs, including interaction states, before adopting them.

| Role | Light — Gallery | Parchment — Archive | Ocean — Coastal | Forest — Botanical |
| --- | --- | --- | --- | --- |
| Canvas | `#F4F5F7` | `#EDE2CE` | `#E7F0F4` | `#EAF0E5` |
| Surface | `#FFFFFF` | `#FFF8E9` | `#FBFDFE` | `#FBFDF7` |
| Secondary surface | `#EAEDF1` | `#E4D5BA` | `#D6E6ED` | `#DCE7D4` |
| Main text | `#20252B` | `#35291E` | `#18313F` | `#263629` |
| Muted text | `#59616C` | `#655541` | `#4B6371` | `#53634F` |
| Accent | `#344E70` | `#79502B` | `#205D79` | `#365F3E` |
| Accent hover | `#263C58` | `#5D3A1D` | `#17465D` | `#26492E` |
| On accent | `#FFFFFF` | `#FFFFFF` | `#FFFFFF` | `#FFFFFF` |
| Decorative divider | `#D5DBE3` | `#CCB997` | `#BFD3DF` | `#C5D3BD` |

### Light

Make this the crisp neutral option: white surfaces, cool graphite text, restrained slate-blue actions, clean rules, and minimal shadow. Remove inherited beige/brown treatment from ordinary controls and metrics. Preserve the music collection's editorial typography. This should feel intentionally neutral, distinct from Parchment.

### Parchment

Commit to warm paper and sepia ink. Increase the distinction between canvas, panel, inset controls, and dividers. Use copper/brown accents sparingly. Avoid yellow body text, heavy faux-aged texture, and brown outlines around everything. Keep logs and dense tables on a quiet, readable surface.

### Ocean

Use deep marine blue as the action color, with pale blue-gray canvas and near-white panels. Reserve sea-glass teal for secondary data. Current warm brown chart/control remnants should become theme-aware. Avoid making every panel blue: color belongs in structure, selected states, and selected data series.

### Forest

Use deep evergreen actions, pale botanical canvas, and warm white surfaces. Add restrained olive secondary accents where needed; keep body text dark and neutral. Distinguish ordinary green theme accents from success/running status through icons, labels, and dedicated status styling. Forest must remain understandable without color recognition.

## Token and component specification

Extend the current token system rather than inventing a parallel stylesheet. Retain existing token names where practical and add missing roles:

- Canvas, surface, raised surface, inset surface, and hover surface.
- Main/muted text, accent, accent hover, on-accent, selected background, selected foreground.
- Decorative divider separately from interactive control boundary: a subtle divider is not automatically sufficient for an input outline.
- Focus ring, overlay scrim, input background/border, placeholder, disabled text/background.
- Success, warning, error, and information foreground/background pairs.
- Chart listening/composition colors plus distinct Last.fm, Plex, and iTunes source colors; ordered series palette, grid, axis text, tooltip surface/text.
- Feature surface/foreground/accent for the home hero and the approved dark Synapse tile. Preserve Synapse’s resolved appearance.

Use a consistent theme attribute/class on an ancestor that also covers the body and portal layer. Set `color-scheme: light` for the four light themes and preserve Midnight's dark setting. Implement browser persistence and startup restoration explicitly; these do not currently exist. Define the default and fallback for invalid stored values, and apply the saved theme early enough to avoid an unrelated canvas flash. Preserve the five existing theme IDs and apply an explicit selector for Light as well as the other four themes.

Solid primary buttons must use on-accent text rather than inheriting body text. Outline buttons need visible boundaries. Disabled controls must remain legible without resembling enabled actions. Every interactive component needs default, hover, pressed, selected, focus, disabled, and error treatment where applicable.

For charts, distinguish theme accents from semantic series identities. Keep listening/composition meanings stable across themes; use appropriate tonal variants. Do not recolor arbitrary categories on every render. Missing data, unknown metadata, and errors must not share indistinguishable treatments.

Keep layout, typography, spacing, radii, and animation behavior stable when switching themes. Theme choice changes the visual palette, not the information hierarchy.

## Implementation priorities

1. Fix full-page theme scope and portal inheritance. Preserve Midnight's resolved appearance.
2. Centralize token definitions and replace hard-coded shared control/chart colors. Consolidate superseded CSS rather than appending another chain of overrides.
3. Apply the four proposed light-theme directions, validate palette pairs, and update selector previews from the same values.
4. Audit remaining feature surfaces, tables, logs, forms, badges, errors, empty states, and tooltips.
5. Verify theme persistence, initial load, route changes, and open overlays. Check Midnight after every shared-token change.

## Acceptance and visual QA

- Midnight's approved character remains intact; shared refactoring introduces no contrast or layout regression.
- Light and Parchment are visibly distinct; Ocean and Forest extend beyond a tinted canvas into controls, selected states, charts, and overlays.
- Page background, gutters, menus, dialogs, select popovers, and tooltips use the active theme consistently.
- Body text and normal control labels meet 4.5:1 contrast; large text meets 3:1. Essential boundaries, focus indicators, and chart marks meet 3:1 against adjacent colors. Decorative dividers need not be treated as control boundaries.
- Keyboard focus is clear on canvas, panel, and feature surfaces. Status is conveyed through text/icons as well as color.
- Palette previews reflect actual tokens. Theme IDs, selection persistence, and Appearance navigation remain compatible.
- Capture matching desktop/mobile views for all five themes: Admin with open menu, job details/log dialog, Collection with charts/ranked rows, and the playlist page with form controls and results.
- Include error, disabled, loading, empty, selected, and hover/focus examples. Check reduced transparency, increased contrast preference, and 200% zoom.

**Ready for development:** implement theme infrastructure and the four light-theme improvements alongside the Admin/Collection work. The proposed colors are design candidates; final acceptance requires rendered comparison and contrast measurements, not source inspection alone.
