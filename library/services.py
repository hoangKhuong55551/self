"""
Tra cứu thông tin sách từ Open Library (miễn phí, không cần API key).
"""
import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://openlibrary.org/search.json'
COVER_URL = 'https://covers.openlibrary.org/b/id/{}-L.jpg'
FIELDS = 'key,title,author_name,number_of_pages_median,cover_i,first_publish_year,subject'


def search_books(query, limit=6):
    """Trả về list dict: title, creator, pages, cover_url, year, genre. Lỗi mạng trả về []."""
    query = (query or '').strip()
    if len(query) < 2:
        return []

    cache_key = f'openlibrary:{query.lower()}:{limit}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"{SEARCH_URL}?{urlencode({'q': query, 'limit': limit, 'fields': FIELDS})}"
    request = Request(url, headers={'User-Agent': 'LifeOS/1.0 (personal book tracker)'})
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.load(response)
    except Exception as exc:  # mạng chập chờn không được làm hỏng trang
        logger.warning('Open Library lookup failed: %s', exc)
        return []

    results = []
    for doc in payload.get('docs', []):
        subjects = doc.get('subject') or []
        results.append({
            'title': doc.get('title', ''),
            'creator': ', '.join((doc.get('author_name') or [])[:2]),
            'pages': doc.get('number_of_pages_median') or 0,
            'cover_url': COVER_URL.format(doc['cover_i']) if doc.get('cover_i') else '',
            'year': doc.get('first_publish_year'),
            'genre': subjects[0][:100] if subjects else '',
        })

    cache.set(cache_key, results, 60 * 60 * 24)
    return results
