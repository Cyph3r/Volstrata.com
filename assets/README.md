# Assets

Brand assets used by this repository's documentation.

| File | What it is |
|---|---|
| [`volstrata-logo.svg`](volstrata-logo.svg) | The VolStrata wordmark in gold (`#e0b23a`), 631 x 76, vector paths with no embedded fonts. Used in the top-level [`README.md`](../README.md) at `height="40"`. |

## Why the gold variant

GitHub renders README images against either a white or a near-black page depending on the
reader's theme, and it does not support a theme-swapped image without duplicating the
markup. Gold has enough contrast against both, so one file covers both themes and the
logo never disappears into the background.

## Editing

The logo is a byte-for-byte copy of the upstream wordmark with a single copyright comment
inserted at the top. Do not redraw it, recolour it, minify it or run it through an SVG
optimiser — replace it wholesale from upstream if it ever changes. `.editorconfig` exempts
this directory's SVGs from the final-newline rule for the same reason.

Use of the name and logo is covered by [`NOTICE`](../NOTICE), not by the MIT licence that
covers the example code. See https://volstrata.com.

---

Copyright 2026 Volstrata.com - https://volstrata.com
