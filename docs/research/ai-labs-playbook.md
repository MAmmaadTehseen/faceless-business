# AI Labs playbook for our faceless channels

Source: AI Labs / First Movers course transcripts (Julia McCoy), read 2026-11-24. Paraphrased; each point cites
`[course › lesson]`. Short keys: **RE** = reverse-engineer-viral-youtube-ai (single lesson: "Reverse-Engineering a Viral YouTube Hit");
**FBB** = julias-fbb-formula-organic-views (single lesson); **TI** = topic-ideation-for-your-youtube-channel (Tutorial);
**CO** = channel-optimization-101 (Tutorial); **TH** = julias-youtube-thumbnail-system (Thumbnail System Tutorial);
**CM** = content-multiplication-formula-julia (Watch Video); **AEO** = answer-engine-optimization-mastery (Lesson 5, Course Overview, quiz).

**Caveat (read first).** The courses are built around a human/clone-fronted business channel selling services. They say
almost nothing on second-by-second Shorts hooks, pacing, or TTS delivery. Items marked *(inference)* are our extrapolation,
not course content. Julia's own growth claims (2M views/month) are self-reported and come from a face-led channel; our
faceless stock-footage format may not reproduce them. Treat everything as hypotheses to A/B in `docs/growth-log.md`.

## 1. Hooks

What the course says:
- A long video opens with one hook that is a shocking, named-authority claim (a CEO/major company predicting or announcing something), stated as fact, then immediately backed with context. [RE]
- The hook is only the first of six blocks: hook, context, core message, evidence, application ("why should I care"), CTA. [RE]
- Quote or excerpt notable people in the field inside the video; it raises perceived value. [RE]

Fill-in templates (built from the above; length limits are *(inference)*):
- Long, first 15 s: `[Named actor] just [specific, checkable action/number]. [One sentence of why that breaks the usual assumption.] Here is what it means for [viewer role], and what the numbers actually say.`
- Short, first 1-3 s (spoken and on the hook card, subject first): `[Named actor] just [verb] [number/thing].` / `[Big claim in <=8 words]. Here is the catch.`
- Context beat right after (next 5-10 s): `That matters because [one-sentence stake]. [Source] said [paraphrase].`
- Do not manufacture conflict the video cannot support; the thumbnail lesson explicitly warns against misleading. [TH]

## 2. Script structure and pacing

- Fixed spine for every long video: Hook → Context (proves the hook) → Core message (future, takeaways, what to do) → Evidence (industry examples, expert validation, market impact) → Application (personal relevance) → CTA. [RE]
- CTA: ask for engagement (comment) then a one-line subscribe reminder; keep it simple and do not pitch the business in most videos. [RE]
- Spend promotion rarely; a dedicated "what we do" video produced bookings once but is the exception. [RE]
- Every script is reviewed for strategy fit, voice consistency, brand accuracy, audience value and CTA effectiveness before production; the goal is systematic consistency rather than first-try perfection. [CM]
- *(inference, not in courses)*: open one loop in the hook and pay it off in the last third; put the single strongest evidence before the 40% mark; end on the application line, not a recap.

## 3. Titles and thumbnails

- Thumbnail text: powerful, simple statement of three words or less; negative statements work, tied to a matching colour (red for "something broke"). [RE] Hook text is 2-4 words, dramatic/urgent/curiosity-driven, with strong verbs (broke, exposed) and "just" for recency. [TH]
- Two-element rule: one subject plus one clear object/concept, understandable in one second; a bare face (or bare text) is weaker than a relationship between two elements. Simpler can beat busier. [TH]
- Use logos/names of the actors in the story (the viral hit pictured the companies involved). [RE] For us: the named actor's logo or an iconic frame replaces Julia's face.
- Colour matches the tone of the claim. [RE] Sponsor/logo, if any, is large and in a high-attention area. [TH]
- Process: read script → one-line core conflict → 2-4 word hook → concept (subject + object + emotion) → generate → evaluate ("if you must think, it is weak") → refine in small single-change steps, not one big prompt. [TH]
- Title (from RE's example): `[Provocative claim], [named authority] just confirmed it`; ties title, hook and thumbnail to the same claim. [RE]
- Fact-check numerals in generated art (the course's own example misread "$200K per month" as views). [TH]

## 4. Topic selection

- Daily news scan: Google Discover (trains to your clicks) plus Google News filtered to "news" and the last few hours/day; choose items with mass appeal, skip topics already covered. [TI]
- Second source twice a month: YouTube search of the niche keyword; note what surfaces on top. [TI]
- For a promising rival video, pull its transcript, then have the model write an original video from it and add the channel's own thought/angle ("what they have not covered"). [TI]
- Curation criteria: viral potential (trending, rising not already saturated), value/brand alignment, series and cross-platform potential, production feasibility; about five minutes per topic. [CM]
- Tools named: BuzzSumo, Exploding Topics, social listening, news aggregators, competitor analysis. [CM]
- The human stays the source of ideas and adds a personal angle; AI executes. [TI, CM]

## 5. Voice and delivery

The courses cover the clone/avatar only as consistency (same voice, no off days), plus disclosing it is a clone (the clone says so on camera). [RE, CM] Nothing on pace, emphasis or humanising TTS. We should not claim course support here.
*(inference)*: keep the hook line slower and punchier than the body; one idea per sentence; vary sentence length; put the number or name last in a sentence; avoid filler openers; test Kokoro speed per channel with the retention graph, not by ear.

## 6. Repurposing

- One core video becomes 5-10 (or 8-12) supporting pieces: description, SEO text, social posts per platform, email; each adapted to its platform's tone (LinkedIn professional, X conversational). [CM]
- Metadata (descriptions, thumbnail, posts) is generated by the same trained project with the same brand rules. [CM]
- Social post pattern (FBB): rotate three categories, family/personal, beliefs/opinions, business; write each from a strong point of view in plain direct language; 15 minutes every two days; commit to one platform for three months; once a month make an explicit ask. [FBB] Opinionated or myth-busting posts drew the most response; a proof screenshot (testimonial/email) as the image works. [FBB]
- Link goes in the first comment, post body carries the story. [FBB]
- Fit for us: the "family" pillar does not apply to faceless brands. Map it to persona/behind-the-build notes; keep beliefs (`beliefs.md`) and business (the video) as the other two.

## 7. Channel setup items we may be missing

- Description: first sentence states exactly what makes the channel unique; then signature phrase, why trust us, mission, perspective, what viewers will get, upload cadence; links to one free offer. [CO]
- Banner (at least 2048x1152), recognisable avatar identical across platforms, simple handle, watermark logo on all videos. [CO]
- Home tab: a single featured video chosen to build authority (best performer), shown to new and returning visitors alike; add a trailer section if useful; playlists as sections; link sister channels. [CO]
- Pin a Community post and keep the channel's best video as the featured one. [CO]
- Everything is still a test, even after months; keep testing topics. [CO]

## 8. Hub/blog AEO and SEO quick wins

- Question-based H2/H3 headings; each directly followed by a 40-60 word direct answer; lists and tables instead of dense prose; each section independently extractable (about 100-300 tokens). [AEO › Lessons 5, 11, 12 and quiz Q12-14]
- Definition pattern: "What is X? X is ...". [AEO › Lesson 11 outline]
- Schema priority: Organization, FAQ, Article, How-To, then Breadcrumb and VideoObject; validate with Google's Rich Results Test; one broken implementation can negate the rest. [AEO › Lessons 5, 6, 10]
- Allow AI crawlers in robots.txt, consider llms.txt, keep pages fast and server-rendered. [AEO › Lesson 5, community post]
- Consistent publishing on a defined set of topics builds topical authority. [AEO community post]
- Most citations come from off-site mentions (Reddit, YouTube, publications), so mentions without links also count. [AEO course summary and community post]
- Measure by running target prompts in ChatGPT/Google AI/Gemini and logging when we are cited. [AEO › Lesson 5]
- Already in our hub per AGENTS.md: JSON-LD (Article/FAQ/Breadcrumb/Video), sitemap, RSS. Gaps to check: answer-first paragraph under each H2, Organization schema with `sameAs` to the channels, llms.txt.

## Top 10 changes for our pipeline (ranked by expected impact / effort)

1. **Spine enforcement in the long-script prompt** (script prompt): require Hook (named actor + checkable claim) → Context → Core → Evidence → Application → CTA, and fail validation if the first 40 words lack a named actor or number. [RE]
2. **Subject-first claim hook, shared by narration and hook card** (script prompt + hook card): hook card text equals the first spoken sentence; template `[Actor] just [verb] [number]`; no hook may promise more than the body shows. [RE, TH]
3. **Thumbnail two-element rule with 2-4 word strong-verb text** (thumbnail): one subject/logo plus one object, text three words or less, colour tied to tone, reject candidates that need more than one second to read; verify digits and units in the text. [TH, RE]
4. **Evidence block with named quotes/excerpts** (script prompt): require at least two attributed expert or company statements drawn from the supplied sources only (already our citation rule). [RE]
5. **Topic ingestion from news plus rival-transcript angle** (ideation): add a Google News/Discover-style recency scan and "what has nobody covered" angle to the ideation prompt; skip topics already used; prefer mass-appeal items. [TI, CM]
6. **Topic scoring rubric** (ideation): score viral potential (rising, not saturated), brand fit, series potential, production feasibility; pick the top. [CM]
7. **Channel home-tab and description audit** (schedule/ops, one-off task): featured video = best performer, topic playlists as sections, description with unique first sentence and cadence, watermark, consistent avatar. [CO]
8. **Hub articles in answer-first form** (hub/article prompt): question H2s, 40-60 word direct answer first, one list or table per article, FAQ block with FAQ schema, Organization schema with `sameAs`, llms.txt. [AEO]
9. **Captions: opinionated post per long video plus a pinned first-comment link** (captions): one strong-viewpoint post per platform using `beliefs.md`, link in first comment, monthly explicit ask; cross-post shaped per platform. [FBB, CM]
10. **Hypothesis-labelled experiments for delivery** (voice): A/B Kokoro speed and a slower hook line on one channel, judged by Shorts retention; the courses give no data, so record results in `docs/growth-log.md`. *(inference)*
