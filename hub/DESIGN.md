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
