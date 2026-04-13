# recuperer les  paroles synchronisees en ligne (lrclib + syncedlyrics)
import re
import logging
import requests

log = logging.getLogger('karaoking')

LRCLIB_API = 'https://lrclib.net/api'
UA = 'KaraoKing/1.0 (karaoke-africain)'

# bruit dans les titres youtube
TITLE_NOISE = [
    r'\(.*?official.*?\)', r'\[.*?official.*?\]',
    r'\(.*?officiel.*?\)', r'\[.*?officiel.*?\]',
    r'\(.*?clip.*?\)', r'\[.*?clip.*?\]',
    r'\(.*?video.*?\)', r'\[.*?video.*?\]',
    r'\(.*?vid\u00e9o.*?\)', r'\[.*?vid\u00e9o.*?\]',
    r'\(.*?lyrics.*?\)', r'\[.*?lyrics.*?\]',
    r'\(.*?paroles.*?\)',
    r'\(.*?audio.*?\)', r'\[.*?audio.*?\]',
    r'\(.*?HD.*?\)', r'\(.*?HQ.*?\)', r'\(.*?4K.*?\)',
    r'\(.*?MV.*?\)', r'\(.*?visualizer.*?\)',
    r'\(.*?lyric video.*?\)',
    r'\(.*?ft\..*?\)', r'\(.*?feat\..*?\)', r'\(.*?featuring.*?\)',
]

ARTIST_NOISE = [' - Topic', 'VEVO', ' Official', ' Music']


def clean_title(title):
    if not title:
        return ''
    c = title
    for pat in TITLE_NOISE:
        c = re.sub(pat, '', c, flags=re.IGNORECASE)
    # coupe apres ft./feat./prod.
    c = re.split(r'\s+(?:ft\.?|feat\.?|featuring|prod\.?)\s+', c, flags=re.IGNORECASE)[0]
    c = re.sub(r'\s+', ' ', c).strip(' -|\u00b7\u2022')
    return c


def clean_artist(artist):
    if not artist:
        return ''
    c = artist
    for noise in ARTIST_NOISE:
        c = c.replace(noise, '')
    c = re.split(r'\s+(?:ft\.?|feat\.?|featuring|x|&|,|/)\s+', c, flags=re.IGNORECASE)[0]
    return c.strip()


def split_artist_from_title(title):
    if not title:
        return title, None
    for sep in [' - ', ' \u2013 ', ' \u2014 ', ' | ']:
        if sep in title:
            parts = title.split(sep, 1)
            if len(parts) == 2:
                return parts[1].strip(), parts[0].strip()
    return title, None


def fetch_synced_lyrics(track_name, artist_name, duration_sec=None):
    clean_t = clean_title(track_name)
    clean_a = clean_artist(artist_name)

    extracted_title, extracted_artist = split_artist_from_title(clean_t)
    if extracted_artist and (not clean_a or clean_a == 'Unknown Artist'):
        clean_a = extracted_artist
        clean_t = extracted_title
    elif extracted_artist and clean_a and extracted_artist.lower() == clean_a.lower():
        clean_t = extracted_title

    log.info(f"[lyrics-fetch] cleaned: '{clean_a}' - '{clean_t}' (orig: '{artist_name}' - '{track_name}')")

    candidates = [
        (clean_t, clean_a),
        (extracted_title or clean_t, clean_a),
        (clean_t, artist_name),
        (track_name, clean_a),
    ]
    seen = set()

    for t, a in candidates:
        key = (t.lower(), a.lower() if a else '')
        if key in seen or not t:
            continue
        seen.add(key)

        # lrclib direct
        lrc = _try_lrclib(t, a, duration_sec)
        if lrc:
            log.info(f"[lyrics-fetch] Found on LRCLIB: '{a}' - '{t}'")
            return lrc

        # lrclib search (plus souple)
        lrc = _try_lrclib_search(t, a)
        if lrc:
            log.info(f"[lyrics-fetch] Found on LRCLIB search: '{a}' - '{t}'")
            return lrc

    # dernier recours: syncedlyrics
    lrc = _try_syncedlyrics(clean_t, clean_a)
    if lrc:
        log.info(f"[lyrics-fetch] Found via syncedlyrics: '{clean_a}' - '{clean_t}'")
        return lrc

    log.info(f"[lyrics-fetch] No synced lyrics found for: '{artist_name}' - '{track_name}'")
    return None


def _try_lrclib(track, artist, dur=None):
    try:
        params = {'track_name': track, 'artist_name': artist}
        if dur:
            params['duration'] = int(dur)
        resp = requests.get(f'{LRCLIB_API}/get', params=params,
                            headers={'User-Agent': UA}, timeout=10)
        if resp.status_code == 200:
            synced = resp.json().get('syncedLyrics')
            if synced and len(synced) > 20:
                return synced
    except Exception as e:
        log.debug(f"[lyrics-fetch] LRCLIB get error: {e}")
    return None


def _try_lrclib_search(track, artist):
    try:
        resp = requests.get(f'{LRCLIB_API}/search',
                            params={'q': f'{artist} {track}'},
                            headers={'User-Agent': UA}, timeout=10)
        if resp.status_code == 200:
            results = resp.json()
            if results and isinstance(results, list):
                for r in results[:5]:
                    synced = r.get('syncedLyrics')
                    if synced and len(synced) > 20:
                        return synced
    except Exception as e:
        log.debug(f"[lyrics-fetch] LRCLIB search error: {e}")
    return None


def _try_syncedlyrics(track, artist):
    # maybe cache this?
    try:
        import syncedlyrics
        lrc = syncedlyrics.search(f'{track} {artist}', synced_only=True,
                                  providers=['Lrclib', 'NetEase', 'Megalobiz'])
        if lrc and len(lrc) > 20:
            return lrc
    except Exception as e:
        log.debug(f"[lyrics-fetch] syncedlyrics error: {e}")
    return None
