# Faceless dashboard · design system

A calm operating desk. Each screen answers one question, then lets the owner investigate.

**Layout.** Use a 12-column grid, maximum content width 1280px, 24px gutters and page padding of 32px desktop / 16px mobile. Spacing is 4/8/12/16/24/32/48px. Align section edges; separate sections with space rather than containers.

**Typography.** Keep the existing system sans family. Use regular and semibold only (400/600). Hero numbers are 32/40 semibold, one per page; h1 22px, h2 16px, body 14px, caption 12px. Section labels may be muted uppercase 11px with .08em tracking; other text never falls below 12px. All numbers use tabular figures.

**Colour.** Retain the committed near-black canvas and red/blue/cyan/orange/grey tokens. Colour conveys active selection, the primary action, one highlighted chart series, or status. Other content is greyscale. No coloured borders, card gradients or decorative glows. Only the selected chart series may glow. Channel identity is a 6px dot or 3px stripe, never a coloured surface.

**Surfaces.** Two elevations: canvas and surface, with the raised surface token reserved for hover/controls. Cards have no default border or shadow, radius 10px. Where grouping is ambiguous use a 1px white 8% hairline. Hover raises one surface step without shadows.

**Density.** Header offers Comfortable / Compact, persisted in localStorage. Rows are 44/36px minimum and card padding is 20/12px. Touch controls remain at least 44px in both modes.

**Hierarchy.** One hero state/number and an honest seven-day comparison where the source supports one; never fabricate a delta. At most four supporting stats. Secondary IDs, timestamps, platform IDs, breakdowns and quota calculations belong in Details or a drawer. Tables have at most six columns. Mobile rows reduce to title and status plus the key number; Details retains the rest.

**Components.** Status is text with a 6px dot: live, scheduled, queued, failed, needs review. Other labels are plain muted text. One primary action per screen; secondary actions are ghost buttons, destructive actions ghost red with confirmation. Tabs are underlined. Filters share one right-aligned toolbar and apply on change. Empty states have one sentence and one action; loading uses skeletons.

**Page jobs.** Home: health, attention, channels, activity. Analytics: four metrics, full-width Studio chart, striped report. Content: title-led list with platform details disclosed. Inbox: conversations with reply drawer/sheet. Queue: seven-day schedule then topics. Costs: budget and projection, channel bars, ledger. Automation: grouped settings without nested cards. Login: brand and one field group. Preserve platform navigation, actions, PWA and mobile tabs.

**Review.** Check every route at 390×844 and 1440×900 in both densities. Look for noise, repeated identity, secondary data in rows, excessive columns, spacing drift, small type and inaccessible touch targets. Record limitations honestly.
