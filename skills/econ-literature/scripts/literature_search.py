#!/usr/bin/env python3
"""Federated economics literature search: several sources at once, merged, deduplicated and ranked by the
journal and working-paper policy of research_search.py.

  search    --query Q [--query Q2 ...] [--from YEAR] [--to YEAR] [--field FIELD ...]
            [--sources journals,openalex,crossref,semanticscholar,arxiv,cinii,jstage] [--limit N] --output DIR
            ('journals' searches the top five, the fields' journals and NBER directly through Crossref)
  snowball  --doi DOI [--limit N] --output DIR       backward references and forward citations of one paper
  contexts  --doi DOI [--limit N] --output DIR       sentences in citing papers that cite this paper (Semantic Scholar)

Sources: OpenAlex (works, citations; set OPENALEX_API_KEY or a proxy credential when the shared quota is used),
Crossref (journal metadata), Semantic Scholar (relevance search, citation contexts; SEMANTIC_SCHOLAR_API_KEY
raises the rate limit), arXiv (econ.* preprints), CiNii Research and J-STAGE (Japanese literature).
Every raw response is saved under DIR/raw; DIR/works.json holds the merged records and DIR/ranked.md the table.
"""
import argparse
import html
import json
import math
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_search import journal_policy, publication_details, search_windows, venue_priority  # noqa: E402

USER_AGENT = 'econ-literature-search/1.0'
ALL_SOURCES = ('journals', 'openalex', 'crossref', 'semanticscholar', 'arxiv', 'cinii', 'jstage')
ARXIV_CATEGORIES = ('econ.EM', 'econ.GN', 'econ.TH', 'q-fin.EC', 'stat.ME')
# DOI prefixes of working-paper series that Crossref lists without a container title
WP_PREFIXES = {'10.3386': 'NBER Working Papers', '10.1596': 'World Bank Policy Research Working Paper',
               '10.5089': 'IMF Working Papers', '10.21033': 'Federal Reserve Bank Working Paper'}
# Japanese academic venues and discussion-paper series ranked as listed venues (tier 3)
JA_VENUES = ('経済研究', '日本経済研究', '日本労働研究雑誌', '社会保障研究', '季刊社会保障研究', 'フィナンシャル・レビュー',
             '経済分析', '金融研究', '経済学論集', '経済論叢', '国民経済雑誌', '三田学会雑誌', '経済セミナー',
             'RIETI Discussion Paper', 'RIETI Policy Discussion Paper', '日本銀行ワーキングペーパー', 'Bank of Japan Working Paper',
             'ESRI Discussion Paper', 'JILPT', '労働政策研究報告書', 'CIRJE', 'Japanese Economic Review',
             'Journal of the Japanese and International Economies', 'Japan and the World Economy', '応用経済学研究',
             '行動経済学', '医療経済研究', '社会政策', '人口学研究', '地域学研究', '都市計画論文集')
TIER_LABEL = {0: 'Top 5', 1: 'Field leader', 2: 'W1 working paper (recent)', 3: 'Listed venue / W2', 4: 'Other'}


# ---------------------------------------------------------------- HTTP

def fetch(url, raw_dir, name, headers=None, retries=2):
    """GET with saved raw response; returns (text, status). Retries once on 429/5xx."""
    request = Request(url, headers={'User-Agent': USER_AGENT, **(headers or {})})
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=40) as response:
                body = response.read().decode('utf-8', 'replace')
                status = response.status
        except HTTPError as exc:
            body, status = exc.read().decode('utf-8', 'replace'), exc.code
        except Exception as exc:  # network, TLS, protocol and URL errors are recorded per source
            body, status = str(getattr(exc, 'reason', exc)), 0
        if status in (429, 500, 502, 503) and attempt < retries:
            time.sleep(3 * (attempt + 1))
            continue
        break
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / name).write_text(json.dumps({'url': url, 'status': status, 'body': body[:2_000_000]}), encoding='utf-8')
    return body, status


def openalex_headers():
    key = os.environ.get('OPENALEX_API_KEY')
    return {'Authorization': 'Bearer ' + key} if key else {}


def s2_headers():
    key = os.environ.get('SEMANTIC_SCHOLAR_API_KEY')
    return {'x-api-key': key} if key else {}


# ---------------------------------------------------------------- normalization

def norm_title(title):
    text = unicodedata.normalize('NFKC', title or '').lower()
    return re.sub(r'[^\w]+', ' ', text).strip()


def norm_doi(doi):
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)
    return doi or None


def record(source, **fields):
    base = {'title': None, 'authors': [], 'year': None, 'venue': None, 'type': None, 'doi': None, 'url': None,
            'oa_url': None, 'cited_by': None, 'abstract': None, 'publisher': None, 'publication_dates': {},
            'ids': {}, 'sources': [source]}
    base.update({k: v for k, v in fields.items() if v not in (None, '', [], {})})
    base['doi'] = norm_doi(base.get('doi'))
    for key in ('title', 'venue', 'abstract'):
        if isinstance(base.get(key), str):
            base[key] = ' '.join(re.sub(r'<[^>]+>', ' ', html.unescape(html.unescape(base[key]))).split()) or None
    return base


def openalex_abstract(index):
    if not isinstance(index, dict):
        return None
    words = sorted((pos, word) for word, positions in index.items() for pos in positions)
    return ' '.join(word for _, word in words) or None


# ---------------------------------------------------------------- sources

def search_openalex(query, years, limit, raw):
    params = {'search': query, 'per-page': min(limit, 100),
              'select': 'id,doi,title,publication_year,publication_date,type,cited_by_count,primary_location,'
                        'authorships,open_access,abstract_inverted_index'}
    if years:
        params['filter'] = f'publication_year:{years[0]}-{years[1]}'
    body, status = fetch('https://api.openalex.org/works?' + urlencode(params), raw, f'openalex-{slug(query)}.json',
                         openalex_headers())
    if status != 200:
        return [], f'OpenAlex HTTP {status}: {body[:160]}'
    out = []
    for w in json.loads(body).get('results', []):
        source = ((w.get('primary_location') or {}).get('source') or {})
        out.append(record('openalex', title=w.get('title'), year=w.get('publication_year'),
                          venue=source.get('display_name'), type=w.get('type'), doi=w.get('doi'),
                          url=w.get('id'), oa_url=(w.get('open_access') or {}).get('oa_url'),
                          cited_by=w.get('cited_by_count'), abstract=openalex_abstract(w.get('abstract_inverted_index')),
                          authors=[(a.get('author') or {}).get('display_name') for a in w.get('authorships', [])][:12],
                          publication_dates={'published': w.get('publication_date')} if w.get('publication_date') else {},
                          ids={'openalex': w.get('id')}))
    return out, None


def search_crossref(query, years, limit, raw):
    params = {'query.bibliographic': query, 'rows': min(limit, 100),
              'select': 'DOI,title,container-title,issued,published-print,published-online,type,author,'
                        'is-referenced-by-count,publisher,abstract,URL'}
    if years:
        params['filter'] = f'from-pub-date:{years[0]}-01-01,until-pub-date:{years[1]}-12-31'
    body, status = fetch('https://api.crossref.org/works?' + urlencode(params), raw, f'crossref-{slug(query)}.json')
    if status != 200:
        return [], f'Crossref HTTP {status}: {body[:160]}'
    return [crossref_record(w) for w in json.loads(body).get('message', {}).get('items', [])], None


def crossref_record(w):
    if True:
        def date_of(key):
            parts = ((w.get(key) or {}).get('date-parts') or [[None]])[0]
            return '-'.join(f'{p:02d}' if i else str(p) for i, p in enumerate(parts) if p) or None
        dates = {k: v for k, v in {'issued': date_of('issued'), 'published_print': date_of('published-print'),
                                   'published_online': date_of('published-online')}.items() if v}
        issued = dates.get('issued')
        doi = w.get('DOI') or ''
        series = WP_PREFIXES.get(doi.split('/')[0])
        return record('crossref', title=(w.get('title') or [None])[0], year=int(issued[:4]) if issued else None,
                      venue=(w.get('container-title') or [None])[0] or series,
                      type='working-paper' if series else w.get('type'), doi=doi,
                      url=w.get('URL'), cited_by=w.get('is-referenced-by-count'), publisher=w.get('publisher'),
                      abstract=re.sub(r'<[^>]+>', ' ', w.get('abstract') or '').strip() or None,
                      authors=[' '.join(x for x in (a.get('given'), a.get('family')) if x) for a in w.get('author', [])][:12],
                      publication_dates=dates, ids={'crossref': w.get('DOI')})


def search_crossref_targeted(query, years, limit, raw, fields=()):
    """Crossref restricted to the leading journals of the plan (top five and the fields' journals) and to the
    NBER DOI prefix, so that leading publications surface even when general relevance search ranks them low."""
    plan = journal_policy(list(fields))
    venues = list(plan['groups']['E0'])
    for field in plan['fields'].values():
        venues += [v for v in field.get('journals', []) if v not in venues]
    out, errors = [], []
    for venue in venues:
        params = {'query.bibliographic': query, 'query.container-title': plan['venues'][venue]['name'],
                  'rows': max(5, min(limit, 10)),
                  'select': 'DOI,title,container-title,issued,published-print,published-online,type,author,'
                            'is-referenced-by-count,publisher,URL'}
        if years:
            params['filter'] = f'from-pub-date:{years[0]}-01-01,until-pub-date:{years[1]}-12-31,type:journal-article'
        else:
            params['filter'] = 'type:journal-article'
        body, status = fetch('https://api.crossref.org/works?' + urlencode(params), raw, f'crossref-{venue}-{slug(query)}.json')
        if status != 200:
            errors.append(f'{venue} HTTP {status}')
            continue
        names = {norm_title(plan['venues'][venue]['name'])} | {norm_title(a) for a in plan['venues'][venue]['aliases']}
        for w in json.loads(body).get('message', {}).get('items', []):
            if norm_title((w.get('container-title') or [''])[0]) in names:
                out.append(dict(crossref_record(w), sources=['journals']))
        time.sleep(0.2)
    nber = {'query.bibliographic': query, 'rows': min(limit, 20), 'filter': 'prefix:10.3386' +
            (f',from-pub-date:{years[0]}-01-01,until-pub-date:{years[1]}-12-31' if years else '')}
    body, status = fetch('https://api.crossref.org/works?' + urlencode(nber), raw, f'crossref-nber-{slug(query)}.json')
    if status == 200:
        out += [dict(crossref_record(w), sources=['journals']) for w in json.loads(body).get('message', {}).get('items', [])]
    else:
        errors.append(f'NBER HTTP {status}')
    return out, ('; '.join(errors) if errors else None)


def search_semanticscholar(query, years, limit, raw):
    params = {'query': query, 'limit': min(limit, 100),
              'fields': 'title,year,venue,citationCount,externalIds,authors,openAccessPdf,publicationTypes,abstract,url'}
    if years:
        params['year'] = f'{years[0]}-{years[1]}'
    body, status = fetch('https://api.semanticscholar.org/graph/v1/paper/search?' + urlencode(params), raw,
                         f'semanticscholar-{slug(query)}.json', s2_headers())
    if status != 200:
        return [], f'Semantic Scholar HTTP {status}: {body[:160]}'
    out = []
    for w in json.loads(body).get('data', []):
        ext = w.get('externalIds') or {}
        out.append(record('semanticscholar', title=w.get('title'), year=w.get('year'), venue=w.get('venue') or None,
                          type='journal-article' if 'JournalArticle' in (w.get('publicationTypes') or []) else None,
                          doi=ext.get('DOI'), url=w.get('url'), oa_url=(w.get('openAccessPdf') or {}).get('url'),
                          cited_by=w.get('citationCount'), abstract=w.get('abstract'),
                          authors=[a.get('name') for a in w.get('authors', [])][:12],
                          ids={'semanticscholar': w.get('paperId'), 'arxiv': ext.get('ArXiv')}))
    return out, None


def search_arxiv(query, years, limit, raw):
    cats = ' OR '.join(f'cat:{c}' for c in ARXIV_CATEGORIES)
    terms = ' AND '.join(f'all:{t}' for t in query.split())
    url = 'https://export.arxiv.org/api/query?' + urlencode({'search_query': f'({terms}) AND ({cats})',
                                                             'max_results': min(limit, 100), 'sortBy': 'relevance'})
    body, status = fetch(url, raw, f'arxiv-{slug(query)}.xml')
    if status != 200:
        return [], f'arXiv HTTP {status}'
    ns = {'a': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
    out = []
    for e in ET.fromstring(body).findall('a:entry', ns):
        year = int(e.findtext('a:published', '', ns)[:4] or 0) or None
        if years and year and not years[0] <= year <= years[1]:
            continue
        doi = e.findtext('arxiv:doi', None, ns)
        out.append(record('arxiv', title=' '.join(e.findtext('a:title', '', ns).split()), year=year,
                          venue='arXiv', type='preprint', doi=doi, url=e.findtext('a:id', None, ns),
                          oa_url=(e.findtext('a:id', '', ns) or '').replace('/abs/', '/pdf/') or None,
                          abstract=' '.join(e.findtext('a:summary', '', ns).split()),
                          authors=[a.findtext('a:name', '', ns) for a in e.findall('a:author', ns)][:12],
                          publication_dates={'posted': e.findtext('a:published', '', ns)[:10]},
                          ids={'arxiv': e.findtext('a:id', None, ns)}))
    return out, None


def search_cinii(query, years, limit, raw):
    params = {'q': query, 'count': min(limit, 200), 'format': 'json'}
    if years:
        params.update({'from': str(years[0]), 'until': str(years[1])})
    body, status = fetch('https://cir.nii.ac.jp/opensearch/articles?' + urlencode(params), raw, f'cinii-{slug(query)}.json')
    if status != 200:
        return [], f'CiNii HTTP {status}'
    out = []
    for w in json.loads(body).get('items', []):
        doi = next((i.get('@value') for i in w.get('dc:identifier', []) if isinstance(i, dict) and i.get('@type') == 'cir:DOI'), None)
        date_value = w.get('prism:publicationDate')
        out.append(record('cinii', title=w.get('title'), year=int(date_value[:4]) if date_value and date_value[:4].isdigit() else None,
                          venue=w.get('prism:publicationName'), type=(w.get('dc:type') or '').lower() or None, doi=doi,
                          url=(w.get('link') or {}).get('@id'), publisher=w.get('dc:publisher'),
                          authors=w.get('dc:creator', [])[:12], abstract=w.get('description'),
                          ids={'cinii': w.get('@id')}))
    return out, None


def search_jstage(query, years, limit, raw):
    params = {'service': 3, 'article': query, 'count': min(limit, 1000)}
    if years:
        params.update({'pubyearfrom': years[0], 'pubyearto': years[1]})
    body, status = fetch('https://api.jstage.jst.go.jp/searchapi/do?' + urlencode(params), raw, f'jstage-{slug(query)}.xml')
    if status != 200:
        return [], f'J-STAGE HTTP {status}'
    ns = {'a': 'http://www.w3.org/2005/Atom', 'prism': 'http://prismstandard.org/namespaces/basic/2.0/'}
    out = []
    for e in ET.fromstring(body).findall('a:entry', ns):
        def pick(tag):
            node = e.find(f'a:{tag}', ns)
            return None if node is None else ((node.findtext('a:ja', '', ns) or node.findtext('a:en', '', ns)).strip() or None)
        year = e.findtext('a:pubyear', None, ns)
        authors = [n.text.strip() for n in e.findall('a:author/a:ja/a:name', ns) if n.text] or \
                  [n.text.strip() for n in e.findall('a:author/a:en/a:name', ns) if n.text]
        out.append(record('jstage', title=pick('article_title'), year=int(year) if year and year.isdigit() else None,
                          venue=pick('material_title'), type='journal-article',
                          doi=e.findtext('prism:doi', None, ns), url=e.findtext('a:id', None, ns), authors=authors[:12],
                          ids={'jstage': e.findtext('a:id', None, ns)}))
    return out, None


SEARCHERS = {'openalex': search_openalex, 'crossref': search_crossref, 'journals': search_crossref_targeted, 'semanticscholar': search_semanticscholar,
             'arxiv': search_arxiv, 'cinii': search_cinii, 'jstage': search_jstage}


# ---------------------------------------------------------------- merge and rank

def slug(text):
    return re.sub(r'[^\w]+', '-', unicodedata.normalize('NFKC', text))[:40].strip('-') or 'q'


def merge(records):
    merged, index = [], {}
    for r in records:
        keys = [k for k in (('doi', r['doi']) if r['doi'] else None,
                            ('title', norm_title(r['title']), r['year']) if r['title'] else None) if k]
        found = next((index[k] for k in keys if k in index), None)
        if found is None:
            merged.append(dict(r))
            found = len(merged) - 1
        else:
            m = merged[found]
            for key, value in r.items():
                if key == 'sources':
                    m['sources'] = sorted(set(m['sources']) | set(value))
                elif key == 'ids':
                    m['ids'] = {**value, **m['ids']}
                elif key == 'cited_by':
                    m['cited_by'] = max(x for x in (m.get('cited_by'), value) if x is not None) if value is not None else m.get('cited_by')
                elif key == 'publication_dates':
                    m['publication_dates'] = {**value, **m['publication_dates']}
                elif m.get(key) in (None, '', []) and value not in (None, '', []):
                    m[key] = value
        for k in keys:
            index[k] = found
    return merged


STOPWORDS = {'a', 'an', 'and', 'the', 'of', 'in', 'on', 'for', 'to', 'with', 'by', 'from', 'at', 'as', 'or',
             'is', 'are', 'its', 'their', 'evidence', 'effect', 'effects', 'impact', 'analysis', 'study'}


def tokens(text):
    words = norm_title(text).split()
    out = set()
    for w in words:
        if w in STOPWORDS or len(w) < 2:
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith('s') else w)   # light plural folding
    return out


def relevance(r, queries):
    """Share of query words found as whole words, weighted toward the title, plus a bonus for the exact phrase.
    Japanese queries (no spaces) fall back to substring matching of each space-separated term."""
    title, body = r.get('title') or '', (r.get('title') or '') + ' ' + (r.get('abstract') or '')
    best = 0.0
    for q in queries:
        if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', q):
            terms = [t for t in q.split() if t]
            score = sum(t in body for t in terms) / len(terms) if terms else 0
        else:
            terms = tokens(q)
            if not terms:
                continue
            title_hits = len(terms & tokens(title)) / len(terms)
            body_hits = len(terms & tokens(body)) / len(terms)
            score = 0.5 * body_hits + 0.5 * title_hits + (0.2 if norm_title(q) in norm_title(title) else 0)
        best = max(best, min(score, 1.0))
    return round(best, 3)


def rank(records, queries, fields):
    plan = {**search_windows(None), **journal_policy(fields or [])}
    for r in records:
        meta = {'journal': r.get('venue'), 'container_title': r.get('venue'), 'type': r.get('type'),
                'publisher': r.get('publisher') or '', 'year': r.get('year'),
                'publication_dates': {k: v for k, v in (r.get('publication_dates') or {}).items()
                                      if isinstance(v, str) and re.fullmatch(r'\d{4}(-\d{2}){0,2}', v)}}
        try:
            publication = publication_details(meta)
            priority = venue_priority(meta, plan, publication)
            r['tier'], r['window'], r['status'] = priority['tier'], publication['window'], publication['status']
        except (ValueError, KeyError, StopIteration):
            r['tier'], r['window'], r['status'] = 4, None, None
        if r['tier'] == 4 and any(v.lower() in (r.get('venue') or '').lower() for v in JA_VENUES):
            r['tier'] = 3
        r['relevance'] = relevance(r, queries)
    band = lambda x: 2 if x >= 0.8 else 1 if x >= 0.5 else 0
    records.sort(key=lambda r: (-band(r['relevance']), r['tier'], -r['relevance'],
                                -math.log1p(r.get('cited_by') or 0), -(r.get('year') or 0)))
    return records


def table(records, limit):
    lines = ['| # | Tier | Year | Title | Authors | Venue | Cited | Rel. | Sources | Link |',
             '|---:|---|---:|---|---|---|---:|---:|---|---|']
    for i, r in enumerate(records[:limit], 1):
        link = f'https://doi.org/{r["doi"]}' if r.get('doi') else (r.get('url') or '')
        authors = ', '.join(a for a in r.get('authors', [])[:3] if a) + (' et al.' if len(r.get('authors', [])) > 3 else '')
        cell = lambda s: (s or '').replace('|', '/').replace('\n', ' ')
        lines.append(f'| {i} | {TIER_LABEL.get(r.get("tier"), "")} | {r.get("year") or ""} | {cell(r.get("title"))} | '
                     f'{cell(authors)} | {cell(r.get("venue"))} | {r.get("cited_by") if r.get("cited_by") is not None else ""} | '
                     f'{r.get("relevance", "")} | {",".join(r["sources"])} | {link} |')
    return '\n'.join(lines) + '\n'


def save(output, records, notes, limit, header):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'works.json').write_text(json.dumps({'notes': notes, 'works': records}, ensure_ascii=False, indent=1),
                                       encoding='utf-8')
    md = header + ('\n'.join(f'- {n}' for n in notes) + '\n\n' if notes else '\n') + table(records, limit)
    (output / 'ranked.md').write_text(md, encoding='utf-8')
    print(md)


# ---------------------------------------------------------------- commands

def cmd_search(args):
    out, raw = Path(args.output), Path(args.output) / 'raw'
    years = (args.year_from or 1900, args.year_to or 2100) if (args.year_from or args.year_to) else None
    sources = [s.strip() for s in args.sources.split(',') if s.strip()]
    records, notes = [], []
    for source in sources:
        for query in args.query:
            found, error = (search_crossref_targeted(query, years, args.per_source, raw, args.field)
                            if source == 'journals' else SEARCHERS[source](query, years, args.per_source, raw))
            if error:
                notes.append(f'{source} / "{query}": {error}')
            records += found
            time.sleep(0.3)
    merged = rank(merge(records), args.query, args.field)
    counts = {s: sum(s in r['sources'] for r in merged) for s in sources}
    notes.insert(0, 'records by source: ' + ', '.join(f'{k} {v}' for k, v in counts.items()) +
                 f'; merged {len(merged)} from {len(records)}')
    save(out, merged, notes, args.limit, f'# Literature search: {"; ".join(args.query)}\n\n')


def cmd_snowball(args):
    """Backward references: OpenAlex, then Crossref reference lists. Forward citations: OpenAlex, then Semantic
    Scholar. Each direction records which source answered and why another failed."""
    out, raw = Path(args.output), Path(args.output) / 'raw'
    doi = norm_doi(args.doi)
    records, notes = [], []
    select = 'id,doi,title,publication_year,type,cited_by_count,primary_location,authorships'
    body, status = fetch(f'https://api.openalex.org/works/doi:{quote(doi, safe="/")}?select=id,title,referenced_works',
                         raw, 'openalex-root.json', openalex_headers())
    root = json.loads(body) if status == 200 else None
    backward = forward = None
    if root:
        refs = [w.rsplit('/', 1)[1] for w in root.get('referenced_works', [])][:args.limit]
        found = []
        for i in range(0, len(refs), 50):
            b, st = fetch('https://api.openalex.org/works?' + urlencode({'filter': 'openalex:' + '|'.join(refs[i:i + 50]),
                          'per-page': 50, 'select': select}), raw, f'openalex-backward-{i}.json', openalex_headers())
            if st != 200:
                notes.append(f'OpenAlex backward HTTP {st}')
                found = None
                break
            found += openalex_records(b)
        backward = found
        b, st = fetch('https://api.openalex.org/works?' + urlencode({'filter': 'cites:' + root['id'].rsplit('/', 1)[1],
                      'per-page': min(args.limit, 200), 'sort': 'cited_by_count:desc', 'select': select}),
                      raw, 'openalex-forward.json', openalex_headers())
        forward = openalex_records(b) if st == 200 else None
        if st != 200:
            notes.append(f'OpenAlex forward HTTP {st}')
    else:
        notes.append(f'OpenAlex root HTTP {status}')
    if backward is None:
        b, st = fetch(f'https://api.crossref.org/works/{quote(doi, safe="/")}', raw, 'crossref-references.json')
        if st == 200:
            refs = json.loads(b).get('message', {}).get('reference', [])
            resolved = crossref_by_doi([r['DOI'] for r in refs if r.get('DOI')][:args.limit], raw)
            backward = [resolved[norm_doi(r['DOI'])] if r.get('DOI') and norm_doi(r['DOI']) in resolved else record('crossref', title=r.get('article-title') or r.get('unstructured'), doi=r.get('DOI'),
                               venue=r.get('journal-title'), year=int(r['year'][:4]) if str(r.get('year', ''))[:4].isdigit() else None,
                               authors=[r['author']] if r.get('author') else [])
                        for r in refs][:args.limit]
            notes.append(f'backward from Crossref reference list ({len(refs)} references)')
        else:
            notes.append(f'Crossref references HTTP {st}')
    if forward is None:
        b, st = fetch(f'https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe="/")}/citations?' +
                      urlencode({'limit': min(args.limit, 1000), 'fields': 'title,year,venue,citationCount,externalIds,authors'}),
                      raw, 's2-forward.json', s2_headers())
        if st == 200:
            forward = []
            for item in json.loads(b).get('data', []):
                w = item.get('citingPaper') or {}
                forward.append(record('semanticscholar', title=w.get('title'), year=w.get('year'), venue=w.get('venue'),
                                      doi=(w.get('externalIds') or {}).get('DOI'), cited_by=w.get('citationCount'),
                                      authors=[a.get('name') for a in w.get('authors', [])][:12]))
            notes.append('forward from Semantic Scholar')
        else:
            notes.append(f'Semantic Scholar forward HTTP {st}: forward citations need OPENALEX_API_KEY or '
                         'SEMANTIC_SCHOLAR_API_KEY when the shared quota is used up')
    records = [dict(r, direction='backward') for r in backward or []] + [dict(r, direction='forward') for r in forward or []]
    merged = rank(merge(records), [], args.field)
    notes.insert(0, f'backward {len(backward or [])}, forward {len(forward or [])}')
    save(out, merged, notes, args.limit, f'# Snowball: {doi}\n\n')


def crossref_by_doi(dois, raw):
    """Metadata for many DOIs through Crossref's doi filter, 40 per request."""
    found = {}
    for i in range(0, len(dois), 40):
        chunk = dois[i:i + 40]
        b, st = fetch('https://api.crossref.org/works?' + urlencode({'filter': ','.join('doi:' + d for d in chunk),
                      'rows': len(chunk)}), raw, f'crossref-doi-batch-{i}.json')
        if st == 200:
            for w in json.loads(b).get('message', {}).get('items', []):
                r = crossref_record(w)
                found[r['doi']] = r
    return found


def openalex_records(body):
    out = []
    for w in json.loads(body).get('results', []):
        source = ((w.get('primary_location') or {}).get('source') or {})
        out.append(record('openalex', title=w.get('title'), year=w.get('publication_year'), venue=source.get('display_name'),
                          type=w.get('type'), doi=w.get('doi'), url=w.get('id'), cited_by=w.get('cited_by_count'),
                          authors=[(a.get('author') or {}).get('display_name') for a in w.get('authorships', [])][:12],
                          ids={'openalex': w.get('id')}))
    return out


def cmd_contexts(args):
    out, raw = Path(args.output), Path(args.output) / 'raw'
    doi = norm_doi(args.doi)
    body, status = fetch(f'https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe="/")}/citations?' +
                         urlencode({'limit': min(args.limit, 1000), 'fields': 'contexts,intents,title,year,venue,externalIds'}),
                         raw, 's2-contexts.json', s2_headers())
    if status != 200:
        raise SystemExit(f'Semantic Scholar HTTP {status}: {body[:200]}')
    lines = [f'# Citation contexts: {doi}\n']
    rows = []
    for item in json.loads(body).get('data', []):
        paper = item.get('citingPaper') or {}
        for context in item.get('contexts') or []:
            rows.append({'year': paper.get('year'), 'title': paper.get('title'), 'venue': paper.get('venue'),
                         'intents': item.get('intents'), 'context': context})
            lines.append(f'- ({paper.get("year")}) {paper.get("title")} [{", ".join(item.get("intents") or [])}]: {context}')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'contexts.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'contexts.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:60]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('search')
    s.add_argument('--query', action='append', required=True)
    s.add_argument('--from', dest='year_from', type=int)
    s.add_argument('--to', dest='year_to', type=int)
    s.add_argument('--field', action='append', default=[])
    s.add_argument('--sources', default=','.join(ALL_SOURCES))
    s.add_argument('--per-source', type=int, default=25)
    s.add_argument('--limit', type=int, default=40)
    s.add_argument('--output', required=True)
    b = sub.add_parser('snowball')
    b.add_argument('--doi', required=True)
    b.add_argument('--field', action='append', default=[])
    b.add_argument('--limit', type=int, default=100)
    b.add_argument('--output', required=True)
    c = sub.add_parser('contexts')
    c.add_argument('--doi', required=True)
    c.add_argument('--limit', type=int, default=200)
    c.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    {'search': cmd_search, 'snowball': cmd_snowball, 'contexts': cmd_contexts}[args.command](args)


if __name__ == '__main__':
    main()
