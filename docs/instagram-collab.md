# Instagram cross-promotion and Collab research

Checked 2026-11-05. Only official Meta documentation informs this decision.
No authenticated API probes or live publishing were performed.

## Decision: Collabs remain unimplemented

Support for `collaborators` with **Instagram API with Instagram Login** is
unclear in the current official documentation. Do not enable or send this
parameter in this pipeline. `collab_posts_enabled` has no implementation and
therefore cannot activate it, even if someone adds that setting. Ordinary Reel
publishing remains the fallback; there is no speculative container retry or
second Reel upload. A monthly Collab allowance is consequently unnecessary.

## What the official pages establish

- [Content Publishing, Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing/)
  explicitly lists `graph.instagram.com`, an Instagram User token, and
  `instagram_business_basic` plus `instagram_business_content_publish` for this
  login type. Standard/Advanced Access apply according to the app's access level.
  It documents Reel container creation and publishing, and a general publishing
  limit of 100 API posts per moving 24 hours. It directs optional container
  parameters to the shared media reference, without clarifying Collab support
  for Instagram Login.
- [IG User media reference](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media)
  lists `collaborators` for feed images, Reels and carousels, with up to three
  Instagram usernames; Stories are excluded. However, the reference's creation
  requirements list Facebook Login permissions (`instagram_basic`,
  `instagram_content_publish`, `pages_read_engagement`, with extra advertising
  permissions in some Business Manager cases), and examples use
  `graph.facebook.com`. These are not proof that our Instagram Login token
  supports the parameter, and they are not instructions to add those scopes to
  our existing login flow.

The three-collaborator limit above is the documented parameter limit, **not** a
verified limit for our login type. The proposed two-per-UTC-calendar-month cap
is our business policy, not a Meta quota; it must be implemented if support is
confirmed later.

## Acceptance remains unverified for our login type

A caption @mention is a notification/tag, not co-authorship or acceptance of a
Collab invitation. The pages retrieved above do not establish how a recipient
accepts a Collab for Instagram Login or which permission authorizes acceptance.
The [collaboration invites reference URL](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/collaboration_invites)
and [accept invitation reference URL](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/accept_collaboration_invite)
returned generic developer page shells in this research session, without usable
endpoint specifications. Consequently automated acceptance, acceptance scopes,
and whether native-app acceptance is required cannot be asserted here. Owner
verification of official login-specific documentation is required before any
implementation. Do not infer support from Facebook Login, third-party blogs,
or the native app's Collab UI.

Initial browser fetches failed with access errors/429. Direct unauthenticated
GETs retrieved the publishing guide and shared media reference; the attempted
login-specific media reference URL returned 404. This is a documentation gap,
not evidence of an API rejection.

## Implemented caption mentions

Set each channel's `instagram_handle` to an owner-verified Instagram username.
All three are initially blank; existing `handle` values describe YouTube and are
never reused. `cross_mention_keywords` and `cross_mention_line` in each channel
config describe that channel's niche and the line used when mentioning it.
Matching is case insensitive with word boundaries, using the Reel title only,
so generic descriptions/footers cannot trigger promotion. Highest distinct-term
count wins, ties resolve by channel key. Self mentions, missing/invalid handles,
and captions already containing an @mention are skipped. Only one line is
appended, reserving space within Instagram's 2,200-character limit.

The shared setting `cross_mentions_enabled` must be the JSON boolean `true`;
missing, false, or string values keep it off. Normal publishing and manual
Instagram retries use the same helper. Facebook/YouTube captions are unchanged.

The account's latest three successful Instagram publications must contain no
cross mention before another is permitted (including three ordinary Reels at
startup). History joins publications to Short content by channel, excludes
failed/other-platform publications, and survives process restarts. To avoid a
schema migration, successful Instagram publications store a JSON
`cross_mention: {channel, handle}` audit marker in the existing nullable `error`
text column; it is success metadata, not a failure. Ordinary successes clear
old failure text. Replay retains the marker and original publication timestamp.
Existing publications without a marker count as ordinary Reels. Do not clear
these success markers when maintaining publication history.

Missing history/settings or invalid config skips promotion and allows the
ordinary Reel. At 1,000 Short content rows for an account, the helper fails
closed to avoid using potentially truncated Supabase history. Extend history
pagination before that threshold. The history check is not an atomic
cross-run reservation: concurrent publishers for the same account can both
qualify. Run one publishing job per account at a time to retain the approximate
one-in-four limit. No likes, reposts, duplicate uploads, or additional model
calls are introduced.

## Owner steps

1. Fill `instagram_handle` in `channels/<key>/channel.json` only after verifying
   each username in Instagram. Leave unknown accounts blank.
2. Review each channel's keyword list and mention wording for editorial fit.
3. When ready, set `settings.cross_mentions_enabled` to JSON boolean `true`
   using the existing settings mechanism (there is no dashboard toggle added).
   Public Reels still require `publish_privacy=public` and existing credentials.
4. Keep Collabs off. Revisit only when official documentation explicitly covers
   creation, permissions and recipient acceptance for Instagram Login. Future
   work must enforce two Collabs per account per UTC calendar month and safe
   container failure fallback without duplicate publication.
