"""Bounded citation discovery and local source-corpus analysis.

The caller supplies existing source I/O owners; this module creates no database.
"""
import hashlib
import copy
import json
import math
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_sources import read_record

DIMENSIONS = ('mechanism','estimand','identification','measurement','population')
OPENALEX = 'https://api.openalex.org/works'
EXTRACTOR_VERSION = 'canonical-page-text-v1'
PUBLICATION_FIELDS = ('doi', 'journal', 'container_title', 'container_titles', 'series', 'publisher', 'type',
                      'year', 'publication_status', 'publication_dates', 'volume', 'issue', 'version')
JOURNAL_POLICY = Path(__file__).resolve().parents[1] / 'references' / 'journal-priority.json'
if not JOURNAL_POLICY.is_file():
    JOURNAL_POLICY = Path(__file__).resolve().with_name('journal-priority.json')


def name_key(value):
    value = unicodedata.normalize('NFKC', value).casefold().replace('&', ' and ')
    return re.sub(r'[^\w]+', '', re.sub(r'^the\s+', '', value))


def doi_key(value):
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', str(value).strip(), flags=re.I).casefold()


def execution_date(as_of=None):
    if as_of is None:
        return date.today()
    if not isinstance(as_of, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', as_of):
        raise ValueError('as_of must be an ISO calendar date YYYY-MM-DD')
    return date.fromisoformat(as_of)


def search_windows(as_of=None):
    current = execution_date(as_of)
    if current.year < 11:
        raise ValueError('search execution year must be at least 11')
    year = current.year
    return {'as_of': current.isoformat(), 'year': year, 'windows': [
        {'id': 'R0', 'start_year': year-2, 'end_year': year},
        {'id': 'R1', 'start_year': year-5, 'end_year': year-3},
        {'id': 'R2', 'start_year': year-9, 'end_year': year-6},
        {'id': 'R3', 'start_year': None, 'end_year': year-10}]}


def journal_policy(fields=None, theme=None):
    """Return the requested field slice from the single stable policy owner."""
    raw = JOURNAL_POLICY.read_bytes()
    policy = json.loads(raw)
    if fields is None:
        fields = []
    if not isinstance(fields, list) or any(not isinstance(x, str) or not x.strip() for x in fields):
        raise ValueError('fields must be a list of field names or aliases')
    lookup = {name_key(alias): key for key, value in policy['fields'].items()
              for alias in [key, value['name'], *value['aliases']]}
    selected = []
    for field in fields:
        if name_key(field) not in lookup:
            raise ValueError('unknown literature field: ' + field)
        key = lookup[name_key(field)]
        if key not in selected:
            selected.append(key)
    selected_theme = None
    if theme is not None:
        matches = [key for key, row in policy['themes'].items() if name_key(theme) in
                   {name_key(key), name_key(row['name'])}]
        if len(matches) != 1:
            raise ValueError('unknown crime research theme: ' + str(theme))
        selected_theme = {'id': matches[0], **policy['themes'][matches[0]]}
        if 'crime' not in selected:
            selected.append('crime')
        for field in selected_theme.get('fields', []):
            if field not in selected:
                selected.append(field)
    groups = ['C0', 'C1', 'C2'] if 'crime' in selected else ['E0']
    ids = {key for group in groups for key in policy['groups'][group]}
    ids.update(key for field in selected for key in policy['fields'][field].get('journals', []))
    if selected_theme:
        ids.update(selected_theme['journals'])
    return {'policy_id': policy['policy_id'], 'policy_sha256': hashlib.sha256(raw).hexdigest(),
            'ordering_authority': policy['ordering_authority'], 'ranking_sources': policy['ranking_sources'],
            'fields': {key: policy['fields'][key] for key in selected},
            'field_catalog': {key: row['name'] for key, row in policy['fields'].items()} if not selected else {},
            'groups': {key: policy['groups'][key] for key in groups}, 'theme': selected_theme,
            'venues': {key: row for key, row in policy['venues'].items() if key in ids},
            'working_papers': policy['working_papers'], 'other_official_wp': policy['other_official_wp'],
            'discovery_platforms': policy['discovery_platforms'], 'recent_wp_windows': policy['recent_wp_windows']}


def search_plan(fields=None, as_of=None, theme=None):
    plan = {**search_windows(as_of), **journal_policy(fields, theme)}
    plan['search_order'] = ['R0: E0/C0 and field leaders, W1 and relevant W2',
                            'R1', 'R2', 'R3: foundations and backward/forward citations']
    for window in plan['windows']:
        until = plan['as_of'] if window['id'] == 'R0' else str(window['end_year']) + '-12-31'
        filters = {'until-pub-date': until}
        if window['start_year'] is not None:
            filters['from-pub-date'] = str(window['start_year']) + '-01-01'
        window['crossref_filters'] = filters
    return plan


def publication_details(metadata, as_of=None):
    """Keep reported dates separate; deposited/indexed dates never date a manuscript."""
    current = execution_date(as_of)
    dates = metadata.get('publication_dates', {})
    if not isinstance(dates, dict):
        raise ValueError('publication_dates must be an object')
    dated = {}
    for key, value in dates.items():
        if value is None:
            continue
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}(?:-\d{2}){0,2}', value):
            raise ValueError('publication dates must retain ISO year, month or day precision')
        pieces = list(map(int, value.split('-')))
        dated[key] = date(*(pieces + [1] * (3-len(pieces))))
    status = None if metadata.get('publication_status_inferred') else metadata.get('publication_status')
    if status not in {None, 'published', 'forthcoming', 'working_paper', 'unreported'}:
        raise ValueError('publication_status must be published, forthcoming, working_paper or unreported')
    kind = metadata.get('type')
    if status in (None, 'unreported'):
        if kind in {'posted-content', 'working-paper', 'working_paper', 'preprint'}:
            status = 'working_paper'
        elif kind in {'journal-article', 'article-journal', 'article'}:
            released = [dated[k] for k in ('published_online', 'published_print', 'published', 'issued') if k in dated]
            status = ('published' if any(d <= current for d in released) else
                      'forthcoming' if released or 'accepted' in dated else 'unreported')
        else:
            status = 'forthcoming' if 'accepted' in dated else 'unreported'
    keys = (('published_online', 'published_print', 'published', 'issued')
            if status in {'published', 'forthcoming'} else ('latest_revision', 'revised', 'posted', 'wp_first_release', 'first_release', 'issued'))
    available = [(key, dated[key]) for key in keys if key in dated and dated[key] <= current]
    if not available and status == 'forthcoming' and 'accepted' in dated and dated['accepted'] <= current:
        available = [('accepted', dated['accepted'])]
    # Formal publication uses its first public date; WP selection uses the latest reported revision.
    chosen = (min(available, key=lambda x: x[1]) if status == 'published' else
              max(available, key=lambda x: x[1])) if available else None
    year = chosen[1].year if chosen else metadata.get('year')
    if year is not None and (type(year) is not int or not 1 <= year <= 9999):
        raise ValueError('publication year must be an integer calendar year')
    window = None
    if year is not None and year <= current.year:
        window = next(w['id'] for w in search_windows(current.isoformat())['windows']
                      if (w['start_year'] is None or year >= w['start_year']) and year <= w['end_year'])
    formal = next((dates[k] for k in ('published_print', 'published', 'issued', 'published_online') if k in dates), None)
    first = next((dates[k] for k in ('wp_first_release', 'first_release', 'posted') if k in dates), None)
    manuscript = next((dates[k] for k in ('latest_revision', 'revised', 'posted', 'published_online', 'published', 'issued')
                       if k in dated and dated[k] <= current), None)
    return {'status': status, 'dates': dates, 'selection_date': dates[chosen[0]] if chosen else None,
            'selection_date_field': chosen[0] if chosen else 'year' if year is not None else None,
            'selection_year': year, 'window': window, 'first_release_date': first,
            'latest_manuscript_date': manuscript,
            'formal_publication_year': int(formal[:4]) if formal and status in {'published', 'forthcoming'} else None,
            'volume': metadata.get('volume'), 'issue': metadata.get('issue')}


def venue_priority(metadata, plan, publication):
    aliases = {name_key(alias): key for key, row in plan['venues'].items()
               for alias in [row['name'], *row['aliases']]}
    names = [metadata[k] for k in ('journal', 'container_title', 'series') if isinstance(metadata.get(k), str)]
    titles = metadata.get('container_titles', [])
    if not isinstance(titles, list) or any(not isinstance(value, str) for value in titles):
        raise ValueError('container_titles must be a list of names')
    names.extend(titles)
    venue_ids = {aliases[name_key(name)] for name in names if name_key(name) in aliases}
    memberships = []
    for field, row in plan['fields'].items():
        for rank, key in enumerate(row.get('journals', []), 1):
            if key in venue_ids:
                memberships.append({'field': field, 'rank': rank, 'venue_id': key,
                                    'leading': key in row.get('leading_journals', [])})
    groups = [{'group': group, 'rank': order.index(key)+1, 'venue_id': key}
              for group, order in plan['groups'].items() for key in venue_ids if key in order]
    leading = any(row['leading'] for row in memberships) or any(
        key in field.get('leading_journals', []) for field in plan['fields'].values() for key in venue_ids)
    series_names = names + ([metadata.get('publisher', '')] if publication['status'] == 'working_paper' else [])
    series = next((row for row in plan['working_papers'] if any(name_key(name) in
                  {name_key(row['name']), *(name_key(x) for x in row['aliases'])} for name in series_names)), None)
    official = metadata.get('official_wp')
    if series is None and official is not None:
        if (not isinstance(official, dict) or not set(plan['other_official_wp']['requires']) <= set(official)
                or official.get('institution_kind') not in plan['other_official_wp']['institution_kinds']
                or any(not isinstance(official[k], str) or not official[k].strip() for k in plan['other_official_wp']['requires'])
                or not official['official_url'].startswith('https://')):
            raise ValueError('official_wp requires institution_kind, series, official_url and source basis')
        series = {'name': official['series'], 'tier': 'W2', 'rank': 5, 'url': official['official_url']}
    formal = publication['status'] in {'published', 'forthcoming'}
    top = [row for row in groups if row['group'] in {'E0', 'C0'}]
    tier = 4
    if formal and top:
        tier = 0
    elif formal and leading:
        tier = 1
    elif publication['status'] == 'working_paper' and series:
        tier = 2 if series['tier'] == 'W1' and publication['window'] in plan['recent_wp_windows'] else 3
    elif formal and (memberships or groups):
        tier = 3
    theme = plan.get('theme')
    theme_ranks = [theme['journals'].index(key)+1 for key in venue_ids if theme and key in theme['journals']]
    ranks = [row['rank'] for row in (top or memberships or groups)]
    group_order = min((list(plan['groups']).index(row['group']) for row in groups), default=0)
    if series and not formal:
        ranks = [series['rank']]
    return {'tier': tier, 'venue_ids': sorted(venue_ids), 'field_ranks': memberships, 'groups': groups,
            'venue_rank': min(ranks) if ranks else None,
            'group_order': group_order, 'theme_rank': min(theme_ranks) if theme_ranks else None,
            'working_paper': series, 'reported_venue': names[0] if names else None}


def rank_studies(record, specification, as_of=None, limit=20):
    """Rank the existing record; direct-match judgments require inspected original ranges."""
    if (not isinstance(specification, dict) or set(specification) - {'fields', 'theme', 'direct_only', 'matches', 'question'}
            or type(limit) is not int or not 1 <= limit <= 1000
            or type(specification.get('direct_only', False)) is not bool):
        raise ValueError('ranking requires fields, optional theme/question/direct_only/matches and limit 1..1000')
    plan = search_plan(specification.get('fields', []), as_of, specification.get('theme'))
    if not plan['fields']:
        raise ValueError('select at least one literature field for ranking')
    docs = record.get('documents', [])
    documents = {row['id']: row for row in docs}
    works = record.get('works', [record['work']] if 'work' in record else [])
    candidates = [(row['id'], row.get('metadata', {}), row) for row in docs]
    if not docs:
        candidates = [(str(row.get('doi') or row.get('id') or 'work:' + str(i+1)), row, {}) for i, row in enumerate(works)]
    if not candidates:
        raise ValueError('ranking requires documents or bibliographic works in the source record')
    matches = specification.get('matches', {})
    if not isinstance(matches, dict) or set(matches) - {row[0] for row in candidates}:
        raise ValueError('matches must be keyed by an existing document ID or work DOI/ID')
    ranked = []
    for ident, metadata, doc in candidates:
        match = copy.deepcopy(matches.get(ident, {'status': 'unassessed'}))
        if (not isinstance(match, dict) or match.get('status') not in {'direct', 'related', 'excluded', 'unassessed'}
                or set(match) - {'status', 'basis', 'actor', 'evidence', 'priority', 'dimensions'}
                or type(match.get('priority', 1)) is not int or match.get('priority', 1) < 1):
            raise ValueError('invalid relevance judgment for ' + ident)
        if match['status'] != 'unassessed' and any(not isinstance(match.get(k), str) or not match[k].strip() for k in ('basis', 'actor')):
            raise ValueError('a relevance judgment requires its basis and actor')
        if match['status'] == 'direct':
            if not match.get('evidence') or not isinstance(match['evidence'], list):
                raise ValueError('direct relevance requires inspected original evidence')
            for evidence in match['evidence']:
                if not isinstance(evidence, dict):
                    raise ValueError('direct relevance requires original page locators')
                source = documents.get(evidence.get('document_id', ident))
                if source is None or source['id'] != ident:
                    raise ValueError('direct relevance requires the candidate body in the current corpus')
                selected = verified_passage(source, evidence.get('page'), evidence.get('start'), evidence.get('end'))
                if not any(observation.get('current') and observation.get('raw_sha256') == source['raw_sha256']
                    and observation.get('version') == source.get('version') and any(
                        e['page'] == selected['page'] and e['start'] <= selected['start'] and e['end'] >= selected['end']
                        for e in observation.get('evidence', [])) for observation in source.get('reading_observations', [])):
                    raise ValueError('direct relevance evidence requires an explicit current reading observation')
                evidence.update(selected)
        publication = publication_details(metadata, plan['as_of'])
        venue = venue_priority(metadata, plan, publication)
        if venue['working_paper'] and not venue['venue_ids'] and publication['status'] != 'working_paper':
            publication = publication_details({**metadata, 'publication_status': 'working_paper',
                                              'publication_status_inferred': False}, plan['as_of'])
            publication['status_basis'] = 'reported institutional working-paper series'
            venue = venue_priority(metadata, plan, publication)
        ranked.append({'document_id': ident, 'paper_id': doc.get('paper_id', metadata.get('doi') or ident),
                       'version': doc.get('version', metadata.get('version')), 'raw_sha256': doc.get('raw_sha256'),
                       'title': metadata.get('title'), 'authors': metadata.get('authors', []),
                       'doi': metadata.get('doi'), 'url': metadata.get('url'), 'publication': publication,
                       'priority': venue, 'match': match, 'body_status': doc.get('body_status', 'missing'),
                       'research_selection': doc.get('research_selection'), 'metadata': metadata})
    # Only shared stable identifiers and explicitly evidenced version relations join editions.
    parents = list(range(len(ranked)))
    def root(index):
        while parents[index] != index:
            index = parents[index]
        return index
    known, by_doi, by_doc, identity_links = {}, {}, {}, []
    for i, row in enumerate(ranked):
        by_doc[row['document_id']] = i
        if row['doi']:
            by_doi[doi_key(row['doi'])] = i
        for identity in [('paper', row['paper_id']), *([('doi', doi_key(row['doi']))] if row['doi'] else [])]:
            if identity in known:
                parents[root(i)] = root(known[identity])
                identity_links.append({'documents': [row['document_id'], ranked[known[identity]]['document_id']],
                                       'basis': identity[0], 'identifier': identity[1]})
            else:
                known[identity] = i
    for i, row in enumerate(ranked):
        relations = row['metadata'].get('relations', {})
        if isinstance(relations, dict):
            for kind in ('is-preprint-of', 'has-preprint', 'is-version-of', 'has-version', 'is-identical-to'):
                for relation in relations.get(kind, []):
                    target = by_doi.get(doi_key(relation.get('id', '')))
                    if relation.get('id-type') == 'doi' and target is not None:
                        parents[root(i)] = root(target)
                        identity_links.append({'documents': [row['document_id'], ranked[target]['document_id']],
                            'basis': 'publisher_relation', 'relation': kind, 'metadata': relation,
                            'source': row['metadata'].get('metadata_response', row['metadata'].get('metadata_source'))})
        for relation in documents.get(row['document_id'], {}).get('relations', []):
            target = by_doc.get(relation.get('target', {}).get('document_id'))
            if relation['kind'] == 'version_of' and target is not None:
                parents[root(i)] = root(target)
                identity_links.append({'documents': [row['document_id'], ranked[target]['document_id']],
                                       'basis': 'source_bound_version_of', 'relation': relation})
    families = {}
    for i, row in enumerate(ranked):
        families.setdefault(root(i), []).append(row)
    studies = []
    status_order = {'published': 0, 'forthcoming': 1, 'working_paper': 2, 'unreported': 3}
    relevance_order = {'direct': 0, 'related': 1, 'unassessed': 2, 'excluded': 3}
    for versions in families.values():
        versions.sort(key=lambda row: (status_order[row['publication']['status']],
            -(row['publication']['formal_publication_year'] or row['publication']['selection_year'] or 0), row['document_id']))
        preferred = copy.deepcopy(versions[0])
        relevant = min(versions, key=lambda row: (relevance_order[row['match']['status']], row['match'].get('priority', 1)))
        preferred['match'] = relevant['match']
        preferred['match_document_id'] = relevant['document_id']
        first_dates = [row['publication']['first_release_date'] for row in versions if row['publication']['first_release_date']]
        preferred['first_release_date'] = min(first_dates) if first_dates else None
        bodies = [row for row in versions if row['body_status'] == 'available']
        preferred['latest_manuscript_document_id'] = max(bodies, key=lambda row:
            row['publication']['latest_manuscript_date'] or '')['document_id'] if bodies else None
        preferred['versions'] = [{key: row[key] for key in ('document_id', 'version', 'raw_sha256', 'doi', 'title', 'authors', 'url', 'publication', 'body_status')}
                                 for row in versions]
        version_ids = {row['document_id'] for row in versions}
        preferred['edition_reconciliation'] = {'publication_document_id': preferred['document_id'],
            'inspected_match_document_id': relevant['document_id'] if relevant['match']['status'] == 'direct' else None,
            'manuscript_document_id': preferred['latest_manuscript_document_id'],
            'identity_links': [link for link in identity_links if set(link['documents']) <= version_ids],
            'source_claims_remain_bound_to_document_id': True}
        p, m = preferred['priority'], preferred['match']
        preferred['sort_key'] = [relevance_order[m['status']], p['tier'], m.get('priority', 1),
            int(preferred['publication']['window'][1]) if preferred['publication']['window'] else 4,
            -(preferred['publication']['selection_year'] or 0), p['group_order'],
            p['theme_rank'] or 10000, p['venue_rank'] or 10000, preferred['document_id']]
        if m['status'] != 'excluded' and (not specification.get('direct_only') or m['status'] == 'direct'):
            studies.append(preferred)
    studies.sort(key=lambda row: row['sort_key'])
    for rank, row in enumerate(studies, 1):
        row['rank'] = rank
    return {'as_of': plan['as_of'], 'year': plan['year'], 'windows': plan['windows'],
            'policy_id': plan['policy_id'], 'policy_sha256': plan['policy_sha256'],
            'specification': copy.deepcopy(specification), 'candidate_count': len(candidates),
            'study_count': len(families), 'eligible_count': len(studies), 'ranked_studies': studies[:limit]}


def verified_passage(document, page, start=None, end=None):
    if document.get('body_status') == 'missing' or not document.get('path'):
        raise ValueError('selected document has no original body')
    if hashlib.sha256(Path(document['path']).read_bytes()).hexdigest() != document['raw_sha256']:
        raise ValueError('selected original source hash changed: ' + document['id'])
    if type(page) is not int or not 1 <= page <= len(document['pages']):
        raise ValueError('selected page is outside the document')
    row = document['pages'][page-1]
    path = Path(row['text_path'])
    if not path.is_absolute():
        raise ValueError('stored extracted page path must be absolute')
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    start = 0 if start is None else start
    end = len(text) if end is None else end
    source_id = hashlib.sha256((document['id'] + '\0' + str(page)).encode()).hexdigest()
    if (hashlib.sha256(raw).hexdigest() != row['text_sha256'] or text != row['text'] or row['page'] != page
            or row['source_id'] != source_id or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(text)):
        raise ValueError('selected extracted page or locator changed')
    return {'document_id': document['id'], 'version': document.get('version'), 'raw_sha256': document['raw_sha256'],
            'page': page, 'start': start, 'end': end, 'source_id': source_id, 'text_sha256': row['text_sha256'],
            'quote': text[start:end], 'quote_sha256': hashlib.sha256(text[start:end].encode()).hexdigest()}


def search_paged(owner, queries, directory, per_page=20, pages=2, *, as_of=None, window=None, venue=None):
    if not isinstance(queries,list) or not queries or len(queries)>20 or any(not isinstance(q,str) or not q.strip() for q in queries) or not 1<=per_page<=100 or not 1<=pages<=10:
        raise ValueError('provide 1..20 nonempty queries, 1..100 results per page, and 1..10 pages')
    timing = search_plan([], as_of)
    filters = {}
    if window is not None:
        if window not in {'R0', 'R1', 'R2', 'R3'}:
            raise ValueError('window must be R0, R1, R2 or R3')
        filters.update(next(row['crossref_filters'] for row in timing['windows'] if row['id'] == window))
    if venue is not None and (not isinstance(venue, str) or not venue.strip()):
        raise ValueError('venue must be a nonempty Crossref container title')
    results=[]; works=[]; identities={}
    for qi,query in enumerate(queries):
        for page in range(1,pages+1):
            parameters = {'query.bibliographic':query,'rows':per_page,'offset':(page-1)*per_page}
            if filters:
                parameters['filter'] = ','.join(key + ':' + value for key, value in filters.items())
            if venue:
                parameters['query.container-title'] = venue
            url=owner.CROSSREF+'?'+urlencode(parameters)
            response=None
            try:
                payload,response=owner.get_json(url,directory,f'search-{qi+1}-{page}.json')
                message=owner.crossref_message(payload)
                if not isinstance(message.get('items'),list) or len(message['items']) > per_page or not isinstance(message.get('total-results'),int) or message['total-results'] < 0: raise ValueError('invalid Crossref pagination')
                batch=[owner.crossref_work(item,response) for item in message['items']]
            except (ValueError,RuntimeError,OSError) as exc:
                fail={'query':query,'query_index':qi+1,'page':page,'status':'error','error':str(exc)}
                if isinstance(exc,owner.SourceResponseError): fail['response']=exc.response
                elif response is not None: fail['response']=response
                results.append(fail); break
            results.append({'query':query,'query_index':qi+1,'page':page,'status':'ok','response':response,'returned':len(batch),'total':message['total-results']})
            for index,work in enumerate(batch):
                identity = owner.work_identity(work) or ('unresolved', qi, page, index)
                origin={'query':query,'query_index':qi+1,'page':page,'rank':(page-1)*per_page+index+1,'response':response}
                if identity in identities: works[identities[identity]]['origins'].append(origin)
                else:
                    identities[identity]=len(works); works.append({**work,'origins':[origin]})
            if len(batch)<per_page or page*per_page>=message['total-results']: break
    coverage = []
    for qi, query in enumerate(queries):
        matched = [x for x in results if x['query_index'] == qi+1]
        successful = [x for x in matched if x['status'] == 'ok']
        totals = [x['total'] for x in successful]
        stable = len(set(totals)) <= 1
        coverage.append({'query':query, 'query_index':qi+1, 'pages_retrieved':len(successful),
                         'reported_totals':totals, 'stable_total':stable,
                         'complete':bool(successful and stable and not any(x['status'] == 'error' for x in matched) and (successful[-1]['page']*per_page >= successful[-1]['total'] or successful[-1]['returned'] < per_page))})
    record={'source':'Crossref','queries':queries,'per_page':per_page,'maximum_pages':pages,'pages':results,'coverage':coverage,
            'as_of':timing['as_of'], 'window':window, 'filters':filters, 'venue_query':venue,
            'works':works,'returned':len(works),'status':'partial' if any(x['status']=='error' for x in results) else 'ok'}
    owner.save_record(directory,record); return record


def citations(owner, doi, directory, per_page=20, pages=2):
    if not 1<=per_page<=100 or not 1<=pages<=10: raise ValueError('per-page must be 1..100 and pages 1..10')
    doi=owner.normalize_doi(doi)
    url=OPENALEX+'/https://doi.org/'+quote(doi,safe='/')+'?'+urlencode({'select':'id,doi,title,referenced_works,cited_by_count'})
    work,work_response=owner.get_json(url,directory,'citation-root.json')
    if not isinstance(work,dict) or not re.fullmatch(r'https://openalex\.org/W\d+',work.get('id','')) or owner.normalize_doi(work.get('doi'))!=doi or not isinstance(work.get('referenced_works'),list):
        raise owner.SourceResponseError('OpenAlex returned an invalid root work',work_response)
    wid=work['id'].rsplit('/',1)[1]; backward=work['referenced_works']
    resolved = {}; backward_responses=[]; failures=[]
    if any(not isinstance(x,str) or not re.fullmatch(r'https://openalex\.org/W\d+',x) for x in backward):
        raise owner.SourceResponseError('invalid referenced work identifier',work_response)
    chunk_size=min(per_page,25)
    for offset in range(0,min(len(backward),chunk_size*pages),chunk_size):
        chosen=backward[offset:offset+chunk_size]
        selector='|'.join(x.rsplit('/',1)[1] for x in chosen)
        target=OPENALEX+'?'+urlencode({'filter':'openalex:'+selector,'per-page':chunk_size,'page':1,'select':'id,doi,title,publication_year'})
        response=None
        try:
            payload,response=owner.get_json(target,directory,f'citations-backward-{offset//chunk_size+1}.json')
            if not isinstance(payload,dict) or not isinstance(payload.get('results'),list): raise ValueError('invalid OpenAlex referenced-work page')
            for item in payload['results']:
                if not isinstance(item,dict) or item.get('id') not in chosen or item['id'] in resolved: raise ValueError('unexpected or duplicate referenced work')
                resolved[item['id']]={'work':item,'response':response}
            backward_responses.append({'requested':chosen,'returned':len(payload['results']),'response':response})
        except (ValueError,RuntimeError,OSError) as exc:
            failure={'direction':'backward','offset':offset,'error':str(exc)}
            if isinstance(exc,owner.SourceResponseError): failure['response']=exc.response
            elif response is not None: failure['response']=response
            failures.append(failure); break
    forward=[]; responses=[]
    for page in range(1,pages+1):
        url=OPENALEX+'?'+urlencode({'filter':'cites:'+wid,'per-page':per_page,'page':page,'select':'id,doi,title,publication_year,referenced_works'})
        response=None
        try:
            payload,response=owner.get_json(url,directory,f'citations-forward-{page}.json')
            if not isinstance(payload,dict) or not isinstance(payload.get('results'),list) or not isinstance(payload.get('meta'),dict): raise ValueError('invalid OpenAlex citing-work page')
            batch=payload['results']; meta=payload['meta']
            if meta.get('page')!=page or meta.get('per_page')!=per_page or not isinstance(meta.get('count'),int): raise ValueError('invalid OpenAlex citation pagination')
            for item in batch:
                if not isinstance(item,dict) or not isinstance(item.get('id'),str) or work['id'] not in item.get('referenced_works',[]): raise ValueError('citing work does not link to root')
            ids={x['id'] for x in forward}
            if any(item['id'] in ids for item in batch) or len({x['id'] for x in batch})!=len(batch): raise ValueError('duplicate citing work across pages')
            forward.extend(batch);responses.append({'page':page,'response':response,'returned':len(batch),'total':meta['count']})
        except (ValueError,RuntimeError,OSError) as exc:
            failure={'direction':'forward','page':page,'error':str(exc)}
            if isinstance(exc,owner.SourceResponseError): failure['response']=exc.response
            elif response is not None: failure['response']=response
            failures.append(failure); break
        if len(batch)<per_page or page*per_page>=meta['count']:break
    requested_backward=sum(len(x['requested']) for x in backward_responses)
    backward_complete = len(resolved) == len(backward) and not any(x['direction'] == 'backward' for x in failures)
    forward_totals = [x['total'] for x in responses]
    forward_complete = bool(responses and len(set(forward_totals)) == 1 and len(forward) >= forward_totals[-1]
                            and not any(x['direction'] == 'forward' for x in failures))
    coverage={'backward':{'total_ids':len(backward), 'requested':requested_backward, 'resolved':len(resolved),
                          'complete':backward_complete, 'bounded_prefix':chunk_size*pages},
              'forward':{'returned':len(forward),'reported_totals':forward_totals,'complete':forward_complete,
                         'maximum_pages':pages, 'per_page':per_page}}
    record={'source':'OpenAlex','requested_doi':doi,'root':work,'root_response':work_response,'coverage':coverage,
            'backward':[{'referenced_work_id':x,'source_response':work_response, 'resolved':resolved.get(x)} for x in backward],
            'backward_responses':backward_responses,
            'forward':forward,'forward_responses':responses,'failures':failures,'per_page':per_page,'maximum_pages':pages,
            'returned':len(forward),'status':'partial' if failures else 'ok'}
    owner.save_record(directory,record);return record


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts=[]; self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript'}: self.hidden+=1
        if not self.hidden and tag in {'p','div','section','article','h1','h2','h3','li','br'}: self.parts.append('\n\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript'} and self.hidden: self.hidden-=1
        if not self.hidden and tag in {'p','div','section','article','h1','h2','h3','li'}: self.parts.append('\n\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def pages_from_bytes(raw,kind):
    if kind=='pdf':
        try:
            out=subprocess.run(['pdftotext','-layout','-enc','UTF-8','-','-'],input=raw,capture_output=True,check=True,timeout=60).stdout.decode('utf-8')
        except (OSError,subprocess.SubprocessError,UnicodeError) as exc: raise ValueError(f'PDF extraction failed: {exc}') from None
        pages=out.split('\f')
        if pages and not pages[-1].strip():pages.pop()
        return pages
    try: content=raw.decode('utf-8')
    except UnicodeDecodeError: raise ValueError('text and HTML inputs must be UTF-8') from None
    if kind=='text':return [content]
    if kind=='html':
        parser=VisibleHTML();parser.feed(content);parser.close();return [''.join(parser.parts)]
    raise ValueError('format must be text, html or pdf')


def design_proposition(claim):
    """Keep each comparison dimension attached to its own original passage."""
    dimensions = {}
    for facet, value in claim.get('facets', {}).items():
        if facet in DIMENSIONS:
            evidence = claim['evidence'][claim.get('facet_evidence', {}).get(facet, 0)]
            dimensions['identifying_variation' if facet == 'identification' else facet] = {
                'claim': value, 'evidence': {key: evidence[key] for key in ('source_id', 'start', 'end', 'quote')}}
    return {'id': claim['document_id'] + ':' + claim['id'], 'dimensions': dimensions}


def corpus(owner, spec, directory, reuse=None, *, as_of=None):
    """Extract source passages and rank selected, attributed economic propositions."""
    required = {'query', 'documents', 'limit'}
    if not isinstance(spec, dict) or not required <= set(spec) or set(spec) - required - {'selection', 'search_priority'}:
        raise ValueError('corpus requires query, documents and limit, with optional selection')
    if (not isinstance(spec['query'], str) or not spec['query'].strip()
            or not isinstance(spec['documents'], list) or not 1 <= len(spec['documents']) <= 500
            or type(spec['limit']) is not int or not 1 <= spec['limit'] <= 1000):
        raise ValueError('provide a query, 1..500 documents and limit 1..1000')
    selection = spec.get('selection', {})
    filters = {'document_ids', 'proposition_ids', 'kinds', 'facets', 'knowledge_ids', 'relation_kinds'}
    if (not isinstance(selection, dict) or set(selection) - filters or any(
            not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values)
            or len(set(values)) != len(values) for values in selection.values())):
        raise ValueError('selection filters must be nonempty lists of distinct IDs')
    facet_names = set(DIMENSIONS) | {'question', 'contribution', 'data', 'estimator', 'inference', 'counterfactual', 'welfare'}
    kinds = {'claim', 'model', 'identification', 'result', 'interpretation', 'adoption'}
    relation_kinds = {'supports', 'contradicts', 'extends', 'replicates', 'shares_data', 'shares_experiment',
                      'reuses_result', 'measurement_diff', 'population_diff', 'identification_diff', 'method_critique', 'version_of'}
    if (set(selection.get('facets', [])) - facet_names or set(selection.get('kinds', [])) - kinds
            or set(selection.get('relation_kinds', [])) - (relation_kinds | {'author_code', 'replication'})):
        raise ValueError('selection contains an unknown kind or facet')
    prior_docs, old_pages = {}, {}
    if reuse is not None:
        prior = read_record(reuse)
        if prior.get('kind') != 'local_corpus' or not isinstance(prior.get('documents'), list):
            raise ValueError('reuse requires a local corpus source record')
        for row in prior['documents']:
            if row['id'] in prior_docs:
                raise ValueError('reuse contains duplicate document IDs')
            prior_docs[row['id']] = row
            if row.get('extractor_version') == EXTRACTOR_VERSION and row.get('raw_sha256') is not None:
                old_pages[(row['format'], row['raw_sha256'])] = row['pages']
    documents, passages, propositions, ids = [], [], [], set()
    for doc in spec['documents']:
        if (not isinstance(doc, dict) or not {'id', 'path', 'format'} <= set(doc)
                or set(doc) - {'id', 'path', 'format', 'propositions', 'relations', 'uses', 'metadata', 'paper_id', 'version',
                               'research_selection', 'reading_observations'}):
            raise ValueError('document requires id, path and format with optional annotations and metadata')
        ident = doc['id']
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError('document IDs must be unique nonempty strings')
        ids.add(ident)
        missing = doc['format'] == 'metadata'
        if missing and doc['path'] is not None:
            raise ValueError('metadata-only document cannot claim an original body path')
        path = None if missing else Path(doc['path']).resolve()
        raw = None if missing else path.read_bytes()
        if raw is not None and len(raw) > owner.MAX_BYTES:
            raise ValueError('document exceeds size limit')
        raw_hash = hashlib.sha256(raw).hexdigest() if raw is not None else None
        previous = prior_docs.get(ident)
        metadata = doc.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ValueError('metadata must be an object')
        json.dumps(metadata, allow_nan=False)
        old_version = previous.get('version') if previous else None
        version = doc.get('version', metadata.get('version', old_version))
        if version is not None and (not isinstance(version, str) or not version.strip()):
            raise ValueError('document version must be a nonempty string')
        same = bool(previous and previous['raw_sha256'] == raw_hash and old_version == version
                    and previous['format'] == doc['format'] and previous.get('extractor_version') == EXTRACTOR_VERSION)
        if (previous and not same and (previous.get('raw_sha256') is not None or
                any(previous.get(key) for key in ('propositions', 'relations', 'uses')))
                and any(key not in doc for key in ('propositions', 'relations', 'uses'))):
            raise ValueError('changed document or edition requires explicit propositions, relations and uses')
        if same or (previous and previous.get('raw_sha256') is None and old_version == version):
            metadata = {**previous.get('metadata', {}), **metadata}
        if previous:
            old_publication = {key: previous.get('metadata', {}).get(key) for key in PUBLICATION_FIELDS}
            new_publication = {key: metadata.get(key) for key in PUBLICATION_FIELDS}
            if old_publication != new_publication:
                history = copy.deepcopy(previous.get('metadata', {}).get('publication_history', []))
                history.append({'fields': old_publication, 'metadata_source': previous.get('metadata', {}).get('metadata_source'),
                                'metadata_response': previous.get('metadata', {}).get('metadata_response')})
                metadata['publication_history'] = history
        if 'paper_id' in doc and (not isinstance(doc['paper_id'], str) or not doc['paper_id'].strip()):
            raise ValueError('paper_id must be a nonempty string')
        paper_id = doc.get('paper_id') or (previous.get('paper_id') if previous else None)
        if paper_id is None:
            paper_id = owner.normalize_doi(metadata['doi']) if metadata.get('doi') else ident
        if not isinstance(paper_id, str) or not paper_id.strip():
            raise ValueError('paper_id must be a nonempty string')
        key = (doc['format'], raw_hash)
        reused = key in old_pages
        if missing:
            page_rows = []
        elif reused:
            page_rows = copy.deepcopy(old_pages[key])
            if (not isinstance(page_rows, list) or any(not isinstance(page, dict) or page.get('page') != i + 1
                    or not isinstance(page.get('text'), str)
                    or hashlib.sha256(page['text'].encode()).hexdigest() != page.get('text_sha256')
                    for i, page in enumerate(page_rows))):
                raise ValueError('reused page hashes do not match text')
        else:
            page_rows = [{'page': i + 1, 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
                         for i, text in enumerate(pages_from_bytes(raw, doc['format']))]
        for page in page_rows:
            page_bytes = page['text'].encode('utf-8')
            retained = Path(page['text_path']) if reused and page.get('text_path') else None
            if retained is not None and retained.is_file():
                if retained.read_bytes() != page_bytes:
                    raise ValueError('reused page file has conflicting bytes')
                page_path = retained
            else:
                page_path = directory / 'pages' / (page['text_sha256'] + '.txt')
                if page_path.exists() and page_path.read_bytes() != page_bytes:
                    raise ValueError('content-addressed page has conflicting bytes')
                if not page_path.exists():
                    owner.atomic_write(page_path, page_bytes)
            page['source_id'] = hashlib.sha256((ident + '\0' + str(page['page'])).encode()).hexdigest()
            page['text_path'] = str(page_path.resolve())
        props = copy.deepcopy(doc.get('propositions', previous.get('propositions', []) if same else []))
        relations = copy.deepcopy(doc.get('relations', previous.get('relations', []) if same else []))
        uses = copy.deepcopy(doc.get('uses', previous.get('uses', []) if same else []))
        research_selection = copy.deepcopy(doc.get('research_selection', previous.get('research_selection') if previous else None))
        if previous and not same and previous.get('research_selection') is not None and 'research_selection' not in doc:
            raise ValueError('changed document requires explicit research selection')
        if 'research_selection' in doc and research_selection is None:
            raise ValueError('research selection requires status, reason, actor and adoption authority')
        if research_selection is not None:
            if (not isinstance(research_selection, dict) or set(research_selection) != {'status', 'reason', 'actor', 'authority'}
                    or research_selection['status'] not in {'adopted', 'excluded', 'pending'}
                    or any(not isinstance(research_selection[k], str) or not research_selection[k].strip() for k in ('reason', 'actor'))
                    or not isinstance(research_selection['authority'], str)
                    or research_selection['status'] == 'adopted' and not research_selection['authority'].strip()):
                raise ValueError('research selection requires status, reason, actor and adoption authority')
        observations = copy.deepcopy(previous.get('reading_observations', []) if previous else [])
        for observation in observations:
            observation['current'] = (observation['raw_sha256'] == raw_hash and observation.get('version') == version)
        supplied = doc.get('reading_observations', [])
        if not isinstance(supplied, list):
            raise ValueError('reading observations must be a list')
        for observation in supplied:
            if (not isinstance(observation, dict) or set(observation) != {'kind', 'reader', 'basis', 'evidence'}
                    or observation['kind'] not in {'ai_inspected', 'human_asserted'}
                    or any(not isinstance(observation[k], str) or not observation[k].strip() for k in ('reader', 'basis'))
                    or not isinstance(observation['evidence'], list) or not observation['evidence']):
                raise ValueError('reading observation requires kind, reader, basis and exact source ranges')
            evidence = copy.deepcopy(observation['evidence'])
            for locator in evidence:
                if not isinstance(locator, dict) or set(locator) != {'page', 'start', 'end'}:
                    raise ValueError('reading observation requires exact page, start and end')
                page, start, end = (locator[k] for k in ('page', 'start', 'end'))
                if (any(type(v) is not int for v in (page, start, end)) or not 1 <= page <= len(page_rows)
                        or not 0 <= start < end <= len(page_rows[page-1]['text'])):
                    raise ValueError('reading observation falls outside extracted text')
                source = page_rows[page-1]
                quote = source['text'][start:end]
                locator.update(source_id=source['source_id'], text_sha256=source['text_sha256'], quote=quote,
                               quote_sha256=hashlib.sha256(quote.encode('utf-8')).hexdigest())
            saved = {**observation, 'evidence': evidence, 'raw_sha256': raw_hash, 'version': version, 'current': True}
            if saved not in observations:
                observations.append(saved)
        # Reused records retain generated evidence; reconstruct the single authored form.
        if 'propositions' not in doc and isinstance(props, list):
            for item in props:
                item.pop('proposition_sha256', None)
                item['evidence'] = [{k: e[k] for k in ('page', 'start', 'end')} for e in item['evidence']]
        if 'relations' not in doc:
            for item in relations:
                if 'evidence' in item:
                    item['evidence'] = [{k: e[k] for k in ('page', 'start', 'end')} for e in item['evidence']]
        legacy = isinstance(props, dict)
        if legacy and set(props) - set(DIMENSIONS):
            raise ValueError('legacy propositions must use the five comparison dimensions')
        if not legacy and not isinstance(props, list):
            raise ValueError('propositions must be a five-dimension map or a list')
        if not isinstance(relations, list) or not isinstance(uses, list):
            raise ValueError('relations and uses must be lists')
        claims = []
        if legacy:
            for dim, item in props.items():
                if (not isinstance(item, dict) or set(item) != {'claim', 'page', 'start', 'end'}
                        or not isinstance(item['claim'], str) or not item['claim'].strip()):
                    raise ValueError('legacy proposition requires claim, page, start and end')
                claims.append({'id': dim, 'kind': 'claim', 'claim': item['claim'],
                               'attribution': {'actor': 'researcher', 'role': 'researcher'},
                               'facets': {dim: item['claim']},
                               'evidence': [{k: item[k] for k in ('page', 'start', 'end')}]})
        else:
            claims = props
        claim_ids, spans = set(), []
        for claim in claims:
            required_claim = {'id', 'kind', 'claim', 'attribution', 'evidence'}
            if (not isinstance(claim, dict) or not required_claim <= set(claim)
                    or set(claim) - required_claim - {'facets', 'facet_evidence', 'content', 'knowledge_ids', 'decision', 'location'}
                    or not isinstance(claim['id'], str) or not claim['id'].strip() or claim['id'] in claim_ids
                    or claim['kind'] not in kinds or not isinstance(claim['claim'], str) or not claim['claim'].strip()):
                raise ValueError('invalid or duplicate proposition')
            claim_ids.add(claim['id'])
            attribution = claim['attribution']
            if (not isinstance(attribution, dict) or set(attribution) != {'actor', 'role'}
                    or not isinstance(attribution['actor'], str) or not attribution['actor'].strip()
                    or attribution['role'] not in {'author', 'researcher', 'decision_owner'}):
                raise ValueError('proposition attribution requires actor and role')
            facets = claim.get('facets', {})
            if (not isinstance(facets, dict) or set(facets) - facet_names
                    or any(not isinstance(value, str) or not value.strip() for value in facets.values())):
                raise ValueError('invalid proposition facets')
            if 'content' in claim:
                if not isinstance(claim['content'], dict): raise ValueError('proposition content must be an object')
                json.dumps(claim['content'], allow_nan=False)
            knowledge = claim.get('knowledge_ids', [])
            if not isinstance(knowledge, list) or any(not isinstance(x, str) or not x.strip() for x in knowledge) or len(set(knowledge)) != len(knowledge):
                raise ValueError('knowledge_ids must be distinct nonempty strings')
            if 'location' in claim:
                location = claim['location']
                if (not isinstance(location, dict) or not location or set(location) - {'section', 'equation', 'table', 'figure'}
                        or any(not isinstance(value, str) or not value.strip() for value in location.values())):
                    raise ValueError('invalid proposition location')
            if 'decision' in claim:
                decision = claim['decision']
                if (not isinstance(decision, dict) or set(decision) != {'decision_id', 'purpose', 'status', 'authority'}
                        or any(not isinstance(decision[k], str) or not decision[k].strip() for k in ('decision_id', 'purpose'))
                        or decision['status'] not in {'proposed', 'adopted'}
                        or not isinstance(decision['authority'], str)
                        or decision['status'] == 'adopted' and not decision['authority'].strip()):
                    raise ValueError('invalid proposition decision or adoption authority')
            if not isinstance(claim['evidence'], list) or not claim['evidence']:
                raise ValueError('proposition needs source evidence')
            facet_evidence = claim.get('facet_evidence', {})
            if (not isinstance(facet_evidence, dict) or set(facet_evidence) - set(facets)
                    or any(type(index) is not int or not 0 <= index < len(claim['evidence'])
                           for index in facet_evidence.values())):
                raise ValueError('facet_evidence must reference a proposition evidence index')
            spans.extend(('proposition', claim, evidence) for evidence in claim['evidence'])
        for relation in relations:
            if not isinstance(relation, dict) or not isinstance(relation.get('basis'), str) or not relation['basis'].strip():
                raise ValueError('relation requires kind and nonempty basis')
            if relation.get('kind') in {'author_code', 'replication'}:
                if set(relation) != {'kind', 'url', 'basis'}: raise ValueError('invalid source URL relation')
                owner.validate_url(relation['url'])
            else:
                if (set(relation) - {'kind', 'target', 'basis', 'evidence', 'conditions'}
                        or not {'kind', 'target', 'basis', 'evidence'} <= set(relation)
                        or relation['kind'] not in relation_kinds or not isinstance(relation['target'], dict)
                        or set(relation['target']) not in ({'document_id'}, {'document_id', 'proposition_id'})
                        or any(not isinstance(v, str) or not v.strip() for v in relation['target'].values())
                        or not isinstance(relation['evidence'], list) or not relation['evidence']
                        or 'conditions' in relation and (not isinstance(relation['conditions'], str) or not relation['conditions'].strip())):
                    raise ValueError('invalid typed relation')
                spans.extend(('relation', relation, evidence) for evidence in relation['evidence'])
        for use in uses:
            if (not isinstance(use, dict) or set(use) != {'decision_id', 'purpose', 'page', 'start', 'end'}
                    or any(not isinstance(use[k], str) or not use[k].strip() for k in ('decision_id', 'purpose'))):
                raise ValueError('use requires decision_id, purpose, page, start and end')
            spans.append(('use', use, {k: use[k] for k in ('page', 'start', 'end')}))
        for kind, parent, evidence in spans:
            if not isinstance(evidence, dict) or set(evidence) != {'page', 'start', 'end'}:
                raise ValueError('evidence locator requires exactly page, start and end')
            page, start, end = (evidence[k] for k in ('page', 'start', 'end'))
            if (any(type(v) is not int for v in (page, start, end)) or not 1 <= page <= len(page_rows)
                    or not 0 <= start < end <= len(page_rows[page-1]['text'])):
                raise ValueError('evidence locator falls outside extracted text')
            if kind != 'use':
                source = page_rows[page-1]
                quote_text = source['text'][start:end]
                evidence.update(source_id=source['source_id'], text_sha256=source['text_sha256'],
                                quote=quote_text, quote_sha256=hashlib.sha256(quote_text.encode('utf-8')).hexdigest())
        for claim in claims:
            authored = {k: v for k, v in claim.items() if k != 'evidence'}
            authored['evidence'] = [{k: e[k] for k in ('page', 'start', 'end')} for e in claim['evidence']]
            identity = {'document_id': ident, 'paper_id': paper_id, 'version': version, 'raw_sha256': raw_hash,
                        'authored': authored, 'page_hashes': [e['text_sha256'] for e in claim['evidence']]}
            claim['proposition_sha256'] = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            propositions.append({'document_id': ident, 'paper_id': paper_id, 'version': version,
                                 'raw_sha256': raw_hash, **claim})
        for page in page_rows:
            text = page['text']
            for match in re.finditer(r'\S(?:.*?\S)?(?=\n[ \t]*\n|\s*\Z)', text, re.S):
                for start in range(match.start(), match.end(), 1200):
                    end = min(start + 1200, match.end())
                    passages.append({'document_id': ident, 'page': page['page'], 'start': start, 'end': end,
                                     'text': text[start:end]})
        document = {'id': ident, 'paper_id': paper_id, 'version': version, 'metadata': metadata,
                          'path': str(path) if path is not None else None, 'format': doc['format'], 'raw_sha256': raw_hash,
                          'bytes': len(raw) if raw is not None else None,
                          'extractor_version': EXTRACTOR_VERSION, 'pages': page_rows, 'reused': reused,
                          'propositions': props, 'relations': relations, 'uses': uses, 'body_status': 'missing' if missing else 'available'}
        if research_selection is not None: document['research_selection'] = research_selection
        if observations: document['reading_observations'] = observations
        documents.append(document)
    by_id = {doc['id']: doc for doc in documents}
    for doc in documents:
        for relation in doc['relations']:
            if 'target' not in relation: continue
            target = relation['target']
            if target['document_id'] not in by_id:
                raise ValueError('relation target document does not exist')
            if 'proposition_id' in target and not any(p['document_id'] == target['document_id'] and p['id'] == target['proposition_id'] for p in propositions):
                raise ValueError('relation target proposition does not exist')
    priority_result = None
    priority_documents = set(by_id)
    priority_order = {}
    if 'search_priority' in spec:
        priority_result = rank_studies({'documents': documents}, spec['search_priority'], as_of, spec['limit'])
        priority_documents = set()
        for row in priority_result['ranked_studies']:
            ident = (row['match_document_id'] if row['match']['status'] == 'direct' else
                     row['latest_manuscript_document_id'] or row['document_id'])
            priority_documents.add(ident)
            priority_order[ident] = row['rank']
    if not passages and not any(doc['format'] == 'metadata' for doc in documents):
        raise ValueError('documents contain no extractable passages')
    selected = []
    for claim in propositions:
        document = by_id[claim['document_id']]
        if (claim['document_id'] not in priority_documents
                or 'document_ids' in selection and claim['document_id'] not in selection['document_ids']
                or 'proposition_ids' in selection and claim['id'] not in selection['proposition_ids']
                    and claim['document_id'] + ':' + claim['id'] not in selection['proposition_ids']
                or 'kinds' in selection and claim['kind'] not in selection['kinds']
                or 'facets' in selection and not set(selection['facets']) & set(claim.get('facets', {}))
                or 'knowledge_ids' in selection and not set(selection['knowledge_ids']) & set(claim.get('knowledge_ids', []))
                or 'relation_kinds' in selection and not set(selection['relation_kinds']) & {r['kind'] for r in document['relations']}):
            continue
        selected.append(claim)
    selected_docs = set(selection.get('document_ids', by_id))
    selected_docs &= priority_documents
    proposition_filter = bool(set(selection) - {'document_ids'})
    if proposition_filter: selected_docs &= {claim['document_id'] for claim in selected}
    passages = [row for row in passages if row['document_id'] in selected_docs and (not proposition_filter or any(
        claim['document_id'] == row['document_id'] and any(e['page'] == row['page'] and e['start'] < row['end'] and e['end'] > row['start']
                                                             for e in claim['evidence']) for claim in selected))]
    tokenize = lambda value: re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', value).casefold(), flags=re.UNICODE)
    terms = list(dict.fromkeys(tokenize(spec['query'])))
    if not terms: raise ValueError('query has no lexical terms')
    ranked_documents = [{'document_id': doc['id'], 'body_status': doc['body_status'],
                         **({'research_selection': doc['research_selection']} if 'research_selection' in doc else {})}
                        for doc in documents]
    bibliography_fields = {'title', 'authors', 'year', 'doi', 'jel', 'keywords', 'citation_key', 'abstract'}
    rank_groups = [[(row, row['text']) for row in passages],
                   [(row, ' '.join([row['claim'], *row.get('facets', {}).values(),
                                    json.dumps(row.get('content', {}), ensure_ascii=False, sort_keys=True),
                                    ' '.join(row.get('knowledge_ids', [])),
                                    json.dumps({key: value for key, value in by_id[row['document_id']]['metadata'].items()
                                                if key in bibliography_fields},
                                               ensure_ascii=False, sort_keys=True)]))
                    for row in selected],
                   [(row, json.dumps({key: value for key, value in by_id[row['document_id']]['metadata'].items()
                                      if key in bibliography_fields}, ensure_ascii=False, sort_keys=True))
                    for row in ranked_documents]]
    rank_statistics = []
    for rank_items in rank_groups:
        tokens = [tokenize(value) for _, value in rank_items]
        counts = [Counter(value) for value in tokens]
        mean = sum(map(len, tokens))/len(tokens) if tokens else 0.
        df = {term: sum(term in count for count in counts) for term in terms}
        rank_statistics.append((df, mean))
        for (row, _), count, words in zip(rank_items, counts, tokens):
            score = 0.
            for term in terms:
                frequency = count[term]
                if frequency:
                    score += math.log(1 + (len(tokens)-df[term]+.5)/(df[term]+.5))*frequency*2.2/(frequency+1.2*(.25+.75*len(words)/mean))
            row['bm25'] = score
    if not selection and rank_statistics[0][1] == 0 and not any(doc['format'] == 'metadata' for doc in documents):
        raise ValueError('corpus has no lexical tokens')
    passages.sort(key=lambda row: (-row['bm25'], row['document_id'], row['page'], row['start']))
    selected.sort(key=lambda row: (-row['bm25'], row['document_id'], row['id']))
    document_scores = {row['document_id']: row['bm25'] for row in ranked_documents}
    for item in passages + selected:
        ident = item['document_id']
        document_scores[ident] = max(document_scores[ident], item['bm25'])
    for row in ranked_documents:
        row['bm25'] = document_scores[row['document_id']]
    ranked_documents.sort(key=lambda row: (-row['bm25'], row['document_id']))
    if priority_result is not None:
        for row in ranked_documents:
            row['literature_rank'] = priority_order.get(row['document_id'])
        ranked_documents.sort(key=lambda row: (row['literature_rank'] or len(documents)+1, -row['bm25'], row['document_id']))
        selected.sort(key=lambda row: (priority_order[row['document_id']], -row['bm25'], row['id']))
        passages.sort(key=lambda row: (priority_order[row['document_id']], -row['bm25'], row['page'], row['start']))
    delivered = selected[:spec['limit']]
    for claim in delivered:
        claim['relations'] = [relation for relation in by_id[claim['document_id']]['relations']
                              if 'relation_kinds' not in selection or relation['kind'] in selection['relation_kinds']]
        if 'research_selection' in by_id[claim['document_id']]:
            claim['research_selection'] = by_id[claim['document_id']]['research_selection']
        claim['evidence_status'] = 'source-location-only'
        claim['relation_status'] = 'researcher-asserted'
    design_sources, design_propositions = {}, []
    for claim in delivered:
        for evidence in claim['evidence']:
            page = by_id[claim['document_id']]['pages'][evidence['page']-1]
            design_sources[evidence['source_id']] = {'path': page['text_path'], 'sha256': evidence['text_sha256']}
        design_propositions.append(design_proposition(claim))
    # The original five-dimension object remains a single compatible design row.
    for doc in documents:
        if isinstance(doc['propositions'], dict) and doc['id'] in selected_docs and 'proposition_ids' not in selection:
            matching = [claim for claim in (delivered if proposition_filter else propositions)
                        if claim['document_id'] == doc['id']]
            dimensions = {}
            for claim in matching:
                evidence = claim['evidence'][0]
                page = doc['pages'][evidence['page']-1]
                design_sources[evidence['source_id']] = {'path': page['text_path'], 'sha256': evidence['text_sha256']}
                dim, value = next(iter(claim['facets'].items()))
                dimensions['identifying_variation' if dim == 'identification' else dim] = {'claim': value,
                    'evidence': {key: evidence[key] for key in ('source_id', 'start', 'end', 'quote')}}
            design_propositions = [row for row in design_propositions if not row['id'].startswith(doc['id'] + ':')]
            design_propositions.append({'id': doc['id'], 'dimensions': dimensions})
    identity = [{'id': d['id'], 'paper_id': d['paper_id'], 'version': d['version'], 'raw_sha256': d['raw_sha256'],
                 'propositions': d['propositions'], 'relations': d['relations'], 'uses': d['uses'],
                 **({'research_selection': d['research_selection']} if 'research_selection' in d else {})} for d in documents]
    corpus_hash = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    versions, unit_owners = [], {}
    for collection in (prior_docs.values(), documents):
        units = {}
        for doc in collection:
            entries = doc['propositions'].items() if isinstance(doc['propositions'], dict) else (
                (claim['id'], claim) for claim in doc['propositions'])
            for local_id, claim in entries:
                reference = doc['id'] + ':' + local_id
                if reference in unit_owners and unit_owners[reference] != doc['id']:
                    raise ValueError('proposition reference collides between document IDs')
                unit_owners[reference] = doc['id']
                units[reference] = (doc['raw_sha256'], doc.get('version'), claim)
        versions.append(units)
    before, after = versions
    altered = {key for key in before.keys() & after.keys() if before[key] != after[key]}
    relations_changed = [doc['id'] for doc in documents if doc['id'] in prior_docs
                         and doc['relations'] != prior_docs[doc['id']]['relations']]
    changed_documents = {doc['id'] for doc in documents if doc['id'] in prior_docs and (
        (doc['raw_sha256'], doc.get('version')) != (prior_docs[doc['id']]['raw_sha256'], prior_docs[doc['id']].get('version')))}
    whole_documents = changed_documents | set(relations_changed) | (prior_docs.keys() - by_id.keys())
    affected_ids = altered | (before.keys() - after.keys()) | (after.keys() - before.keys())
    changed_documents.update(unit_owners[key] for key in affected_ids if unit_owners[key] in prior_docs)
    changed_documents.update(prior_docs.keys() - by_id.keys())
    changed_documents.update(relations_changed)
    reassess = []
    for doc in [*prior_docs.values(), *documents]:
        if doc['id'] in changed_documents:
            spans = [span for version in (before, after) for key in affected_ids if key in version
                     and unit_owners[key] == doc['id']
                     for span in version[key][2].get('evidence', [version[key][2]])]
            for use in doc.get('uses', []):
                if doc['id'] not in whole_documents and not any(
                        span.get('page') == use['page'] and span.get('start', 0) < use['end']
                        and span.get('end', 0) > use['start'] for span in spans):
                    continue
                row = {'document_id': doc['id'], **use}
                if row not in reassess:
                    reassess.append(row)
    changes = {'added': sorted(after.keys() - before.keys()), 'changed': sorted(altered),
               'removed': sorted(before.keys() - after.keys()), 'relations_changed': sorted(relations_changed),
               'documents_changed': sorted(changed_documents), 'uses_to_reassess': reassess,
               'publication_changed': [doc['id'] for doc in documents if doc['id'] in prior_docs and any(
                   doc['metadata'].get(key) != prior_docs[doc['id']].get('metadata', {}).get(key) for key in PUBLICATION_FIELDS)]}
    source_use = []
    for doc in documents:
        if doc['format'] == 'metadata' or doc['id'] not in selected_docs or proposition_filter and not any(
                claim['document_id'] == doc['id'] for claim in delivered):
            continue
        claims = [claim for claim in delivered if claim['document_id'] == doc['id']]
        uses = doc['uses'] if not selection else [use for use in doc['uses'] if any(
            use['decision_id'] == claim.get('decision', {}).get('decision_id') or any(
                e['page'] == use['page'] and e['start'] < use['end'] and e['end'] > use['start']
                for e in claim['evidence']) for claim in claims)]
        source_use.append({'document_id': doc['id'], 'raw_sha256': doc['raw_sha256'],
                           'relations': [relation for relation in doc['relations'] if 'relation_kinds' not in selection
                                         or relation['kind'] in selection['relation_kinds']], 'uses': uses})
    comparisons = [{'document_id': d['id'], **{dim: d['propositions'].get(dim)
                   for dim in DIMENSIONS}} for d in documents if isinstance(d['propositions'], dict) and d['id'] in selected_docs]
    comparisons.extend({'document_id': row['document_id'], 'proposition_id': row['id'],
                        **{dim: row.get('facets', {}).get(dim) for dim in DIMENSIONS}} for row in delivered
                       if isinstance(by_id[row['document_id']]['propositions'], list))
    record = {'schema_version': 2, 'kind': 'local_corpus', 'query': spec['query'], 'corpus_sha256': corpus_hash,
              'documents': documents, 'comparison_matrix': comparisons,
              'design_sources': design_sources, 'design_propositions': design_propositions,
              'ranked_passages': passages[:spec['limit']], 'passage_count': len(passages),
              'ranked_documents': ranked_documents,
              'returned': min(len(passages), spec['limit']), 'ranked_propositions': delivered,
              'proposition_count': len(selected), 'selection': selection, 'changes': changes,
              'bm25': {'k1': 1.2, 'b': .75, 'document_frequency': rank_statistics[0][0],
                       'average_passage_tokens': rank_statistics[0][1],
                       'proposition_document_frequency': rank_statistics[1][0],
                       'average_proposition_tokens': rank_statistics[1][1]},
              'source_use': source_use}
    if priority_result is not None:
        record['search_priority'] = priority_result
    owner.save_record(directory, record)
    return record


def verified_corpus_record(path, expected_sha256):
    """Verify the adopted record before selecting metadata, pages or propositions."""
    raw_record = Path(path).read_bytes()
    actual_record = hashlib.sha256(raw_record).hexdigest()
    if not isinstance(expected_sha256, str) or actual_record != expected_sha256:
        raise ValueError('corpus source record hash differs from the adopted hash')
    record = read_record(path, raw_record)
    if record.get('kind') != 'local_corpus' or not isinstance(record.get('documents'), list):
        raise ValueError('expected a local corpus source record')
    documents = record['documents']
    if len({d['id'] for d in documents}) != len(documents):
        raise ValueError('corpus contains duplicate document IDs')
    if record.get('schema_version') == 2:
        identity = [{'id': d['id'], 'paper_id': d['paper_id'], 'version': d['version'],
                     'raw_sha256': d['raw_sha256'], 'propositions': d['propositions'],
                     'relations': d['relations'], 'uses': d['uses'],
                     **({'research_selection': d['research_selection']} if 'research_selection' in d else {})} for d in documents]
        encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    elif record.get('schema_version') in (None, 1):
        encoded = json.dumps([(d['id'], d['raw_sha256']) for d in documents], ensure_ascii=False, separators=(',', ':'))
    else:
        raise ValueError('unsupported corpus source record version')
    if hashlib.sha256(encoded.encode()).hexdigest() != record.get('corpus_sha256'):
        raise ValueError('corpus contents differ from corpus_sha256')
    return record, actual_record


def corpus_view(path, expected_sha256, *, limit=20, document_ids=None, as_of=None):
    record, digest = verified_corpus_record(path, expected_sha256)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('view limit must be 1..1000')
    docs = {row['id']: row for row in record['documents']}
    if document_ids is not None and (not isinstance(document_ids, list) or not document_ids or set(document_ids)-docs.keys()):
        raise ValueError('view document IDs must exist in the corpus')
    priority = record.get('search_priority')
    if priority:
        priority = rank_studies(record, priority['specification'], as_of, limit)
        order = [row['document_id'] for row in priority['ranked_studies']]
    else:
        order = [row['document_id'] for row in record.get('ranked_documents', [])] or list(docs)
    chosen = (document_ids if document_ids is not None else order)[:limit]
    rows = []
    for ident in chosen:
        doc = docs[ident]
        metadata = doc.get('metadata', {})
        rows.append({'document_id': ident, 'paper_id': doc.get('paper_id'), 'version': doc.get('version'),
                     'raw_sha256': doc.get('raw_sha256'), 'body_status': doc.get('body_status'),
                     'title': metadata.get('title'), 'authors': metadata.get('authors', []), 'doi': metadata.get('doi'),
                     'url': metadata.get('url'), 'journal': metadata.get('journal', metadata.get('container_title')),
                     'publication': publication_details(metadata, as_of), 'page_count': len(doc['pages']),
                     'proposition_count': len(doc['propositions']), 'research_selection': doc.get('research_selection'),
                     'reading_observation_count': sum(bool(row.get('current')) for row in doc.get('reading_observations', []))})
    return {'record_sha256': digest, 'corpus_sha256': record['corpus_sha256'], 'documents': rows,
            'document_count': len(docs), 'returned': len(rows),
            'search_priority': compact_priority(priority) if priority else None}


def compact_priority(priority):
    if priority is None:
        return None
    keys = ('rank', 'document_id', 'paper_id', 'version', 'raw_sha256', 'title', 'authors', 'doi', 'url',
            'publication', 'priority', 'match_document_id', 'first_release_date', 'latest_manuscript_document_id', 'versions',
            'edition_reconciliation')
    rows = [{**{key: row[key] for key in keys},
             'match': {key: value for key, value in row['match'].items() if key != 'evidence'}}
            for row in priority['ranked_studies']]
    return {**{key: priority[key] for key in ('as_of', 'year', 'windows', 'policy_id', 'policy_sha256',
                                            'candidate_count', 'study_count', 'eligible_count')}, 'ranked_studies': rows}


def corpus_passage(path, expected_sha256, document_id, page, start=None, end=None, *, max_chars=12000):
    record, digest = verified_corpus_record(path, expected_sha256)
    if type(max_chars) is not int or not 1 <= max_chars <= 100000:
        raise ValueError('passage max_chars must be 1..100000')
    matches = [row for row in record['documents'] if row['id'] == document_id]
    if len(matches) != 1:
        raise ValueError('selected document ID does not exist')
    result = verified_passage(matches[0], page, start, end)
    if result['end'] - result['start'] > max_chars:
        raise ValueError('selected passage exceeds max_chars; select explicit start and end offsets')
    return {'record_sha256': digest, 'corpus_sha256': record['corpus_sha256'], 'passage': result,
            'reading_status': 'returned_source_range', 'reading_observation_written': False}


def load_corpus_record(path, expected_sha256, *, proposition_ids=None, as_of=None):
    """Read selected stored claims after checking the record and their current sources."""
    record, actual_record = verified_corpus_record(path, expected_sha256)
    documents = record['documents']
    if proposition_ids is not None and (not isinstance(proposition_ids, list) or not proposition_ids
            or any(not isinstance(item, str) or not item.strip() for item in proposition_ids)
            or len(set(proposition_ids)) != len(proposition_ids)):
        raise ValueError('proposition_ids must be a nonempty list of distinct IDs')
    candidates = []
    for doc in documents:
        if isinstance(doc['propositions'], dict):
            for facet, value in doc['propositions'].items():
                if facet not in DIMENSIONS or not isinstance(value, dict):
                    raise ValueError('invalid stored legacy proposition')
                candidates.append((doc, {'id': facet, 'kind': 'claim', 'claim': value['claim'],
                    'attribution': {'actor': 'researcher', 'role': 'researcher'}, 'facets': {facet: value['claim']},
                    'evidence': [{key: value[key] for key in ('page', 'start', 'end')}]}, True))
        elif isinstance(doc['propositions'], list):
            candidates.extend((doc, copy.deepcopy(value), False) for value in doc['propositions'])
        else:
            raise ValueError('invalid stored propositions')
    full_ids = [doc['id'] + ':' + claim['id'] for doc, claim, _ in candidates]
    if len(full_ids) != len(set(full_ids)):
        raise ValueError('corpus contains duplicate proposition IDs')
    chosen = []
    priority = record.get('search_priority')
    priority_order = None
    if priority is not None:
        priority = rank_studies(record, priority['specification'], as_of, len(documents))
        priority_order = {}
        for row in priority['ranked_studies']:
            ident = (row['match_document_id'] if row['match']['status'] == 'direct' else
                     row['latest_manuscript_document_id'] or row['document_id'])
            priority_order[ident] = row['rank']
    if proposition_ids is None:
        chosen = [i for i, (doc, _, _) in enumerate(candidates) if priority_order is None or doc['id'] in priority_order]
        if priority_order is not None:
            chosen.sort(key=lambda i: priority_order[candidates[i][0]['id']])
    else:
        for identity in proposition_ids:
            matches = [i for i, (doc, claim, _) in enumerate(candidates)
                       if identity == doc['id'] + ':' + claim['id'] or identity == claim['id']]
            if len(matches) != 1 or matches[0] in chosen:
                raise ValueError('proposition ID is missing, ambiguous or selected twice: ' + identity)
            chosen.append(matches[0])
    ranked = {(row['document_id'], row['id']): row.get('bm25') for row in record.get('ranked_propositions', [])}
    selected, design_sources, checked_documents = [], {}, set()
    for index in chosen:
        doc, claim, legacy = candidates[index]
        ident = doc['id']
        if not isinstance(claim.get('evidence'), list) or not claim['evidence']:
            raise ValueError('stored proposition needs source evidence')
        if ident not in checked_documents:
            if hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest() != doc['raw_sha256']:
                raise ValueError('selected original source hash changed: ' + ident)
            checked_documents.add(ident)
        for evidence in claim['evidence']:
            page_no, start, end = (evidence.get(key) for key in ('page', 'start', 'end'))
            if any(type(value) is not int for value in (page_no, start, end)) or not 1 <= page_no <= len(doc['pages']):
                raise ValueError('stored proposition page is invalid')
            page = doc['pages'][page_no-1]
            page_path = Path(page['text_path'])
            if not page_path.is_absolute():
                raise ValueError('stored extracted page path must be absolute')
            text_bytes = page_path.read_bytes()
            text = text_bytes.decode('utf-8')
            if (hashlib.sha256(text_bytes).hexdigest() != page['text_sha256'] or text != page['text']
                    or page['page'] != page_no or not 0 <= start < end <= len(text)):
                raise ValueError('selected extracted page or locator changed')
            source_id = hashlib.sha256((ident + '\0' + str(page_no)).encode()).hexdigest()
            quote_text = text[start:end]
            if page['source_id'] != source_id:
                raise ValueError('selected page source identity changed')
            if not legacy and (evidence.get('source_id') != source_id or evidence.get('text_sha256') != page['text_sha256']
                    or evidence.get('quote') != quote_text
                    or evidence.get('quote_sha256') != hashlib.sha256(quote_text.encode('utf-8')).hexdigest()):
                raise ValueError('stored proposition quote or hash differs from the selected source')
            evidence.update(source_id=source_id, text_sha256=page['text_sha256'], quote=quote_text,
                            quote_sha256=hashlib.sha256(quote_text.encode('utf-8')).hexdigest())
            design_sources[source_id] = {'path': str(page_path), 'sha256': page['text_sha256']}
        authored = {key: value for key, value in claim.items() if key not in {'evidence', 'proposition_sha256'}}
        authored['evidence'] = [{key: evidence[key] for key in ('page', 'start', 'end')} for evidence in claim['evidence']]
        identity = {'document_id': ident, 'paper_id': doc.get('paper_id', ident), 'version': doc.get('version'),
                    'raw_sha256': doc['raw_sha256'], 'authored': authored,
                    'page_hashes': [e['text_sha256'] for e in claim['evidence']]}
        prop_hash = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if not legacy and claim.get('proposition_sha256') != prop_hash:
            raise ValueError('stored proposition hash differs from its source and authored content')
        selected.append({'document_id': ident, 'paper_id': doc.get('paper_id', ident), 'version': doc.get('version'),
                         'raw_sha256': doc['raw_sha256'], **claim, 'proposition_sha256': prop_hash,
                         'bm25': ranked.get((ident, claim['id'])), 'relations': doc['relations'],
                         **({'research_selection': doc['research_selection']} if 'research_selection' in doc else {}),
                         'evidence_status': 'source-location-only', 'relation_status': 'researcher-asserted'})
    design_propositions = []
    for claim in selected:
        design_propositions.append(design_proposition(claim))
    for doc in documents:
        if isinstance(doc['propositions'], dict):
            matching = [item for item in selected if item['document_id'] == doc['id']]
            if matching:
                combined = {}
                for item in matching:
                    evidence = item['evidence'][0]
                    facet, value = next(iter(item['facets'].items()))
                    combined['identifying_variation' if facet == 'identification' else facet] = {
                        'claim': value, 'evidence': {key: evidence[key] for key in ('source_id', 'start', 'end', 'quote')}}
                design_propositions = [row for row in design_propositions if not row['id'].startswith(doc['id'] + ':')]
                design_propositions.append({'id': doc['id'], 'dimensions': combined})
    source_use = []
    for doc in documents:
        claims = [item for item in selected if item['document_id'] == doc['id']]
        if not claims:
            continue
        uses = [use for use in doc.get('uses', []) if any(
            use['decision_id'] == claim.get('decision', {}).get('decision_id') or any(
                e['page'] == use['page'] and e['start'] < use['end'] and e['end'] > use['start']
                for e in claim['evidence']) for claim in claims)]
        for relation in doc['relations']:
            target = relation.get('target')
            if target is not None and (target.get('document_id') not in {item['id'] for item in documents}
                    or 'proposition_id' in target and target['document_id'] + ':' + target['proposition_id'] not in full_ids):
                raise ValueError('stored relation target does not exist')
        locators = [('relation', e) for relation in doc['relations'] for e in relation.get('evidence', [])]
        locators.extend(('use', {key: use[key] for key in ('page', 'start', 'end')}) for use in uses)
        for kind, evidence in locators:
            page_no, start, end = (evidence.get(key) for key in ('page', 'start', 'end'))
            if any(type(value) is not int for value in (page_no, start, end)) or not 1 <= page_no <= len(doc['pages']):
                raise ValueError('stored relation or use page is invalid')
            page = doc['pages'][page_no-1]
            page_path = Path(page['text_path'])
            if not page_path.is_absolute():
                raise ValueError('stored extracted page path must be absolute')
            text_bytes = page_path.read_bytes()
            text = text_bytes.decode('utf-8')
            source_id = hashlib.sha256((doc['id'] + '\0' + str(page_no)).encode()).hexdigest()
            if (hashlib.sha256(text_bytes).hexdigest() != page['text_sha256'] or text != page['text']
                    or page['page'] != page_no or page['source_id'] != source_id or not 0 <= start < end <= len(text)):
                raise ValueError('selected relation or use page or locator changed')
            if kind == 'relation' and (evidence.get('quote') != text[start:end]
                    or evidence.get('text_sha256') != page['text_sha256'] or evidence.get('source_id') != source_id
                    or evidence.get('quote_sha256') != hashlib.sha256(text[start:end].encode('utf-8')).hexdigest()):
                raise ValueError('stored relation quote or hash differs from the selected source')
        source_use.append({'document_id': doc['id'], 'raw_sha256': doc['raw_sha256'],
                           'relations': doc['relations'], 'uses': uses})
    return {'record_sha256': actual_record, 'corpus_sha256': record['corpus_sha256'],
            'propositions': selected, 'design_sources': design_sources,
            'design_propositions': design_propositions, 'source_use': source_use,
            'search_priority': compact_priority(priority) if priority else None}
