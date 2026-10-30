# Plainsight Media design contract

Reading comfort first, brand second, chrome last. Typography carries the design.

- Source Serif 4, vendored Google font self-hosted by next/font/local with preloading and display swap, for headlines and prose. Arial/Helvetica for UI. Desktop prose 18px/1.65; mobile 17px/1.6. Article measure 680px (roughly 65–72 characters). Hero headline 44px/1.1, article h1 40px, h2 26px, h3 20px. No drop caps.
- Light: warm paper near-white; dark: warm near-black. Follow system preference until a reader chooses a theme. No gradients or glass. Channel accents appear only in channel labels, channel link underlines, card top rules and evidence left rules. Text must remain legible in both themes.
- Use an 8px spacing scale; sections breathe at 64px/96px. Prose paragraphs have 1.25em separation. Images fill the text column at 16:9; captions are muted 13px.
- Components: image-led article cards with channel, title, one-line dek, date and read time; channel headers; evidence pull quotes with label, text and source; native FAQ details; stable video facade cards; previous/next; related stories; quiet CTA; channel/legal footer.
- Home: lead plus two secondary stories; three channel rows of up to three stories each, never more than 12 cards. No newsletter.
- Channel: header, subscribe and RSS, two-column archive, 12 stories per page.
- Article: title/dek/byline, generated OG hero, summary, takeaways, prose/evidence/video at its marker, FAQ, quiet CTA, previous/next, three related. Tiny reading progress; left-gutter contents only above 1280px.
- About and Privacy: plain article-width prose.

Keep metadata, canonical/alternate URLs, JSON-LD, sitemap, feeds, OG routes, analytics and tracked facade intact. Verify build, rendered SEO and 390/1440px light/dark screenshots. Test fixtures are explicitly opt-in and never replace production reads.

## Motion

Motion for React (`motion/react`) is confined to small client islands: LazyMotion +
`domAnimation`, `m.button` and the shared spring provide tactile presses without
turning server-rendered stories into client components. CSS view timelines handle
reveals; an IntersectionObserver provides progressive enhancement when unavailable.
Reading progress uses a native root scroll timeline and section-based observer
steps as its fallback, with no scroll listeners. Native same-document View
Transitions wrap router navigation and name only the selected card image/title;
unsupported browsers retain ordinary Next links. The image/title remain visible
at first paint. Theme changes use a circular native transition and a sun/moon icon.
Lenis is omitted: native scrolling avoids extra work on the input path.

Tokens are 150/250/400/600ms, cubic-bezier(.22,1,.36,1), and one spring in
`src/lib/motion.ts`. CSS mirrors these in custom properties. Reduced motion disables
all animation and smooth scrolling. Space is reserved with existing image ratios.
FAQ content uses a short transform/opacity reveal within native details: animating
height conflicts with the transform/opacity-only performance rule, so opening height
changes instantly. No layout animation is used. View Transitions themselves interpolate
snapshot geometry through the browser's native implementation.

Measured route sizes, vitals and reproduction steps: [MOTION-REVIEW.md](MOTION-REVIEW.md).

## Editorial motion revision (30 October)

The owner's follow-up permits a quiet CSS ambient masthead gradient and a short
spring-shaped height animation for explicitly activated FAQ details. These override
the earlier no-gradient and instant-height rules above. The headline remains opaque,
its shallow line masks preserve first paint, and below-fold paragraph enhancement
starts only after hydration. Pointer tilt is capped at 2 degrees and magnetic travel
at 6px; pointer work runs only in response to fine-pointer events, throttled with rAF.
The native cursor remains available. Runtime preference changes cancel active motion.
Article image order is persisted public media, verified YouTube maxres/hqdefault,
article OG, then local channel artwork. Never infer image availability from ID alone.

The revision uses Motion's `motion/react-mini` scoped Web Animations hook for
button presses. It replaces the older LazyMotion/domAnimation wrapper described
above, avoiding a separate feature download while retaining Motion in a small
client island. Native/CSS APIs handle the editorial entrances and shared snapshots.
