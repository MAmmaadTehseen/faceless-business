"""Evergreen inventory, checked against complete channel history before each pick."""
import json
from difflib import SequenceMatcher
from .common import CHANNELS_DIR, slugify

SOURCES = {
    "futurework": ["https://www.nist.gov/itl/ai-risk-management-framework", "https://www.ilo.org/topics-and-sectors/future-work", "https://www.oecd.org/en/topics/artificial-intelligence.html", "https://www.cisa.gov/secure-our-world"],
    "tradewinds": ["https://www.imf.org/en/Publications/fandd/issues/Series/Back-to-Basics", "https://www.worldbank.org/en/topic/trade", "https://www.wto.org/english/thewto_e/whatis_e/tif_e/tif_e.htm", "https://unctad.org/topic/transport-and-trade-logistics"],
    "escapevelocity": ["https://science.nasa.gov/universe/", "https://www.esa.int/Science_Exploration/Space_Science", "https://www.eso.org/public/science/", "https://www.noaa.gov/education/resource-collections/space-weather"],
}



def history(db, channel):
    # Supabase select defaults to a bounded page; explicitly paginate live history.
    if getattr(db, 'sb', None):
        rows, offset = [], 0
        while True:
            page = db.sb.table('content').select('id,title,topic').eq('channel', channel.key).order('id').range(offset, offset + 999).execute().data or []
            rows.extend(page)
            if len(page) < 1000:
                return rows
            offset += 1000
    return db.select('content', {'channel': channel.key})


def duplicate(topic, titles):
    norm = slugify(topic, 500)
    return any(SequenceMatcher(None, norm, slugify(t, 500)).ratio() >= .65 for t in titles if t)


def inventory(db, channel):
    saved = db.setting('evergreen_topics_' + channel.key)
    if saved is not None:
        return saved
    path = CHANNELS_DIR / channel.key / 'evergreen.json'
    return json.loads(path.read_text()) if path.exists() else []


def choose(db, channel):
    titles = [r.get(k, '') for r in history(db, channel) for k in ('title', 'topic')]
    for item in inventory(db, channel):
        topic = item['topic']
        if not db.setting('evergreen_used_' + channel.key + '_' + slugify(topic, 100), False) and not duplicate(topic, titles):
            # Durable across ephemeral Actions runners; channel bank jobs are serialized.
            db.set_setting('evergreen_used_' + channel.key + '_' + slugify(topic, 100), True)
            sources = item.get('source_urls') or SOURCES[channel.key]
            return {'evergreen': True, 'news': [{'url': url} for url in sources], 'topic': topic, 'angle': item.get('angle', '') + '\nEvergreen: explain durable mechanisms; no latest news, current prices, dates or predictions tied to today.',
                    'source_url': sources[0], 'source_headline': None, 'queue_id': None}
    raise RuntimeError('Evergreen list exhausted; owner must generate more topics')
