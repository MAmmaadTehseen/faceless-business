# Plainsight Media mark

The chosen mark is **01 — open eye**: two quadratic arcs and a circular pupil.
It communicates “plain sight” without a letter tile. The continuous silhouette
stays recognizable at 16px, while the pupil stays separate from the rim at 48px.
The open horizon lens (02) loses its distinct side gaps first at 16px; the lens P
(03) keeps its stem but reads primarily as a letter rather than sight.

`concepts/contact-sheet.png` compares all three at actual 16/32/48/192px sizes
on white and warm dark backgrounds. Matching individual PNGs are included.
`mark.svg` is the single-colour transparent master. `app-icon.svg` places the
paper-coloured mark on solid warm charcoal so it survives white, grey and dark
browser surfaces. Its geometry fits within the maskable central safe circle.
`favicon.svg` uses charcoal on transparent in light mode and paper in dark mode.
The masthead inherits the reader's foreground colour; shared and article OG
images show the same mark in paper on charcoal.

Regenerate from the repository root:

```sh
.venv/bin/python scripts/icons.py hub
```

Requires Pillow, Node and the installed hub dependencies (Sharp). No network,
fonts or credentials are used. With no arguments the script only writes hub
assets; legacy dashboard generation requires an explicit dashboard/all argument.
The generated ICO contains 16/32/48px frames; 48/96/192px PNG URLs are stable,
advertised in metadata and crawlable under robots.txt. Icon responses use a
30-day public cache; stable names deliberately do not use immutable caching.

The home title is “Plainsight Media: Work, Power and Space, Explained” (48
characters). Its description is 139 characters. WebSite JSON-LD provides the
full and alternate site names; Organization references the 512px logo.
These are signals for Google, not a guarantee of how or when results change.
Google documentation: [favicons](https://developers.google.com/search/docs/appearance/favicon-in-search)
and [site names](https://developers.google.com/search/docs/appearance/site-names).
