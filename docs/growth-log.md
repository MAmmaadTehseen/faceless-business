# Growth log

Standing loop: measure, diagnose, change, wait 1-3 days, measure again. Snapshot command (read-only):

```
PYTHONPATH=. .venv/bin/python scripts/growth_snapshot.py --days 30
```

Owner target (stated 2026-11-16): 10,000 views per day per video. Milestones on the way, in order:
1. Shorts retention above 70 percent (median today 36-58) so the platforms push past the first test pool.
2. A Short that keeps gaining views after day 2 (today every Short flattens within 48 hours).
3. Median Short above 1,000 views, then one Short past 10,000 total.
4. Daily views per video in the thousands, which on every comparable channel took months of 70 percent-plus retention, not weeks.

## Round 1: 2026-11-16

### Snapshot (last 30 days, public only)

| platform | channel | kind | n | median views | views/day median | median retention % | median AVD s | zero-view | comments |
|---|---|---|---|---|---|---|---|---|---|
| youtube | escapevelocity | long | 8 | 7.5 | 0.9 | 11 | 104 | 0 | 0 |
| youtube | escapevelocity | short | 25 | 24 | 5.0 | 36 | 27 | 0 | 0 |
| youtube | futurework | long | 11 | 7 | 0.7 | 16 | 80 | 1 | 4 |
| youtube | futurework | short | 24 | 14.5 | 1.8 | 40 | 20 | 1 | 0 |
| youtube | tradewinds | long | 8 | 2.5 | 0.2 | 27 | 112 | 3 | 0 |
| youtube | tradewinds | short | 26 | 47 | 8.2 | 58 | 35 | 0 | 0 |
| youtube | tentongues | all | 10 | 0 | 0 | n/a | n/a | 10 | 0 (day one) |
| instagram | escapevelocity | reel | 33 | 126 | | | | 0 | 0 |
| instagram | futurework | reel | 22 | 19.5 | | | | 0 | 0 |
| instagram | tradewinds | reel | 31 | 5 | | | | 2 | 0 |
| facebook | all | reel | 87 | 0 | | | | 85 | 0 |
| hub | all | pageviews | 48 views, 13 uniques, 40 from Pakistan (owner) | | | | | | |

Best Short: 620 views (escapevelocity, "The rescue didn't doom Swift"), retention 29 percent. Its view curve: 5 on day 0, 163 on day 1, 168 from day 2 onward for two weeks. Every Short follows that shape.
Shorts run 42-61 s (median 55); average view duration 20-35 s. Long videos run about 9 minutes with 80-110 s watched.
Posting times: Shorts go out at 13/15/18 UTC by channel; Reels went out in bursts of four within two minutes whenever a long video finished.

Comparison: a new faceless explainer channel typically sees 100-1,000 views per Short in the first test pool and single-digit views on long videos until Shorts bring subscribers. Our test pools are 100-600 impressions (visible as the day-1 jump), which is normal. What is not normal is that none of them get a second wave.

### Diagnosis (where the lag is)

- YouTube Shorts: impressions exist (the day-1 jump), so this is not zero distribution. Retention of 36-58 percent on 55-second Shorts is below the roughly 70 percent that earns a second wave, so each Short dies after its first pool. Zero comments on every upload confirms no engagement signal either.
- YouTube long: effectively no impressions (2-8 views). Expected at this age; longs grow from subscribers that Shorts bring. Retention 11-27 percent is weak but not the bottleneck yet.
- Instagram: escapevelocity reaches the normal non-follower test pool (median 126). futurework (19) and tradewinds (5) do not. Two likely causes: four Reels posted in two minutes (the second to fourth in each burst get 1-6 views on tradewinds) and captions that were the YouTube title plus a non-clickable YouTube link and `#shorts`, with no niche hashtags and no question.
- Facebook: unmeasured, not necessarily zero. The Page token lacks `read_insights`, the Reels `views` field returns 0, and the API refuses `video_insights`. Fix is owner-side (permission) plus the code change below.
- Hub: no organic traffic; the YouTube description links to articles are switched off (`yt_description_links_enabled` is unset).
- Ten Tongues: day one, nothing to judge.

### Hypotheses ranked (impact x cheapness)

1. Shorter Shorts with the payoff before 30 s lift retention to 70 percent and earn a second distribution wave. High impact, cheap (prompt change).
2. Spacing Reels one per day in step with the YouTube slot stops the burst penalty on IG/FB. High impact on IG for futurework/tradewinds, cheap (publisher change, no new infrastructure).
3. Captions with a hook line, a one-comment question and 3-5 niche hashtags raise comments and tell Instagram the niche. Medium impact, cheap.
4. YouTube Short descriptions with keywords, three hashtags and tags (child Shorts were uploaded with an empty description stub and no tags until publish time). Medium impact on search and suggested, cheap.
5. Facebook play counts via `video_insights` once the owner adds `read_insights`. Measurement only, cheap.
6. Hub article links in YouTube descriptions and playlists (settings already built, off). Owner toggle.
7. On-screen hook text card in the first second of each Short (render change). Medium impact, not done this round: touches render/QA and the running bank jobs.
8. Thumbnail and long-title work. Low impact until long videos get impressions; left for a later round.
9. Posting-time tuning. Not enough signal yet; IG by-hour numbers are noise at this volume.

### Shipped in round 1 (commit on main, 2026-11-16)

- Shorts scripts: 75-110 words (about 35-45 s) instead of 110-150; first sentence under twelve words naming an actor, object or number; payoff by sentence three; last line a one-comment question or a loop back to the hook. Applied to child Shorts (`pipeline/script.py`), daily Shorts (`pipeline/shorts_daily.py`, target 80-115, validation widened to 70-160 so saved responses still resume) and `persona/formulas.md`. Each channel's style.md keeps its own voice; only the length line changed.
- New `pipeline/publish/captions.py` (no model calls): Reels caption = spoken hook line, payoff sentence, closing question (script's own or `caption_question` from channel.json), "Full story on our YouTube channel" line, niche `hashtags` from channel.json. No links, no `#shorts`, no `@` (cross-mentions still added by the existing helper). YouTube Short description = hook, payoff, full-video link, channel footer, three niche hashtags plus `#Shorts`. Short tags = own tags, parent tags, then channel niche keywords, up to 15.
- `publish_short`: child Shorts no longer post Reels at production time when their YouTube copy is scheduled for the future. The existing `follow_youtube_to_reels` step in sync publishes them when YouTube makes the Short public, so Reels go out one per day per channel. Gated by shared setting `reels_follow_youtube` (default true). Standalone daily Shorts, Ten Tongues and Shorts without a scheduled YouTube row behave as before.
- `fb_insights`: tries `video_insights` Reel play metrics and keeps the larger of that and the object field; logs the missing-permission message once per video so the owner sees it.
- `scripts/growth_snapshot.py`: the measurement above, rerunnable.
- Tests: `tests/test_captions.py` (8 tests). Full suite: 388 passed.
- Added later the same day: `tighten_shorts` in `pipeline/script.py`. The word budget was prompt-only and the model has overshot before (today's bank run, written on the old prompt, produced 119-126-word Shorts). Every child Short now logs its word count, and any over 110 words gets one small `short_tighten` call (glm-5.3-flash on LunaRoute, effort low, 1500 max tokens) that cuts it to 75-110 words while keeping the hook, the facts and the closing question. A rewrite outside 60-115 words or a failed call keeps the original; resumed saved scripts are never re-paid. Tests: `tests/test_tighten_shorts.py` (4). Suite: 398 passed.

Not touched: bank/stockpile workflow, render, common.py, workflows. Already banked bundles keep their 110-150-word Shorts; new bank runs produce the shorter format.

### What should move, and by when (judge in round 2, on or after 2026-11-19; better 2026-11-23)

| metric | now | expect by round 2 | means |
|---|---|---|---|
| Shorts median retention (YouTube `ctr` column) on Shorts produced after 2026-11-16 | 36-58 % | 65 %+ | hook/length change works |
| Shorts still gaining views on day 3+ | none | at least one per channel | second wave earned |
| Instagram median views, futurework and tradewinds | 19 / 5 | 60+ | spacing + captions work |
| Instagram comments | 0 | any | question line works |
| Facebook plays (now measured) | 2 total across 85 Reels | any movement | Page needs followers first; low priority |
| YouTube Short comments | 0 | a few | closing question works |

Only Shorts whose content id date is after 2026-11-16 count; older queued Shorts (57 scheduled) carry the old scripts and only get the new descriptions when uploaded by the drain.

### Done by the agent on 2026-11-16 (no owner login needed)

- Facebook measured for real: `read_insights` added to the Meta app's Pages use case, new user token generated (owner clicked the consent popup), long-lived Page tokens exchanged and written to `.env` for all four Pages. Result: 85 Reels across the three Pages have 2 plays in total (1 futurework, 1 tradewinds, 0 escapevelocity). Facebook delivers nothing to Pages with no followers; the Reels there are free but worthless until the Pages have an audience. Keep posting (no cost) but judge growth on YouTube and Instagram only.

- `yt_description_links_enabled` and `cross_mentions_enabled` set to `true` in settings; hub links go into new YouTube descriptions and sister-account mentions switch on after three unmentioned Reels per account.
- `instagram_handle` filled for all three explainer channels from the API (`futurework.explained`, `tradewindsreport`, `escapevelocitydaily`).

- Community posts published 2026-11-16 on all four channels from the browser, each with the latest long video's closing question and link (Future Work: buyout list; Trade Winds: tariff ruling prices; Escape Velocity: asteroid suspects; Ten Tongues: bread). Repeat per long video.
- Comments: the only two in the database are the owner's own test comments, already answered. Nothing to reply to yet.
- Instagram Stories cannot be created from the desktop web app, so Reel-to-Story shares stay a phone task.

### Facebook and hub push (2026-11-16, owner asked for a hard effort on both)

Facts first: the four Pages have 0 followers each and no website link; the hub has 25 published articles, Search Console shows 2 indexed and 24 "Discovered, currently not indexed" (sitemap submitted 2026-10-30, last read 2026-11-15, 31 URLs), 1 search click in 30 days.

- Shipped: `pipeline/publish/hub_share.py`. Every published hub article becomes a Facebook Page link post on its channel's Page: new articles right after saving (produce and banked release), older ones backfilled by sync one per Page per UTC day, newest first. Message = title, the article's quick answer (two sentences), the channel's comment question, the link, two niche hashtags. No model calls, idempotent via `fb_article_post_<id>` settings, gated by `fb_article_posts_enabled` (default true). First three posts went out by hand on 2026-11-16 (one per explainer Page). Tests: `tests/test_hub_share.py` (4).
- Done in the browser: requested Google indexing for 8 articles (layoffs, China Busan deal, October jobs report, NASA astronauts, asteroid 1998 KY26, Suez, Kenya rare earths, AI chips seized). Google stopped accepting after that, which matches its daily quota. 16 remain; repeat on later days ("index more").
- Tried and blocked: setting each Page's website to its hub channel page needs `pages_manage_metadata` (API) and the facebook.com About view in the pane has no edit control; Bing Webmaster Tools needs a Google sign-in and OAuth consent that I will not do on the owner's behalf.
- Expectation: Facebook Pages with zero followers will not grow from posts alone. The link posts give the Pages a feed that is not just Reels and give the hub its first inbound links, but follower count is the gate, and the only free lever for that is the owner inviting their own friends from each Page. Hub: indexing requests usually land within days; judge by indexed count and search clicks in round 2, not by views.

### Owner-only levers (one line each)

- Facebook: on each of the three explainer Pages, "Invite friends" from your personal profile (196 followers there). This is the one action that gives the Pages a starting audience; nothing in the pipeline can.
- Facebook: add `pages_manage_metadata` to the app's Pages use case and regenerate the token the same way as `read_insights`, or set Website = https://hub.ammaad.online/c/<channel> by hand in each Page's details.
- Bing Webmaster Tools: sign in with the Google account, "Import from Google Search Console", accept. One minute, and it also covers DuckDuckGo.

- Run the `gh secret set` block from the 2026-11-16 chat so GitHub Actions uses the new Facebook tokens (the agent's secret write was blocked by the permission classifier).
- Ten Tongues phone verified 2026-11-16 (custom thumbnails now allowed).
- Reply to every comment by hand for the first weeks and pin one: the engage job drafts replies but early comment velocity is a ranking signal the owner can supply faster than a 6-hourly cron.
- Instagram: post one Story per Reel (all three accounts are already creator accounts, verified via the API 2026-11-16): the app surfaces Reels to followers through Stories, which the API cannot do.
- YouTube Community posts: the agent can post them from the browser pane each round; ask for it with "community posts".
- Subscribe the three channels to each other and like each other's Shorts from the owner account once; a single early engagement helps the test pool on a brand-new channel.
- Consider hub articles as the Shorts "link in bio" on Instagram (one link per profile): set each profile's link to `https://hub.ammaad.online/c/<channel>`.

### Carry forward to round 2

- Round 2 check: grep bank/produce logs for `short ... words` and `tightened` lines to see how often the model overshoots and whether tightened Shorts hold retention as well as natively short ones.

- If retention moves but views do not, the next lever is the on-screen hook card (render) and a trimmed first 2 s of footage.
- If Instagram tradewinds stays under 20 median with spaced posting, inspect the account itself (shadow restrictions, missing professional category) rather than captions.
- Ten Tongues: judge after seven episodes; its Shorts are 10 per day on one channel, which is a different test from the explainer channels.


## Round 2: 2026-11-17

### Snapshot (last 30 days, public only; round 1 in brackets)

| platform | channel | kind | n | median views | views/day | retention % | zero-view |
|---|---|---|---|---|---|---|---|
| youtube | escapevelocity | short | 25 | 28 (26) | 3.4 | 36 | 0 |
| youtube | tradewinds | short | 27 | 45 (41) | 7.0 | 58 | 1 |
| youtube | futurework | short | 25 | 15 (15) | 1.5 | 39 | 2 |
| youtube | all | long | 28 | 2-7 | 0.2-1.0 | 11-27 | 4 |
| instagram | escapevelocity | short | 33 | 126 (126) | 9.9 | | 0 |
| instagram | tentongues | short | 9 | 107 | 107 | | 0 |
| instagram | futurework | short | 23 | 19 (19.5) | 1.5 | | 0 |
| instagram | tradewinds | short | 32 | 6 (5) | 0.8 | | 3 |
| facebook | all | short | 98 | 0 | 0 | | 96 |
| hub | | | | 71 views, 34 uniques (48 / ~20) | | | US 22 (was ~8) |

Nothing material moved in one day, as expected. Hub uniques and US visits roughly doubled after the Facebook link posts and indexing requests; six Facebook link posts (three by hand, three by sync's backfill) show 0 clicks so far.

### Diagnosis: why round-1 changes cannot show yet

- Every explainer channel had one YouTube upload per day scheduled through 2026-12-09, all produced before round 1. The scheduler placed four child Shorts on four consecutive days per long video while each channel makes three longs a week, so the backlog grew by five days every week. The shorter hook-first Shorts (now consistently 82-110 words in bank runs) would not have reached the public until December.
- Bank mode (until 2026-11-24) banks everything new; `banked_release_per_day` is unset, so releases only add to the end of that queue.
- A regression from round 1: child Reels now wait for the YouTube slot, and sync's follow-up then ran on a fresh runner without the mp4 (`No such file or directory` in sync 44033158218 for old Shorts with no `media_url`). It also tried to post Reels for Shorts that went public weeks ago.
- The YouTube quota ran out at 11:50 UTC today. Correction after the fact: the parent session's `scripts/remove_ai_label.py` made 107 `videos.update` calls (about 5,350 units) at that time to clear the synthetic-media label, and they are in the 7,380 logged. Playlists are not the cause. The remaining 80 videos (about 4,000 units) are cleared after the 08:00 UTC reset on 2026-11-18, so schedule compression is capped per sync run (`compress_schedule_max_per_run`, default 20 updates = 1,020 units) and both fit in one day. Normal days should settle around 2-3k units.

### Shipped in round 2

- Scheduler: the three explainer channels now use `shorts_same_day: true`, `shorts_spacing_hours: 4`, `max_youtube_per_day: 3` in channel.json. Child Shorts fill the parent's day (long plus two Shorts, then the next day at the Shorts hour), never spilling past midnight. Ten Tongues unchanged.
- `pipeline/publish/reschedule.py` + `scripts/compress_schedule.py`: re-slots every future, non-public YouTube publication of a channel under the new calendar in its original order and pushes the new `publishAt` to YouTube (51 units each) and the database. Dry run today: futurework 18 uploads, last slot 2026-12-02 -> 2026-11-22; tradewinds 21, 2026-12-03 -> 2026-11-23; escapevelocity 26, 2026-12-09 -> 2026-11-28. The apply hit Google's quota wall at the first update, so sync now runs `compress()` every six hours (setting `compress_schedule_enabled`, default true) and stops cleanly on quota errors; the backlog moves as quota allows, starting after the 08:00 UTC reset.
- Reels follow-up: restores media through the existing retry/queue paths, skips Shorts with no media on the runner instead of raising, and only follows Shorts whose YouTube copy went public in the last 7 days.
- Tests: `tests/test_reschedule.py` (2), same-day scheduler test, Reels follow-up regression test. Suite: 410 passed.

### What should move by round 3 (2026-11-21 or later)

| metric | now | expect |
|---|---|---|
| explainer uploads going public per channel per day | 1 | 2-3 within a week (watch `compressed schedule` lines in sync logs) |
| days until the hook-first Shorts are public | ~20 | 5-9 |
| Reels follow-up errors in sync | several per run | 0 |
| Facebook link-post clicks (6 posts) | 0 | still ~0 until Pages have followers |
| hub uniques / 30 days | 34 | 60+ once 24 articles are indexed |

### Carry forward / owner

- Sign in to Google in the browser pane again (it came back signed out) so I can request indexing for the remaining 16 articles, 8 a day.
- Decide whether to release banked bundles before 2026-11-24 (`banked_release_per_day` = 1 per channel) now that the calendar can absorb 2-3 uploads a day.


## Round 2b: hooks and SEO research, 2026-11-17 (owner: "are you even trying")

### What our own 72 public Shorts say

| retention bucket | n | median views |
|---|---|---|
| under 35% | 26 | 16.5 |
| 35-50% | 16 | 16.5 |
| 50-70% | 17 | 52 |
| over 70% | 13 | 69 |

Retention is the only trait that correlates with views (r = 0.18; words, title length, numbers and questions in titles are all near zero). Every top-ten Short names a concrete thing in its first sentence (Swift, Starship, Artemis, a $20 billion bill, a 342 percent freight rise). Every bottom-ten Short opens on an abstraction (a Dutch budget, "here's an unpopular take", "your old job might come back", a door latch). Long videos: titles are clever, not searchable ("The Catch Isn't the Real Test"), so they get 2-8 views with no search entry.

### What the research says (vendor blogs, no official YouTube numbers; treat thresholds as rough)

- Shorts: distribution is a staged test; the first filter is swipe-away in the first 2-3 seconds, the second is completion (65% for under-30 s, 50% for 30-60 s). Faceless Shorts autoplay muted, so the first frame must state the topic in text. Loops add replays. Sources: [ContentMatch](https://contentmatch.io/youtube-shorts-algorithm-viewed-vs-swiped-ratio-2026/), [virvid](https://virvid.ai/blog/first-3-seconds-hook-faceless-shorts-2026), [1of10](https://1of10.com/blog/youtube-shorts-analytics/), [socialync](https://www.socialync.io/blog/youtube-shorts-algorithm-2026), [vidIQ hooks](https://vidiq.com/blog/post/viral-video-hooks-youtube-shorts/).
- Long-form SEO: keyword in the first 40 characters of the title, keyword in the first sentence of the description, chapter labels as search phrases, tags nearly irrelevant. Sources: [vidIQ](https://vidiq.com/blog/post/youtube-seo/), [outlierkit](https://outlierkit.com/resources/youtube-seo/).
- Instagram: Trial Reels are the non-follower lever (needs a professional account with enough followers; not exposed in the Instagram Login API), keyword in the first 125 caption characters, said aloud and shown on screen; cover frame matters. Sources: [Hootsuite](https://blog.hootsuite.com/instagram-reels/), [brandID](https://brandid.app/blog/instagram-trial-reels/), [Toptal](https://www.toptal.com/creator/post/instagram-seo).
- Facebook: single-digit Reel views on a Page usually means a "not recommended" flag (check Meta Business Suite > Account status), links in captions, or a cold-start Page with no engagement history. Sources: [lilachbullock](https://www.lilachbullock.com/facebook-reels-not-getting-views/), [advertiserreview](https://advertiserreview.com/social-media/facebook/reels-not-showing/).

### Shipped

- Hook card: every explainer Short now opens with its hook title burned in as a bold boxed headline in the upper third for the first 2.5 s (`pipeline/render.py`, `hook_text`), clear of the action rail and the centred captions; one drawtext per line because ffmpeg 8 draws newlines as missing glyphs. The same frame is the Instagram cover (thumb offset 2 s) and the Facebook Reel cover. Verified on real frames.
- Prompts: `hook_title` under 45 characters naming the subject (proper noun or number) in its first three words; long-video title starts with the searchable subject inside 40 characters, then the angle; description's first sentence states the subject plainly; chapter labels are search phrases. Ideation now prefers topics with a nameable actor plus a hard number, because that is what the top ten have and the bottom ten lack.
- Reels captions already lead with the spoken hook line, carry no links and use niche hashtags (round 1); Facebook Reels get the same caption.

### Not possible from here (owner)

- Instagram Trial Reels: toggle "Trial" when posting from the app; the API we use has no such flag. Run two or three a week per account.
- Facebook: open Meta Business Suite > Account status for each Page and tell me if any says "not recommended"; and invite friends to the Pages. Zero followers plus no engagement history is a cold start nothing automated can fix.
- YouTube Studio: for the next Shorts, read "Viewed vs swiped away" and "Stayed to watch"; I cannot read those through the API.

### Expect

Hook card plus named-subject rules target the 2-second swipe and the 50% retention line. If the next 20 Shorts median above 50% retention, median views should move from the teens to 50+ per the table above, before any algorithmic expansion. 10k a day per video needs the expansion stage; that is a retention problem first, and this is the first round that attacks the muted first frame directly.


## Round 3 check-in: 2026-11-18

Owner: no difference in analytics. Correct, and expected: nothing shipped on 2026-11-16/17 had reached a public video yet. Nine videos went public since 2026-11-17, all rendered and uploaded before round 1 (views 0-95; the 95 is Escape Velocity's "Starlink Dies in Five Years, On Purpose", the one title with a hard named subject). Already-uploaded videos cannot have their file replaced, so the backlog going public this week performs like the old format regardless.

- Schedule compression ran from sync: Future Work's last slot moved 2026-12-02 -> 2026-11-25, Escape Velocity 2026-12-09 -> 2026-11-28, Trade Winds mostly moved (one straggler on 2026-12-03 waits for the per-run cap). All three channels now have 2-3 uploads a day through 2026-11-24.
- Banked bundles were rendered before the hook card existed. Commit 21bcc05: release now burns the card onto each banked Short (one ffmpeg re-encode, audio copied) before upload, so bundles released from the next sync carry it.
- Dispatched one public produce run per explainer channel (new scripts, subject-first titles, hook card, same-day Shorts) so the first fully new-format bundles go public at the next cron slots (2026-11-19/20) rather than after the bank.
- First readable signal: 2026-11-21 (48 h of public life on card-bearing Shorts). Compare "Viewed vs swiped away" in Studio and retention via `scripts/growth_snapshot.py` for Shorts published on/after 2026-11-19 against the round-2b table.
