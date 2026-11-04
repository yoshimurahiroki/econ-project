#!/usr/bin/env python3
"""Generate and retrieve bounded, versioned economics knowledge units."""
import argparse
import ast
import hashlib
import json
import keyword
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import quote, unquote, urlsplit

SPEC_VERSION = 'knowledge-v1'
SEMANTIC_VERSION = 'knowledge-v2'
PROJECTION_VERSION = 'knowledge-runtime-v1'
FIELDS = {'id', 'title', 'chapter', 'domain', 'subdomain', 'kind', 'topic', 'use_when',
          'inputs', 'outputs', 'prerequisites', 'related', 'alternatives', 'file', 'anchor'}
LISTS = {'inputs', 'outputs', 'prerequisites', 'related', 'alternatives'}
ID = re.compile(r'[A-Z]+-[0-9]{2}')
SEMANTIC_ID = re.compile(r'(?:C|R|MC)-[A-Za-z0-9][A-Za-z0-9_-]*')
SEMANTIC_TYPES = {'prerequisite_to_understand', 'requires_to_apply', 'requires_assumption',
                  'special_case_of', 'alternative_under', 'identifies', 'estimated_by',
                  'produces', 'consumed_by', 'validated_by', 'used_for_counterfactual', 'related'}
SEMANTIC_FILES = ('lexicon.json', 'relations.json', 'model-contracts.json')
ANCHOR = re.compile(r'^<a id="([a-z]+-[0-9]{2})"></a>\s*\n\s*## ([A-Z]+-[0-9]{2})[^\S\r\n]+(.+?)\s*$', re.M)
BASE = Path(__file__).resolve().parents[1] / 'references'
# Lexical aliases only: the research owner chooses the method and IDs.
ALIASES = (
    ('graph', 'グラフ'), ('centrality', '中心性'), ('network', 'ネットワーク'),
    ('demand', '需要'), ('equilibrium', '均衡'), ('dynamic', '動学'),
    ('estimation', '推定'), ('welfare', '厚生'), ('migration', '移住'),
    ('forecast', '予測'), ('identification', '識別'), ('price', '価格'),
    ('shadow price', '影価格'), ('comparative statics', '比較静学'),
    ('cohort', '群'), ('staggered', '段階導入'), ('aggregate', '集約'),
    ('merger', '合併'), ('markup', 'マークアップ'), ('tax', '税'),
    ('externality', '外部性'), ('housing', '住宅'), ('spatial', '空間'),
    ('transport', '交通'), ('loss', '損失'), ('distribution', '分布'),
    ('ssj', 'sequence-space jacobian'), ('difference in differences', '差の差'),
    ('blp', 'ランダム係数'),
    ('iv', '操作変数'), ('instrumental variable', '操作変数'),
    ('carbon', '炭素'), ('emission', '排出'), ('emissions', '排出'),
    ('dynamic programming', 'bellman'), ('price index', '価格指数'),
    ('cost of living', '生活費'), ('valuation', '価値'),
    ('optimization', '最適化'), ('convexity', '凸'),
    ('probability', '確率'), ('statistics', '統計'), ('bayesian', 'ベイズ'), ('inference', '推論'),
    ('consumer', '消費者'), ('producer', '生産者'), ('producer', '生産'),
    ('general equilibrium', '一般均衡'),
    ('information', '情報'), ('signaling', 'シグナル'), ('signalling', 'シグナル'),
    ('persuasion', '情報開示'),
    ('heterogeneous treatment effects', '異質効果'), ('treatment', '処置'), ('dml', '直交'),
    ('competition', '競争'), ('platform', 'プラットフォーム'), ('platforms', 'プラットフォーム'),
    ('political economy', '政治'), ('law', '法'), ('crime', '犯罪'),
    ('institution', '制度'), ('institutions', '制度'),
    ('numerical', '数値'), ('simulation', 'シミュレーション'), ('monte carlo', 'モンテカルロ'),
    ('firm valuation', '企業価値'), ('open economy', '開放経済'),
    ('current account', '経常収支'), ('consumption', '消費'), ('exchange rate', '為替'),
    ('医師', '医療提供者'), ('処方', '診療'), ('炭素価格', '排出'),
    ('株式価値', '株主価値'),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def contains_term(text, term):
    """Match ASCII terms at ASCII alphanumeric boundaries; match other terms literally."""
    if not term.isascii():
        return term in text
    start = 0
    while True:
        position = text.find(term, start)
        if position < 0:
            return False
        end = position + len(term)
        left = text[position - 1] if position else ''
        right = text[end] if end < len(text) else ''
        if not (left and ('a' <= left <= 'z' or '0' <= left <= '9')) and not (
                right and ('a' <= right <= 'z' or '0' <= right <= '9')):
            return True
        start = position + 1


def lexical_words(text):
    """Normalize English inflections without conflating distinct concept labels."""
    stop = {'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'can', 'do', 'does',
            'for', 'from', 'how', 'in', 'is', 'it', 'of', 'on', 'or', 'that',
            'the', 'their', 'to', 'under', 'using', 'what', 'when', 'which', 'with'}
    words = set()
    for word in re.findall(r'[a-z0-9]+(?:-[0-9]+)?', text):
        if word in stop or len(word) < 2:
            continue
        if len(word) > 4 and word.endswith('ies'):
            word = word[:-3] + 'y'
        elif word.endswith(('ches', 'shes', 'sses', 'xes', 'zes')):
            word = word[:-2]
        elif len(word) > 3 and word.endswith('s') and not word.endswith(('ss', 'is', 'us')):
            word = word[:-1]
        words.add(word)
    return words


def lexical_scores(query, texts):
    """Rank both unit and concept text using discriminating query evidence."""
    words = lexical_words(query)
    documents = [lexical_words(text) for text in texts]
    word_weights = {word: 1 + math.log((len(texts) + 1) /
                    (1 + sum(word in document for document in documents))) for word in words}
    segments = re.findall(r'[一-龯ぁ-ゖァ-ヺー]+', query)
    particles = set('のとがをでにはへも')
    generic = {'含む', 'よる', '変化'}
    grams = {segment[i:i + width] for segment in segments for width in range(2, 7)
             for i in range(len(segment) - width + 1)
             if segment[i] not in particles and segment[i + width - 1] not in particles
             and (segment[i:i + width] not in generic or query == segment[i:i + width])}
    weights = {gram: len(gram) * (1 + math.log((len(texts) + 1) /
               (1 + sum(gram in text for text in texts)))) for gram in grams}
    scores = []
    for text, document in zip(texts, documents):
        score = 4 * sum(weight for word, weight in word_weights.items() if word in document)
        for segment in segments:
            best = [0.0] * (len(segment) + 1)
            for end in range(1, len(segment) + 1):
                best[end] = best[end - 1]
                for width in range(2, min(6, end) + 1):
                    gram = segment[end - width:end]
                    if gram in weights and gram in text:
                        best[end] = max(best[end], best[end - width] + weights[gram])
            score += best[-1]
        scores.append(score)
    return scores


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def encoded_semantic(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def local(base, name):
    p = Path(name)
    if p.is_absolute() or not p.parts or any(x in ('', '.', '..') for x in name.split('/')) or '\\' in name:
        raise ValueError(f'Unsafe path: {name}')
    path = base / p
    if any(q.is_symlink() for q in [path, *path.parents] if q != base.parent and q.is_relative_to(base)):
        raise ValueError(f'Symlink path: {name}')
    return path


def closure(ids, metadata):
    order, state = [], {}
    def visit(item):
        if item not in metadata:
            raise ValueError(f'Unknown prerequisite or ID: {item}')
        if state.get(item) == 1:
            raise ValueError(f'Cyclic prerequisites: {item}')
        if state.get(item) == 2:
            return
        state[item] = 1
        for dep in metadata[item]['prerequisites']:
            visit(dep)
        state[item] = 2
        order.append(item)
    for item in ids:
        visit(item)
    return order


def normalize_semantics(catalog, base):
    """Validate authored schema 2 and derive compatibility edges and views."""
    units = catalog['units']
    by_unit = {u['id']: u for u in units}
    if len(by_unit) != len(units):
        raise ValueError('Invalid or duplicate unit IDs')
    concepts = catalog['concepts']
    relations = catalog['relations']
    contracts = catalog['model_contracts']
    jel = catalog['jel']
    source_repository = catalog.get('source_repository')
    if (not isinstance(source_repository, dict) or set(source_repository) != {'url', 'ref'}
            or any(not isinstance(value, str) or not value.strip() for value in source_repository.values())):
        raise ValueError('Invalid canonical source repository')
    url = urlsplit(source_repository['url'])
    if (url.scheme != 'https' or not url.netloc or not url.path.strip('/')
            or url.query or url.fragment or url.username or url.password
            or not re.fullmatch(r'[A-Za-z0-9._/-]+', source_repository['ref'])
            or any(part in ('', '.', '..') for part in source_repository['ref'].split('/'))):
        raise ValueError('Invalid canonical source repository')
    if not all(isinstance(x, list) for x in (concepts, relations, contracts)) or not isinstance(jel, dict):
        raise ValueError('Invalid semantic collections')

    def strings(value, label, *, nonempty=False):
        if (not isinstance(value, list) or (nonempty and not value)
                or any(not isinstance(x, str) or not x.strip() for x in value)
                or len(set(value)) != len(value)):
            raise ValueError(f'Invalid {label}')

    def dotted_identifier(value):
        return all(part.isidentifier() and not keyword.iskeyword(part) for part in value.split('.'))

    def records(values, prefix):
        result = {}
        for item in values:
            if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                    or not item['id'].startswith(prefix + '-') or not SEMANTIC_ID.fullmatch(item['id'])
                    or item['id'] in result):
                raise ValueError(f'Invalid or duplicate {prefix} ID')
            result[item['id']] = item
        return result

    concept_map = records(concepts, 'C')
    relation_map = records(relations, 'R')
    contract_map = records(contracts, 'MC')
    if not concept_map or not jel:
        raise ValueError('Concepts and JEL mapping are required')
    if any(not isinstance(code, str) or not re.fullmatch(r'[A-Z](?:[0-9]{1,2})?', code) or not isinstance(value, dict)
           or set(value) != {'en', 'ja', 'provenance_url'}
           or any(not isinstance(label, str) or not label.strip() for label in value.values())
           or not re.match(r'^https?://', value['provenance_url'])
           for code, value in jel.items()):
        raise ValueError('Invalid JEL mapping')

    def locator(value):
        if (not isinstance(value, dict) or set(value) != {'unit', 'anchor'}
                or value['unit'] not in by_unit or value['anchor'] != by_unit[value['unit']]['anchor']):
            raise ValueError('Invalid semantic body locator')

    for concept in concepts:
        required = {'id', 'preferred', 'aliases', 'broader', 'definition', 'jel_codes'}
        if (not required <= set(concept) or set(concept) - required - {'kind'}
                or not isinstance(concept.get('kind', 'concept'), str)
                or concept.get('kind', 'concept') not in {'classification', 'concept', 'method', 'object', 'assumption'}):
            raise ValueError('Invalid concept fields')
        if (not isinstance(concept['preferred'], dict) or set(concept['preferred']) != {'en', 'ja'}
                or any(not isinstance(x, str) or not x.strip() for x in concept['preferred'].values())
                or not isinstance(concept['aliases'], dict) or set(concept['aliases']) != {'en', 'ja'}):
            raise ValueError('Invalid concept labels')
        for aliases in concept['aliases'].values(): strings(aliases, 'concept aliases')
        strings(concept['broader'], 'broader concepts')
        strings(concept['jel_codes'], 'concept JEL codes')
        if (set(concept['broader']) - concept_map.keys() or concept['id'] in concept['broader']
                or set(concept['jel_codes']) - jel.keys()):
            raise ValueError('Invalid concept references')
        locator(concept['definition'])

    # A taxonomy edge points to its broader concept. This graph, unlike the
    # general typed-relation graph, must be acyclic.
    closure(sorted(concept_map), {key: {'prerequisites': value['broader']}
                                  for key, value in concept_map.items()})
    narrower = {key: [] for key in concept_map}
    for concept in concepts:
        for parent in concept['broader']: narrower[parent].append(concept['id'])
    concept_views = [{'kind': concept.get('kind', 'concept'), **concept,
                      'narrower': sorted(narrower[concept['id']])} for concept in concepts]
    for unit in units:
        if set(unit) != (FIELDS - {'prerequisites', 'related', 'alternatives'}) | {'concept_ids', 'jel_codes', 'contract_ids'}:
            raise ValueError(f'Invalid schema 2 unit fields: {unit.get("id")}')
        for key in ('concept_ids', 'jel_codes', 'contract_ids'):
            strings(unit[key], key, nonempty=key != 'contract_ids')
        if (set(unit['concept_ids']) - concept_map.keys() or set(unit['jel_codes']) - jel.keys()
                or set(unit['contract_ids']) - contract_map.keys()):
            raise ValueError(f'Invalid semantic references: {unit["id"]}')

    project = (base.parents[2] if base.name == 'references' and base.parent.name == 'econ-knowledge'
               and base.parent.parent.name == 'skills' else None)
    registry_paths = {}
    if project and (project / 'registry/resources.json').is_file():
        registry = json.loads(local(project, 'registry/resources.json').read_bytes())
        for rid, record in registry['resources'].items():
            path = record['source_path']
            if path in registry_paths:
                raise ValueError('Duplicate registered source path: ' + path)
            registry_paths[path] = (rid, bool(record.get('source_distribution_only')))
    contract_views = []
    for contract in contracts:
        projected = {**contract, **{key: [] for key in ('implementation', 'checks', 'results')}}
        expected = {'id', 'owner', 'units', 'inputs', 'parameters', 'outputs', 'assumptions',
                    'identification', 'equations', 'implementation', 'checks', 'results', 'counterfactual_inputs'}
        if set(contract) != expected or contract['owner'] not in by_unit:
            raise ValueError('Invalid model contract')
        strings(contract['units'], 'contract units', nonempty=True)
        strings(contract['counterfactual_inputs'], 'counterfactual inputs')
        if set(contract['units']) - by_unit.keys() or contract['owner'] not in contract['units']:
            raise ValueError('Invalid contract unit references')
        for key in ('assumptions', 'identification', 'equations'):
            if not isinstance(contract[key], list): raise ValueError(f'Invalid {key}')
            for body in contract[key]: locator(body)
        for key in ('inputs', 'outputs', 'parameters', 'implementation', 'checks', 'results'):
            if not isinstance(contract[key], list): raise ValueError(f'Invalid {key}')
            fields = ({'name', 'unit', 'meaning'} if key in ('inputs', 'outputs') else
                      {'name', 'meaning'} if key == 'parameters' else
                      {'path', 'meaning'} if key == 'results' else {'path', 'symbol'})
            for row in contract[key]:
                valid_fields = (isinstance(row, dict) and (set(row) == fields or
                                (key == 'implementation' and set(row) == {'module', 'symbol', 'version'})))
                if (not valid_fields
                        or any(not isinstance(v, str) or not v.strip() for v in row.values())):
                    raise ValueError(f'Invalid {key} record')
                if 'symbol' in row and not dotted_identifier(row['symbol']):
                    raise ValueError('Invalid contract symbol')
                if 'module' in row:
                    if not dotted_identifier(row['module']):
                        raise ValueError('Invalid contract module')
                    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*(?:[._-]?(?:a|b|rc|post|dev)[._-]?[0-9]+)?(?:\+[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*)?', row['version']):
                        raise ValueError('Invalid pinned module version')
                if 'path' in row:
                    path = row['path']
                    if (Path(path).is_absolute() or any(part in ('', '.', '..') for part in path.split('/'))
                            or '\\' in path):
                        raise ValueError('Unsafe contract path')
                    if project is None:
                        raise ValueError('Contract source paths require the canonical project')
                    target = local(project, path)
                    if not target.is_file(): raise ValueError(f'Missing contract path: {path}')
                    raw = target.read_bytes()
                    if 'symbol' in row and target.suffix == '.py':
                        nodes = ast.parse(raw.decode('utf-8')).body
                        for part in row['symbol'].split('.'):
                            found = next((node for node in nodes if isinstance(node, (ast.FunctionDef,
                                          ast.AsyncFunctionDef, ast.ClassDef)) and node.name == part), None)
                            if not found: raise ValueError(f'Unknown contract symbol: {path}:{row["symbol"]}')
                            nodes = found.body
                    descriptor = {**row, 'path_scope': 'canonical_source', 'source_sha256': sha(raw),
                                  'source_url': (source_repository['url'].rstrip('/') + '/blob/' +
                                      quote(source_repository['ref'], safe='') + '/' + quote(path, safe='/'))}
                    if key == 'implementation':
                        registered = registry_paths.get(path)
                        source_only = registered is None or registered[1]
                        descriptor.update(role='executable_example_provenance' if source_only else 'execution_binding',
                                          source_only=source_only, execution_owner='econ-data')
                        if source_only: descriptor['runtime_required'] = False
                        if registered: descriptor['resource_id'] = registered[0]
                    else:
                        descriptor.update(role='validation_provenance', runtime_required=False)
                    projected[key].append(descriptor)
                elif key == 'implementation':
                    projected[key].append({**row, 'role': 'execution_binding', 'source_only': False,
                                           'execution_owner': 'econ-data'})
        contract_views.append(projected)
    for unit in units:
        if any(unit['id'] not in contract_map[x]['units'] for x in unit['contract_ids']):
            raise ValueError('Contract unit mismatch')
    if any(contract['id'] not in by_unit[contract['owner']]['contract_ids'] for contract in contracts):
        raise ValueError('Contract missing from owner')

    normalized = {u['id']: {**u, 'prerequisites': [], 'related': [], 'alternatives': []} for u in units}
    endpoint_ids = by_unit.keys() | concept_map.keys() | contract_map.keys()
    by_source, by_target = {}, {}
    for relation in relations:
        expected = {'id', 'source', 'target', 'type', 'conditions', 'when', 'use', 'evidence', 'version'}
        if (set(relation) != expected or relation['source'] not in endpoint_ids
                or relation['target'] not in endpoint_ids or relation['source'] == relation['target']
                or relation['type'] not in SEMANTIC_TYPES
                or not isinstance(relation['use'], str) or not relation['use'].strip()
                or not isinstance(relation['version'], str) or not relation['version'].strip()):
            raise ValueError('Invalid semantic relation')
        strings(relation['conditions'], 'relation conditions')
        selectors = relation['when']
        if (not isinstance(selectors, dict) or bool(selectors) != bool(relation['conditions'])
                or any(not isinstance(key, str) or not key.strip() for key in selectors)):
            raise ValueError('Invalid relation conditions or selectors')
        for choices in selectors.values(): strings(choices, 'relation selector values', nonempty=True)
        if not isinstance(relation['evidence'], list) or not relation['evidence']:
            raise ValueError('Relation requires body evidence')
        for evidence in relation['evidence']: locator(evidence)
        source, target, kind = relation['source'], relation['target'], relation['type']
        if kind == 'prerequisite_to_understand':
            if selectors or source not in by_unit or target not in by_unit:
                raise ValueError('Understanding prerequisites must be unconditional unit edges')
            normalized[source]['prerequisites'].append(target)
        elif not selectors and source in by_unit and target in by_unit:
            if kind == 'related': normalized[source]['related'].append(target)
            if kind == 'alternative_under': normalized[source]['alternatives'].append(target)
        by_source.setdefault(source, []).append(relation['id'])
        by_target.setdefault(target, []).append(relation['id'])
    for unit in normalized.values():
        for key in ('prerequisites', 'related', 'alternatives'):
            if len(unit[key]) != len(set(unit[key])): raise ValueError(f'Duplicate {key} edge')
    closure(sorted(normalized), normalized)
    assets = {
        'lexicon.json': encoded_semantic({'spec_version': SEMANTIC_VERSION, 'concepts': concept_views, 'jel': jel}),
        'relations.json': encoded_semantic({'spec_version': SEMANTIC_VERSION, 'relations': relations,
                                   'by_source': by_source, 'by_target': by_target}),
        'model-contracts.json': encoded_semantic({'spec_version': SEMANTIC_VERSION, 'contracts': contract_views}),
    }
    return list(normalized.values()), assets


def project_unit_links(text, chapter_path, project, repository):
    """Project source-relative Markdown destinations without changing body text."""
    masked = list(text)
    def conceal(start, end):
        for index in range(start, end):
            if masked[index] not in '\r\n': masked[index] = ' '

    # Mask fenced blocks before inline code and math so their delimiters do not
    # change the interpretation of later prose.
    fence, offset = None, 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)', line)
        if fence:
            conceal(offset, offset + len(line))
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}[ \t]*[\r\n]*', line):
                fence = None
        elif marker:
            fence = marker.group(1)
            conceal(offset, offset + len(line))
        elif line.startswith(('    ', '\t')):
            conceal(offset, offset + len(line))
        offset += len(line)
    view = ''.join(masked)
    position = 0
    while position < len(view):
        if view[position] != '`' or (position and view[position - 1] == '\\'):
            position += 1
            continue
        end = position
        while end < len(view) and view[end] == '`': end += 1
        width, search = end - position, end
        while search < len(view):
            candidate = view.find('`', search)
            if candidate < 0: break
            stop = candidate
            while stop < len(view) and view[stop] == '`': stop += 1
            if stop - candidate == width:
                conceal(position, stop)
                position = stop
                break
            search = stop
        else:
            candidate = -1
        if candidate < 0 or search >= len(view): position = end
    view = ''.join(masked)
    math_spans = re.compile(r'(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?!\$)(?:(?!\r?\n[ \t]*\r?\n)[\s\S])*?(?<!\\)\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]')
    for match in math_spans.finditer(view): conceal(match.start(), match.end())
    view = ''.join(masked)
    direct = re.compile(r'(?<!\\)\[(?:\\.|[^\]\r\n])+\]\([ \t\n]*')
    definition = re.compile(r'^ {0,3}\[(?!\^)[^\]\r\n]+\]:[ \t]*', re.M)
    changes = []
    for match in sorted([*direct.finditer(view), *definition.finditer(view)], key=lambda item: item.start()):
        start = match.end()
        if start >= len(view): continue
        if view[start] == '<':
            end = view.find('>', start + 1)
            if end < 0 or '\n' in view[start:end]: continue
            start, after = start + 1, end + 1
        else:
            end, depth = start, 0
            while end < len(view):
                char = view[end]
                if char.isspace() and depth == 0: break
                if char == '(': depth += 1
                elif char == ')':
                    if depth == 0: break
                    depth -= 1
                end += 1
            if depth or end == start: continue
            after = end
        if match.re is direct and not re.match(r'''\s*(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\((?:[^)\\]|\\.)*\))?\s*\)''', view[after:]):
            continue
        value = text[start:end]
        parts = urlsplit(value)
        if parts.scheme or parts.netloc or not parts.path: continue
        decoded = unquote(parts.path)
        if (project is None or '\\' in decoded or Path(decoded).is_absolute()
                or any(ord(char) < 32 or ord(char) == 127 for char in decoded)):
            raise ValueError('Unsafe knowledge link: ' + value)
        target = Path(os.path.abspath(chapter_path.parent / decoded))
        if not target.is_relative_to(project): raise ValueError('Knowledge link escapes project: ' + value)
        relative = target.relative_to(project).as_posix()
        if not local(project, relative).is_file(): raise ValueError('Missing knowledge link target: ' + value)
        url = (repository['url'].rstrip('/') + '/blob/' + quote(repository['ref'], safe='') + '/' +
               quote(relative, safe='/'))
        if parts.query: url += '?' + parts.query
        if parts.fragment: url += '#' + quote(unquote(parts.fragment), safe='-._~')
        changes.append((start, end, url))
    for start, end, url in reversed(changes): text = text[:start] + url + text[end:]
    return text


def generate(base, *, strict=True):
    catalog_raw = local(base, 'catalog.json').read_bytes()
    catalog = json.loads(catalog_raw)
    chapters, units = catalog['chapters'], catalog['units']
    schema = catalog.get('schema_version', 1)
    if schema not in (1, 2): raise ValueError('Unsupported knowledge catalog schema')
    semantic_assets = {}
    if schema == 2:
        if any(set(chapter) & {'prerequisites', 'related', 'alternatives'} for chapter in chapters):
            raise ValueError('Schema 2 chapter contains legacy edge fields')
        units, semantic_assets = normalize_semantics(catalog, base)
    version = SEMANTIC_VERSION if schema == 2 else SPEC_VERSION
    if strict and (not chapters or not units):
        raise ValueError('Knowledge collection must contain chapters and units')
    counts = {'chapter_count': len(chapters), 'unit_count': len(units),
              'worked_example_unit_count': sum(u.get('kind') == 'worked_example' for u in units)}
    for name, count in counts.items():
        if name in catalog and (type(catalog[name]) is not int or catalog[name] != count):
            raise ValueError(f'Incorrect catalog {name}')
    metadata = {}
    for u in units:
        fields = FIELDS | ({'concept_ids', 'jel_codes', 'contract_ids'} if schema == 2 else set())
        if set(u) != fields or not ID.fullmatch(u.get('id', '')) or u['id'] in metadata:
            raise ValueError(f'Invalid or duplicate metadata: {u.get("id")}')
        for k in FIELDS - LISTS - {'chapter'}:
            if not isinstance(u[k], str) or not u[k].strip():
                raise ValueError(f'Invalid {k}: {u["id"]}')
        for k in LISTS:
            if not isinstance(u[k], list) or any(not isinstance(v, str) or not v.strip() for v in u[k]) or len(set(u[k])) != len(u[k]):
                raise ValueError(f'Invalid {k}: {u["id"]}')
        if u['anchor'] != u['id'].lower() or u['kind'] not in ('knowledge', 'worked_example'):
            raise ValueError(f'Invalid anchor or kind: {u["id"]}')
        metadata[u['id']] = u
    for u in units:
        for key in ('prerequisites', 'related', 'alternatives'):
            if set(u[key]) - metadata.keys() or u['id'] in u[key]:
                raise ValueError(f'Invalid {key} references: {u["id"]}')
    closure(sorted(metadata), metadata)
    files, chapter_hashes, seen_chapters, seen_units, domains = {}, {}, set(), set(), {}
    for chapter in chapters:
        number, path = chapter['id'], chapter['file']
        if number in seen_chapters or not isinstance(number, int) or not re.fullmatch(r'chapters/[a-z0-9-]+\.md', path) or path in chapter_hashes or not chapter['units']:
            raise ValueError(f'Invalid chapter: {number}')
        seen_chapters.add(number)
        raw = local(base, path).read_bytes()
        chapter_hashes[path] = sha(raw)
        text = raw.decode('utf-8')
        matches = list(ANCHOR.finditer(text))
        chapter_ids = [m.group(2) for m in matches]
        if chapter_ids != chapter['units'] or len(set(chapter_ids)) != len(chapter_ids):
            raise ValueError(f'Chapter IDs or headings do not match catalog: {path}')
        for pos, match in enumerate(matches):
            item = match.group(2)
            u = metadata.get(item)
            if not u or item in seen_units or u['chapter'] != number or u['file'] != path or match.group(1) != u['anchor'] or match.group(3).strip() != u['title']:
                raise ValueError(f'Body/metadata mismatch: {item}')
            seen_units.add(item)
            end = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
            body = text[match.start():end]
            if schema == 2:
                project = (base.resolve().parents[2] if base.name == 'references' and base.parent.name == 'econ-knowledge'
                           and base.parent.parent.name == 'skills' else None)
                body = project_unit_links(body, local(base, path), project, catalog['source_repository'])
            body = body.encode('utf-8')
            files[f'units/{item}.md'] = body
            domains.setdefault(u['domain'], []).append(u)
    if seen_units != metadata.keys():
        raise ValueError('Catalog units do not match chapter bodies')
    domain_map, unit_map = {}, {}
    for number, (domain, entries) in enumerate(sorted(domains.items()), 1):
        name = f'domains/{number:02d}.json'
        data = encoded({'domain': domain, 'units': sorted(entries, key=lambda u: u['id'])})
        files[name] = data
        domain_map[domain] = {'path': name, 'sha256': sha(data), 'count': len(entries)}
        for u in entries:
            unit_map[u['id']] = {'domain': domain, 'path': f'units/{u["id"]}.md',
                                  'sha256': sha(files[f'units/{u["id"]}.md']), 'chapter': u['file']}
    files.update(semantic_assets)
    domain_listing = encoded({'spec_version': version, 'domains': [
        {'domain': domain, 'path': record['path'], 'sha256': record['sha256']}
        for domain, record in domain_map.items()]})
    files['domains.json'] = domain_listing
    manifest = {'spec_version': version, 'catalog_sha256': sha(catalog_raw), 'chapters': chapter_hashes,
                'domain_listing_sha256': sha(domain_listing), 'domains': domain_map, 'units': unit_map}
    if schema == 2:
        manifest['semantic_assets'] = {name: {'path': name, 'sha256': sha(data)}
                                       for name, data in semantic_assets.items()}
    files['manifest.json'] = encoded(manifest)
    return files


def build(base, check=False, *, strict=True, return_files=False):
    files = generate(base, strict=strict)
    expected = set(files)
    actual = {p.relative_to(base).as_posix() for d in ('units', 'domains') if (base / d).exists() for p in (base / d).rglob('*') if p.is_file()}
    for name in ('manifest.json', 'domains.json', *SEMANTIC_FILES):
        if (base / name).is_file(): actual.add(name)
    if check:
        if actual != expected or any(local(base, p).read_bytes() != data for p, data in files.items()):
            raise ValueError('Generated knowledge files are missing or stale')
    else:
        if actual - expected:
            raise ValueError('Unexpected generated files; inspect before regeneration')
        # Generate and validate all bytes before replacing any destination.
        for name, data in files.items():
            path = local(base, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
                temp = f.name
                f.write(data)
            try: os.replace(temp, path)
            finally:
                if os.path.exists(temp): os.unlink(temp)
    summary = {'spec_version': json.loads(files['manifest.json'])['spec_version'],
               'files': len(files), 'manifest_sha256': sha(files['manifest.json'])}
    return (summary, files) if return_files else summary


class Reader:
    def __init__(self, base):
        self.base = base
        self.files = {}
        self.contents = {}
        self.manifest = json.loads(self.read('manifest.json'))
        self.spec_version = self.manifest['spec_version']
        if self.spec_version not in (SPEC_VERSION, SEMANTIC_VERSION):
            raise ValueError('Knowledge specification version mismatch')
        projection_path = local(base, 'runtime.json')
        self.projection = projection_path.exists()
        if self.projection:
            projection = json.loads(self.read('runtime.json'))
            chapters = local(base, 'chapters')
            if (projection != {'projection_version': PROJECTION_VERSION,
                               'manifest_sha256': sha(self.contents['manifest.json'])}
                    or local(base, 'catalog.json').exists()
                    or (chapters.exists() and (not chapters.is_dir() or any(chapters.iterdir())))):
                raise ValueError('Invalid or mixed knowledge runtime projection')
        elif sha(self.read('catalog.json')) != self.manifest['catalog_sha256']:
            raise ValueError('Stale knowledge catalog')
        self.indexes = {}
        self.selection = None
        selection_path = local(base, 'selection.json')
        if selection_path.exists():
            selection = json.loads(self.read('selection.json'))
            if (set(selection) != {'spec_version', 'manifest_sha256', 'selected_ids', 'closure_ids'}
                    or selection['spec_version'] != self.spec_version
                    or selection['manifest_sha256'] != sha(self.contents['manifest.json'])
                    or any(not isinstance(selection[key], list) or not selection[key]
                           or any(not isinstance(item, str) for item in selection[key])
                           or len(set(selection[key])) != len(selection[key])
                           for key in ('selected_ids', 'closure_ids'))
                    or set(selection['closure_ids']) - self.manifest['units'].keys()
                    or set(selection['selected_ids']) - set(selection['closure_ids'])):
                raise ValueError('Invalid knowledge selection manifest')
            self.selection = selection

    def read(self, path, expected=None):
        if path not in self.contents:
            self.contents[path] = local(self.base, path).read_bytes()
        data = self.contents[path]
        if expected and sha(data) != expected:
            raise ValueError(f'Stale knowledge file: {path}')
        self.files[path] = len(data)
        return data

    def index(self, domain):
        if domain not in self.indexes:
            if self.selection and domain not in {self.manifest['units'][item]['domain'] for item in self.selection['closure_ids']}:
                raise ValueError(f'Domain outside exported selection: {domain}')
            if domain not in self.manifest['domains']:
                raise ValueError(f'Unknown domain: {domain}')
            record = self.manifest['domains'][domain]
            index = json.loads(self.read(record['path'], record['sha256']))
            if index['domain'] != domain:
                raise ValueError('Domain index mismatch')
            self.indexes[domain] = {u['id']: u for u in index['units']}
        return self.indexes[domain]

    def metadata(self, item):
        info = self.manifest['units'].get(item)
        if not info:
            raise ValueError(f'Unknown knowledge ID: {item}')
        result = self.index(info['domain']).get(item)
        if not result: raise ValueError(f'Missing indexed ID: {item}')
        return result

    def report(self):
        return {'files': [{'path': k, 'bytes': v} for k, v in self.files.items()],
                'bytes': sum(self.files.values()), 'spec_version': self.spec_version,
                'manifest_sha256': sha(self.contents['manifest.json']),
                'catalog_sha256': self.manifest['catalog_sha256']}

    def domains(self):
        listing = json.loads(self.read('domains.json', self.manifest['domain_listing_sha256']))
        if listing['spec_version'] != self.spec_version:
            raise ValueError('Domain listing specification version mismatch')
        return {**listing, **self.report()}

    def search(self, domain, query, limit):
        if not 1 <= limit <= 20 or not query.strip(): raise ValueError('Use a nonempty query and limit 1..20')
        normalized = unicodedata.normalize('NFKC', query).casefold()
        exact_ids = {term.upper() for term in re.findall(r'[a-z0-9]+(?:-[0-9]+)?', normalized)
                     if ID.fullmatch(term.upper())}
        concept_labels, classifications, matched_concepts = {}, {}, {}
        if self.spec_version == SEMANTIC_VERSION:
            visible = self.visible_concepts()
            for concept in self.semantic('lexicon.json')['concepts']:
                if visible is not None and concept['id'] not in visible:
                    continue
                labels = [*concept['preferred'].values(), *concept['aliases']['en'], *concept['aliases']['ja']]
                target = classifications if concept.get('kind', 'concept') == 'classification' else concept_labels
                target[concept['id']] = sorted({unicodedata.normalize('NFKC', value).casefold() for value in labels})
                matches = [label for label in target[concept['id']] if contains_term(normalized, label)]
                if matches and target is concept_labels:
                    matched_concepts[concept['id']] = {'id': concept['id'], 'labels': matches,
                                                     'definition': concept['definition']}
            expanded = set()
        else:
            expanded = {target for source, target in ALIASES if contains_term(normalized, source)}
        if domain is not None:
            domains = [domain]
        elif self.selection:
            domains = sorted({self.manifest['units'][item]['domain']
                              for item in self.selection['closure_ids']})
        else:
            domains = sorted(self.manifest['domains'])
        candidates = [u for selected_domain in domains
                      for u in self.index(selected_domain).values()
                      if not self.selection or u['id'] in self.selection['closure_ids']]
        def corpus(u):
            fields = (u['id'], u['title'], u['domain'], u['subdomain'], u['topic'], u['use_when'],
                      *u['inputs'], *u['outputs'],
                      *(label for concept in u.get('concept_ids', []) for label in concept_labels.get(concept, [])))
            return unicodedata.normalize('NFKC', ' '.join(fields)).casefold()
        indexed = [(u, corpus(u)) for u in candidates]
        scores = lexical_scores(normalized, [text for _, text in indexed])
        field_scores = lexical_scores(normalized, [' '.join(label for concept in u.get('concept_ids', [])
                         for label in classifications.get(concept, [])) for u in candidates])
        concept_weights = {cid: 4 * (1 + math.log((len(candidates) + 1) /
                           (1 + sum(cid in u.get('concept_ids', []) for u in candidates))))
                           for cid in matched_concepts}
        ranked = []
        for (u, text), primary, field_score in zip(indexed, scores, field_scores):
            # A concept contributes once, irrespective of its number of aliases.
            primary += sum(concept_weights[cid] for cid in u.get('concept_ids', []) if cid in matched_concepts)
            primary += 4 * sum(contains_term(text, term) for term in expanded)
            defining = sum(match['definition']['unit'] == u['id'] for match in matched_concepts.values())
            ranked.append(((u['id'] in exact_ids, primary > 0, primary, defining, field_score), u))
        candidates = [u for rank, u in sorted(ranked, key=lambda row: (row[0], row[1]['id']), reverse=True)
                      if any(rank)]
        return {'domain': domain, 'query': query, 'candidates': candidates[:limit],
                'matched_concepts': list(matched_concepts.values()),
                'truncated': len(candidates) > limit, **self.report()}

    def semantic(self, name):
        if self.spec_version != SEMANTIC_VERSION:
            raise ValueError('Semantic views require knowledge-v2')
        if name not in SEMANTIC_FILES:
            raise ValueError(f'Unknown semantic view: {name}')
        record = self.manifest['semantic_assets'][name]
        if record['path'] != name:
            raise ValueError('Invalid semantic asset path')
        value = json.loads(self.read(name, record['sha256']))
        if value['spec_version'] != self.spec_version:
            raise ValueError('Semantic view specification version mismatch')
        return value

    def visible_concepts(self):
        if not self.selection: return None
        return {concept for item in self.selection['closure_ids']
                for concept in self.metadata(item)['concept_ids']}

    def concepts(self, query, limit=8):
        if not query.strip() or not 1 <= limit <= 20:
            raise ValueError('Use a nonempty query and limit 1..20')
        lexicon = self.semantic('lexicon.json')
        visible = self.visible_concepts()
        normalized = unicodedata.normalize('NFKC', query).casefold()
        candidates, texts, matches = [], [], []
        for concept in lexicon['concepts']:
            if visible is not None and concept['id'] not in visible: continue
            labels = [concept['id'], *concept['preferred'].values(),
                      *concept['aliases']['en'], *concept['aliases']['ja']]
            labels = [unicodedata.normalize('NFKC', label).casefold() for label in labels]
            matched = [label for label in labels if contains_term(normalized, label)]
            candidates.append(concept)
            matches.append((normalized in labels, matched))
            texts.append(' '.join(labels))
        rows = []
        for concept, score, (exact, matched) in zip(candidates, lexical_scores(normalized, texts), matches):
            if score or matched:
                row = dict(concept)
                row['matched_labels'] = matched
                row['jel'] = {code: lexicon['jel'][code] for code in concept['jel_codes']}
                row['definition'] = {**concept['definition'], 'body_readable': not self.selection
                                     or concept['definition']['unit'] in self.selection['closure_ids']}
                if visible is not None:
                    row['broader'] = [x for x in row['broader'] if x in visible]
                    row['narrower'] = [x for x in row['narrower'] if x in visible]
                rows.append(((exact, bool(matched), score), row))
        rows.sort(key=lambda value: (value[0], value[1]['id']), reverse=True)
        return {'query': query, 'concepts': [row for _, row in rows[:limit]],
                'truncated': len(rows) > limit, **self.report()}

    @staticmethod
    def relation_state(relation, context):
        selectors = relation['when']
        if not selectors: return 'satisfied'
        if any(key in context and context[key] not in values for key, values in selectors.items()):
            return 'inapplicable'
        if any(key not in context for key in selectors): return 'unresolved'
        return 'satisfied'

    def semantic_available(self, item):
        if not self.selection: return True
        if item in self.manifest['units']:
            return item in self.selection['closure_ids']
        if item.startswith('C-'):
            return item in self.visible_concepts()
        if item.startswith('MC-'):
            return any(contract['id'] == item and contract['owner'] in self.selection['closure_ids']
                       for contract in self.semantic('model-contracts.json')['contracts'])
        return False

    def check_semantic_id(self, item):
        if item in self.manifest['units']:
            if self.selection and item not in self.selection['closure_ids']:
                raise ValueError(f'Knowledge ID outside exported selection: {item}')
            return
        if item.startswith('C-') and item in {entry['id'] for entry in self.semantic('lexicon.json')['concepts']}:
            visible = self.visible_concepts()
            if visible is not None and item not in visible:
                raise ValueError(f'Concept outside exported selection: {item}')
            return
        contract = next((entry for entry in self.semantic('model-contracts.json')['contracts']
                         if entry['id'] == item), None) if item.startswith('MC-') else None
        if contract:
            if self.selection and contract['owner'] not in self.selection['closure_ids']:
                raise ValueError(f'Contract outside exported selection: {item}')
            return
        raise ValueError(f'Unknown semantic ID: {item}')

    def relations(self, ids, types=(), context=None):
        context = context or {}
        if not ids or set(types) - (SEMANTIC_TYPES | {'generalizes'}):
            raise ValueError('Specify semantic IDs and known relation types')
        graph = self.semantic('relations.json')
        for item in ids: self.check_semantic_id(item)
        edges = {edge['id']: edge for edge in graph['relations']}
        rows = []
        for item in ids:
            for direction, adjacency in (('outgoing', graph['by_source']), ('incoming', graph['by_target'])):
                for edge_id in adjacency.get(item, []):
                    edge = edges[edge_id]
                    inverse = direction == 'incoming' and edge['type'] == 'special_case_of'
                    if types and edge['type'] not in types and not (inverse and 'generalizes' in types):
                        continue
                    row = {**edge, 'queried_id': item, 'direction': direction,
                           'condition_state': self.relation_state(edge, context),
                           'source_available': self.semantic_available(edge['source']),
                           'target_available': self.semantic_available(edge['target'])}
                    if inverse:
                        row['inverse_type'] = 'generalizes'
                    rows.append(row)
        return {'ids': ids, 'relations': rows, **self.report()}

    def contract(self, item):
        contracts = self.semantic('model-contracts.json')
        contract = next((entry for entry in contracts['contracts'] if entry['id'] == item), None)
        if contract is None: raise ValueError(f'Unknown contract: {item}')
        if self.selection and contract['owner'] not in self.selection['closure_ids']:
            raise ValueError(f'Contract outside exported selection: {item}')
        result = dict(contract)
        result['unit_locators'] = [{'id': unit, 'body_readable': self.semantic_available(unit)}
                                   for unit in contract['units']]
        for key in ('assumptions', 'identification', 'equations'):
            result[key] = [{**locator, 'body_readable': not self.selection
                            or locator['unit'] in self.selection['closure_ids']} for locator in contract[key]]
        return result

    def plan(self, selected, context=None):
        context = context or {}
        graph = self.semantic('relations.json')
        contracts = self.semantic('model-contracts.json')
        if not selected: raise ValueError('Specify at least one knowledge ID')
        for item in selected:
            if item not in self.manifest['units']: raise ValueError(f'Unknown knowledge ID: {item}')
            if self.selection and item not in self.selection['closure_ids']:
                raise ValueError(f'Knowledge ID outside exported selection: {item}')
        edges = {edge['id']: edge for edge in graph['relations']}
        required, visiting, completed, cycles = [], set(), set(), []
        eligible, unresolved = {}, {}
        def visit(item):
            if item in visiting:
                cycles.append(item)
                return
            if item in completed: return
            visiting.add(item)
            for edge_id in graph['by_source'].get(item, []):
                edge = edges[edge_id]
                state = self.relation_state(edge, context)
                annotated = {**edge, 'target_available': self.semantic_available(edge['target'])}
                if state == 'satisfied': eligible[edge_id] = annotated
                elif state == 'unresolved': unresolved[edge_id] = annotated
                if (edge['type'] in ('prerequisite_to_understand', 'requires_to_apply')
                        and state == 'satisfied' and edge['target'] in self.manifest['units']):
                    visit(edge['target'])
            visiting.remove(item)
            completed.add(item)
            required.append(item)
        for item in selected: visit(item)
        # An alternative is one authored symmetric comparison. Its reverse
        # lookup supplies the same conditions without creating a dependency.
        for item in required:
            for edge_id in graph['by_target'].get(item, []):
                edge = edges[edge_id]
                if edge['type'] != 'alternative_under':
                    continue
                state = self.relation_state(edge, context)
                annotated = {**edge, 'source_available': self.semantic_available(edge['source']),
                             'target_available': self.semantic_available(edge['target'])}
                if state == 'satisfied': eligible[edge_id] = annotated
                elif state == 'unresolved': unresolved[edge_id] = annotated
        selected_contracts = [self.contract(contract['id']) for contract in contracts['contracts']
                              if contract['owner'] in required and (not self.selection
                                 or contract['owner'] in self.selection['closure_ids'])]
        locators = [{'id': item, 'path': self.manifest['units'][item]['path'],
                     'body_readable': not self.selection or item in self.selection['closure_ids']}
                    for item in required]
        return {'selected_ids': selected, 'required_ids': required, 'locators': locators,
                'eligible_relations': list(eligible.values()), 'unresolved_conditions': list(unresolved.values()),
                'application_cycles': cycles,
                'contracts': selected_contracts, **self.report()}

    def units(self, selected, cached=None):
        order, visiting, done = [], set(), set()
        def visit(item):
            if self.selection and item not in self.selection['closure_ids']:
                raise ValueError(f'Knowledge ID outside exported selection: {item}')
            if item in visiting: raise ValueError(f'Cyclic prerequisites: {item}')
            if item in done: return
            visiting.add(item)
            for dep in self.metadata(item)['prerequisites']: visit(dep)
            visiting.remove(item); done.add(item); order.append(item)
        if self.selection:
            for item in self.selection['selected_ids']: visit(item)
            if order != self.selection['closure_ids']:
                raise ValueError('Knowledge selection prerequisite closure mismatch')
            order.clear(); done.clear()
        for item in selected: visit(item)
        values, omitted = [], []
        manifest_sha256 = sha(self.contents['manifest.json'])
        for item in order:
            info = self.manifest['units'][item]
            if not self.projection:
                self.read(info['chapter'], self.manifest['chapters'][info['chapter']])
            version = {'body_sha256': info['sha256'], 'catalog_sha256': self.manifest['catalog_sha256'],
                       'manifest_sha256': manifest_sha256, 'spec_version': self.spec_version}
            body = self.read(info['path'], info['sha256']).decode('utf-8')
            if cached and cached.get(item, {}).get('version') == version:
                saved = cached[item]
                if sha(saved['body'].encode('utf-8')) != info['sha256']:
                    raise ValueError(f'Corrupt cached body: {item}')
                omitted.append(item)
                values.append({'id': item, 'metadata': self.metadata(item), 'path': info['path'], 'version': version, 'reused': True, 'cache_output': 'knowledge:' + item})
                continue
            values.append({'id': item, 'metadata': self.metadata(item), 'path': info['path'], 'version': version, 'body': body, 'reused': False})
        return {'selected_ids': selected, 'closure_ids': order, 'read_ids': [v['id'] for v in values if not v['reused']],
                'omitted_ids': omitted, 'units': values, **self.report()}


def state_helper():
    """Resolve the state helper packaged with this script's declared layout."""
    script = Path(__file__).resolve()
    if (script.parent.name == 'scripts' and script.parent.parent.name == 'econ-knowledge'
            and script.parent.parent.parent.name == 'skills'):
        helper = script.parents[3] / 'harness/state.py'
    else:
        helper = script.parent / 'state.py'
    if not helper.is_file():
        raise ValueError(f'Missing state helper for knowledge package: {helper}')
    return helper


def parse_context(values):
    result = {}
    for value in values:
        key, separator, item = value.partition('=')
        if not separator or not key.strip() or not item.strip() or key in result:
            raise ValueError('Use distinct nonempty --context KEY=VALUE entries')
        result[key] = item
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE)
    sub = parser.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build'); b.add_argument('--check', action='store_true')
    sub.add_parser('domains')
    s = sub.add_parser('search'); s.add_argument('--domain'); s.add_argument('--query', required=True); s.add_argument('--limit', type=int, default=8)
    r = sub.add_parser('read'); r.add_argument('ids', nargs='+'); r.add_argument('--task'); r.add_argument('--root', type=Path, default=Path.cwd()); r.add_argument('--store', default='.agents/state/team.json')
    c = sub.add_parser('concepts'); c.add_argument('--query', required=True); c.add_argument('--limit', type=int, default=8)
    rel = sub.add_parser('relations'); rel.add_argument('ids', nargs='+'); rel.add_argument('--type', action='append', default=[]); rel.add_argument('--context', action='append', default=[])
    plan = sub.add_parser('plan'); plan.add_argument('ids', nargs='+'); plan.add_argument('--context', action='append', default=[])
    a = parser.parse_args()
    if a.action == 'build': result = build(a.base, a.check)
    else:
        reader = Reader(a.base)
        if a.action == 'domains': result = reader.domains()
        elif a.action == 'search': result = reader.search(a.domain, a.query, a.limit)
        elif a.action == 'concepts': result = reader.concepts(a.query, a.limit)
        elif a.action == 'relations': result = reader.relations(a.ids, a.type, parse_context(a.context))
        elif a.action == 'plan': result = reader.plan(a.ids, parse_context(a.context))
        else:
            cache = {}
            if a.task:
                command = [sys.executable, str(state_helper()), '--root', str(a.root), '--store', a.store]
                task = json.loads(subprocess.check_output(command + ['show', a.task], text=True))
                if task['status'] != 'running': raise ValueError('Knowledge task must be running')
                for name, row in task['outputs'].items():
                    if name.startswith('knowledge:') and row.get('kind') == 'object' and isinstance(row.get('value'), dict):
                        digest = sha(json.dumps(row['value'], sort_keys=True, ensure_ascii=False).encode('utf-8'))
                        if digest != row.get('version'): raise ValueError(f'Corrupt task output: {name}')
                        cache[name.removeprefix('knowledge:')] = row['value']
            result = reader.units(a.ids, cache)
            if a.task:
                for unit in result['units']:
                    if unit['reused']: continue
                    value = {'version': unit['version'], 'body': unit['body']}
                    subprocess.run(command + ['output', a.task, 'knowledge:' + unit['id'], '--kind', 'object', '--value', json.dumps(value, ensure_ascii=False), '--no-dependencies'], check=True, stdout=subprocess.DEVNULL)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as e:
        print(str(e), file=sys.stderr); sys.exit(1)
