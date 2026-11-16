# Channel setup brief (three channels + hub)

Owner: Ammaad. Repo: ~/Documents/faceless-business. Secrets go ONLY into the local `.env` file (never into chat, never committed).

## The three channels

| Key | Channel name | YouTube + Instagram handle | Niche | Voice | Palette |
|---|---|---|---|---|---|
| futurework | Future Work Explained | @futurework.explained (exists) | AI, work, money, online safety | male, US | navy + amber |
| tradewinds | Trade Winds Report | @tradewindsreport | global power and economics: trade, sanctions, energy, chips, shipping, currencies (no war footage, no partisan takes) | male, British | dark maroon + sand |
| escapevelocity | Escape Velocity | @escapevelocitydaily | space and frontier science: launches, Mars, fusion, asteroids, telescopes | female, US | black + cyan |

Brand files per channel in `assets/brand/<key>/`: avatar-800.png, youtube-banner-2560x1440.png, facebook-cover-1640x624.png, watermark-150.png, profile-card-1080.png.

### Bios and descriptions

**Trade Winds Report**
- Tagline: Who holds the power and who pays the price: trade, energy, chips and money.
- YouTube description: Trade Winds Report follows the money behind world events: trade routes, sanctions, energy deals, chip supply chains and currencies, and explains what they mean for prices, jobs and markets where you live. Three videos a week. No partisan takes, sources in every description. Narration is AI-generated from scripts researched and reviewed for this channel.
- Keywords: geopolitics, global economy, trade war, sanctions, energy prices, semiconductors, shipping, oil, central banks, supply chain
- Google News keywords (settings): tariffs, sanctions, oil prices, semiconductor export, shipping route, central bank, trade deal, rare earths, energy crisis, currency

**Escape Velocity**
- Tagline: Launches, missions and the science that gets us off this rock.
- YouTube description: Escape Velocity covers every launch, mission and discovery that matters: Artemis, Starship, Mars, asteroid defense, fusion, telescopes and the companies racing to orbit. Three videos a week, plain English, sources in every description. Narration is AI-generated from scripts researched and reviewed for this channel. Footage courtesy of NASA, ESA and public archives.
- Keywords: space, NASA, SpaceX, Starship, Artemis, Mars, astronomy, rocket launch, James Webb, fusion
- Google News keywords (settings): NASA, SpaceX launch, Starship, Artemis, Mars mission, James Webb telescope, asteroid, fusion energy, ESA, satellite

**Future Work Explained** (already set up; see channel description in the YouTube Studio)

## Accounts the owner creates (nobody else can)
1. Two YouTube brand channels under the same Google account: "Trade Winds Report" (@tradewindsreport) and "Escape Velocity" (@escapevelocitydaily). Studio: Settings, Channel: country Pakistan, keywords above; Advanced: not made for kids; verify phone.
2. Two Instagram accounts with the same handles, switched to Professional (Creator).
3. Facebook Pages: each Instagram account must be linked to its own Facebook Page (a Page can hold only one Instagram account). Create "Trade Winds Report" and "Escape Velocity" Pages; they can stay unpublished. The public hub Page comes later under the hub name.
4. Link each Instagram account to its Page: Instagram, Settings, Accounts Center, Add accounts.

## Browser work (guided)
A. YouTube Studio branding for both new channels: Customization, Branding: picture = avatar-800.png, banner = youtube-banner-2560x1440.png, watermark = watermark-150.png (entire video). Basic info: description above, links: the other channels. Upload defaults: category Science & Technology, language English, not for kids, synthetic content Yes, visibility Private.
B. YouTube API authorization per new channel (same Google Cloud project and OAuth client as the first channel):
   `cd ~/Documents/faceless-business && .venv/bin/python scripts/youtube_auth.py url tradewinds` -> open the printed URL, choose the Trade Winds Report channel when Google asks which account/brand, Allow, copy the final localhost URL ->
   `.venv/bin/python scripts/youtube_auth.py token "<pasted url>" tradewinds`  (saves YT_REFRESH_TOKEN_TRADEWINDS). Repeat with `escapevelocity`.
C. Meta app "Future Work Explained" (already created, App ID in App settings, Basic): use case "API setup with Facebook login" -> Add required permissions; Permissions and features -> add pages_manage_posts, pages_manage_engagement, pages_read_user_content. Graph API Explorer -> Get User Access Token with all pages_* and instagram_* permissions above -> allow ALL three Pages and ALL three Instagram accounts in the popup -> copy token ->
   `.venv/bin/python scripts/meta_token.py APP_ID APP_SECRET SHORT_TOKEN` prints META_PAGE_ID / META_IG_USER_ID / META_ACCESS_TOKEN per Page. Write them into .env with the channel suffix: META_PAGE_ID_FUTUREWORK, META_IG_USER_ID_FUTUREWORK, META_ACCESS_TOKEN_FUTUREWORK, and the same for _TRADEWINDS and _ESCAPEVELOCITY.
D. Instagram: profile picture avatar-800.png, bio = tagline, post profile-card-1080.png once. Facebook Pages: profile picture + cover.
E. When done, run the GitHub secrets sync:
   `cd ~/Documents/faceless-business && grep -E "^[A-Z_]+=.+" .env | grep -vE "^(CLAUDE_MODEL|PEXELS_RATE_LIMIT_PER_HOUR|OUT_DIR)=" > /tmp/secrets.env && gh secret set -f /tmp/secrets.env -R MAmmaadTehseen/faceless-business && rm /tmp/secrets.env`
   and add the new META_* and YT_REFRESH_TOKEN_* variables to Vercel, then redeploy.

## Ten Tongues (fourth channel, key `tentongues`, added 2026-11-16)

Handle `@tentongues` on YouTube; Instagram `@ten.tongues` (`tentongues` was taken, created 2026-11-16); Facebook Page "Ten Tongues" (profile id 61596311564829, Page/API id 1404506206082740, created 2026-11-16). Brand files in `assets/brand/tentongues/`
(avatar-800.png, youtube-banner-2560x1440.png, watermark-150.png, facebook-cover-1640x624.png, profile-card-1080.png).
Palette: violet (167,139,250) on dark aubergine. Voice: Kokoro af_bella (narrator) plus one voice per language.

- Tagline: One everyday English word a day, taught in ten languages.
- YouTube description:
  Ten Tongues teaches one everyday English word a day in ten languages: Mandarin, Hindi, Spanish, French, Bengali, Portuguese, Russian, Urdu, Japanese and Italian. In every episode you hear the word twice from a native-language voice, one example sentence, a memory hook and a cultural note. One full episode every day at 07:00 UTC, then one Short per language, each collected in its own playlist (Spanish word of the day, Hindi word of the day, and so on).
  Narration and pronunciation audio are AI-generated. Pronunciation is a guide, not a native speaker: check it with one before an exam.
  Bengali voice: Piper bn_BD-google (OpenSLR 37, CC BY-SA 4.0; CMU Indic).
  New word every day: subscribe.
- Keywords: learn languages, word of the day, how to say, pronunciation, vocabulary, language learning, polyglot, Spanish, Hindi, Mandarin, French, Japanese, Urdu, Bengali, Portuguese, Russian, Italian
- Channel links (Basic info): Future Work Explained https://www.youtube.com/@futurework.explained, Trade Winds Report https://www.youtube.com/@tradewindsreport, Escape Velocity https://www.youtube.com/@escapevelocitydaily
- Instagram bio (136 chars): One everyday English word a day in ten languages. AI narration and pronunciation, one Reel per language daily. Full episodes on YouTube.
- Facebook Page about: Ten Tongues teaches one everyday English word a day in ten languages: Mandarin, Hindi, Spanish, French, Bengali, Portuguese, Russian, Urdu, Japanese and Italian. Daily full episode and one Short per language on YouTube (@tentongues). Narration and pronunciation audio are AI-generated; pronunciation is a guide, not a native speaker. Bengali voice: Piper bn_BD-google (CC BY-SA 4.0). Page category: Education website.
- Settings > Channel: country Pakistan, keywords above; Advanced: not made for kids.
- Upload defaults: category Education, video language English, not made for kids, altered or synthetic content Yes, visibility Private (the pipeline sets its own privacy and publishAt).

Meta tokens follow section C above with the same app. The Instagram token uses the "Instagram API with Instagram Login"
route (add @tentongues as an Instagram Tester on the app's "API setup with Instagram login" page, accept the invite in
Instagram, generate the 60-day token there). Variables: META_PAGE_ID_TENTONGUES, META_ACCESS_TOKEN_TENTONGUES
(from `scripts/meta_token.py`), META_IG_USER_ID_TENTONGUES and IG_ACCESS_TOKEN_TENTONGUES (from the Instagram Login page;
`GET https://graph.instagram.com/v21.0/me?fields=user_id,username` returns the id). Then the owner runs
`gh secret set` for those four names plus YT_REFRESH_TOKEN_TENTONGUES and adds them in Vercel.

## Done looks like
`.env` contains YT_REFRESH_TOKEN_TRADEWINDS, YT_REFRESH_TOKEN_ESCAPEVELOCITY, and META_PAGE_ID/META_IG_USER_ID/META_ACCESS_TOKEN for all three channel suffixes; GitHub secrets updated; both new channels branded; all three Instagram profiles branded.
