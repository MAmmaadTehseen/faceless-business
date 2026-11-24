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

## Full ranked change list (every actionable item found)

Ranked by expected impact on views/retention for our format, then effort. "Where" names the pipeline area.

| # | Change | Where | Source |
|---|---|---|---|
| 1 | Enforce the six-block spine; reject scripts whose first 40 words lack a named actor or number | script prompt | RE |
| 2 | Hook = "[Actor] just [verb] [number]"; hook card text equals first spoken sentence | script prompt, hook card | RE, TH |
| 3 | Thumbnail: one subject/logo + one object, 3 words or fewer, strong verb, tone-matched colour, one-second readability check | thumbnail | TH, RE |
| 4 | Title pattern "[claim], [named authority] just confirmed it"; title, hook and thumbnail state the same claim | script prompt, thumbnail | RE, TH |
| 5 | At least two attributed quotes/excerpts from supplied sources in the evidence block | script prompt | RE |
| 6 | Context beat right after the hook that proves the claim | script prompt | RE |
| 7 | Recency news scan (Discover/News style) as ideation input; prefer mass-appeal, skip covered topics | ideation | TI |
| 8 | Add a "what nobody covered" own-angle to every topic; rival-transcript angle mining | ideation | TI |
| 9 | Topic scoring rubric: rising-not-saturated, brand fit, series potential, production feasibility | ideation | CM |
| 10 | Answer-first hub articles: question H2s, 40-60 word direct answer, list/table, FAQ block | hub | AEO |
| 11 | Application block ("why you should care") before the CTA | script prompt | RE |
| 12 | Simple CTA: ask for a comment, one-line subscribe reminder, no business pitch in most videos | script prompt, captions | RE |
| 13 | Never overstate in thumbnail/hook; reject conflict the body cannot support; verify digits and units in art text | thumbnail, QA | TH |
| 14 | Thumbnail refine loop in single-change steps; reuse prior winning thumbnails as style reference | thumbnail | TH |
| 15 | Per-script review checklist (strategy fit, voice, accuracy, value, CTA) as a QA step | QA/script prompt | CM |
| 16 | Home tab: featured best video, topic playlist sections, trailer if useful | channel setup (schedule/ops) | CO |
| 17 | Channel description: unique first sentence, signature phrase, why trust us, cadence, one free link | channel setup | CO |
| 18 | Watermark logo, consistent avatar/handle across YouTube, IG, FB; banner at 2048x1152 minimum | channel setup | CO |
| 19 | One opinionated, myth-busting post per long video from `beliefs.md`; link in the first comment | captions | FBB |
| 20 | Platform-adapted repurposing: 8-12 supporting pieces per long video (description, posts per platform) | captions | CM |
| 21 | Monthly explicit ask, otherwise story/belief posts; proof screenshot as image where available | captions | FBB |
| 22 | Pin and refresh a Community post per long video | captions/ops | CO |
| 23 | Organization schema with `sameAs` to channels; Article/FAQ/HowTo/VideoObject/Breadcrumb validated in Rich Results Test | hub | AEO |
| 24 | `robots.txt` allows AI crawlers, add `llms.txt`, keep pages fast and server-rendered | hub | AEO |
| 25 | Definition pattern ("What is X? X is ...") and 100-300 token self-contained sections | hub | AEO |
| 26 | Topical-authority publishing: consistent articles per defined topic set | hub, schedule | AEO |
| 27 | Off-site mentions (Reddit, publications); log AI-citation tests per target prompt | hub/ops | AEO |
| 28 | Query fan-out: write articles for the sub-questions of each core query | hub, ideation | AEO |
| 29 | Author/experience signals (EEAT): author schema, visible sources | hub | AEO |
| 30 | Weekly metrics loop (watch time, engagement, growth) feeding the next prompt update | schedule/ops | CM |
| 31 | Series potential: plan topics as series and cross-platform adaptations | ideation, schedule | CM |
| 32 | Commit to one platform's repurposing style for three months before judging | schedule | FBB |
| 33 | Keep testing topics; treat the channel as continuous experiments | ideation | CO |
| 34 | Slower, punchier hook line; one idea per sentence; number/name last (inference, A/B on one channel) | voice | inference |
| 35 | Do not copy huge-channel tactics blindly; they can skip steps small channels need | all | FBB |
