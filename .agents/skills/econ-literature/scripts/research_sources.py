#!/usr/bin/env python3
"""Discover public research sources and acquire explicitly selected data.

Source responses and their hashes are saved in the requested output directory.
Scientific selection and interpretation remain with the researcher.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 20 * 1024 * 1024
TIMEOUT = 45
WB = "https://api.worldbank.org/v2"
CROSSREF = "https://api.crossref.org/works"


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError("URL must be HTTP(S) with a host and without embedded credentials")
    if parts.fragment:
        raise ValueError("URL fragments do not identify retrieved bytes")
    sensitive = {"key", "apikey", "accesstoken", "token", "password", "secret", "authorization", "appid"}
    if any(re.sub(r"[-_]", "", k).lower() in sensitive for k, _ in parse_qsl(parts.query, keep_blank_values=True)):
        raise ValueError("Credentials are not accepted in URLs")
    return url


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def retrieve(url, directory, name):
    """Fetch bounded response and preserve exact bytes and retrieval identity."""
    validate_url(url)
    request = Request(url, headers={"User-Agent": "EconomicsResearchSources/1.0 (public research)", "Accept": "*/*"})
    for attempt in range(3):
        try:
            with build_opener(SafeRedirect()).open(request, timeout=TIMEOUT) as response:
                final_url = validate_url(response.geturl())
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_BYTES:
                    raise ValueError("Response exceeds size limit")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("Response exceeds size limit")
                content_type = response.headers.get("Content-Type")
            break
        except HTTPError as exc:
            if exc.code not in (429, 503) or attempt == 2:
                raise RuntimeError(f"HTTP request failed with status {exc.code}") from None
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            if retry_after and (not retry_after.isdigit() or int(retry_after) > 5):
                raise RuntimeError(f"HTTP {exc.code}: retry later according to the server's Retry-After") from None
            time.sleep(int(retry_after) if retry_after else attempt + 1)
        except URLError as exc:
            raise RuntimeError(f"HTTP request failed: {type(exc.reason).__name__}") from None
    digest = hashlib.sha256(raw).hexdigest()
    requested_name = Path(name)
    path = directory / f"{requested_name.stem}-{digest}{requested_name.suffix}"
    atomic_write(path, raw)
    return raw, {"request_url": url, "retrieval_url": final_url,
                 "retrieved_at": datetime.now(timezone.utc).isoformat(),
                 "raw_sha256": digest,
                 "raw_path": str(path.resolve()), "bytes": len(raw), "content_type": content_type}


class SourceResponseError(ValueError):
    def __init__(self, message, response):
        super().__init__(message)
        self.response = response


def get_json(url, directory, name):
    raw, meta = retrieve(url, directory, name)
    try:
        return json.loads(raw), meta
    except (ValueError, UnicodeDecodeError):
        raise SourceResponseError("Source returned malformed JSON", meta) from None


def save_record(directory, record):
    path = directory / "source_record.json"
    atomic_write(path, (json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    return path


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def text_from_markup(text):
    parser = TextExtractor()
    parser.feed(text)
    return " ".join(unescape(" ".join(parser.parts)).split())


def normalize_doi(value):
    if not isinstance(value, str):
        raise ValueError("DOI must be a string")
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.IGNORECASE)
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi, flags=re.IGNORECASE):
        raise ValueError("Supply a valid DOI")
    return doi.casefold()


def crossref_message(payload):
    if not isinstance(payload, dict) or payload.get("status") != "ok" or not isinstance(payload.get("message"), dict):
        raise ValueError("Crossref returned an invalid response")
    return payload["message"]


def crossref_work(item, response):
    if (not isinstance(item, dict) or not isinstance(item.get("title"), list)
            or any(not isinstance(title, str) for title in item["title"])
            or (item.get("DOI") is not None and not isinstance(item["DOI"], str))):
        raise ValueError("Crossref returned malformed work metadata")
    date_record = item.get("published", item.get("issued", {}))
    dates = date_record.get("date-parts", [[]]) if isinstance(date_record, dict) else None
    refs, author_records = item.get("reference", []), item.get("author", [])
    if (not isinstance(dates, list) or any(not isinstance(part, list) for part in dates)
            or (dates and dates[0] and (not isinstance(dates[0][0], int) or isinstance(dates[0][0], bool)))
            or not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs)
            or not isinstance(author_records, list) or any(not isinstance(a, dict) for a in author_records)):
        raise ValueError("Crossref returned malformed work metadata")
    abstract = text_from_markup(item["abstract"]) if isinstance(item.get("abstract"), str) else None
    authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) or a.get("name", "") for a in author_records]
    return {"doi": item.get("DOI"), "title": item["title"][0] if item["title"] else None,
            "authors": authors, "year": dates[0][0] if dates and dates[0] else None,
            "url": item.get("URL"), "links": item.get("link", []), "relations": item.get("relation", {}),
            "reference_ids": [{k: ref[k] for k in ("DOI", "key", "unstructured") if k in ref}
                              for ref in refs],
            "abstract": abstract,
            "passages": ([{"location": "Crossref metadata abstract", "text": abstract,
                           "source_url": response["retrieval_url"],
                           "raw_sha256": response["raw_sha256"]}] if abstract else [])}


def literature_query(query, directory, limit):
    url = CROSSREF + "?" + urlencode({"query.bibliographic": query, "rows": limit})
    payload, response = get_json(url, directory, "crossref.json")
    try:
        message = crossref_message(payload)
        if not isinstance(message.get("items"), list) or not isinstance(message.get("total-results"), int):
            raise ValueError("Crossref response is missing items or total-results")
        works = [crossref_work(item, response) for item in message["items"]]
    except ValueError as error:
        raise SourceResponseError(str(error), response) from None
    return {"source": "Crossref", "query": query, "total_results": message["total-results"],
            "returned": len(works), "limit": limit, "response": response, "works": works}


def literature(query, directory, limit=20):
    if not query.strip() or not 1 <= limit <= 100:
        raise ValueError("Query must be nonempty and limit must be 1–100")
    record = literature_query(query, directory, limit)
    save_record(directory, record)
    return record


def literature_multi(queries, directory, limit=20):
    if not queries or any(not q.strip() for q in queries) or not 1 <= limit <= 100:
        raise ValueError("Queries must be nonempty and limit must be 1–100")
    results, works, identities = [], [], {}
    for index, query in enumerate(queries, 1):
        try:
            result = literature_query(query, directory, limit)
        except (ValueError, RuntimeError, OSError) as error:
            failure = {"query": query, "query_index": index, "status": "error", "error": str(error)}
            if isinstance(error, SourceResponseError):
                failure["response"] = error.response
            results.append(failure)
            continue
        results.append({key: value for key, value in result.items() if key != "works"} | {"query_index": index, "status": "ok"})
        for rank, work in enumerate(result["works"], 1):
            doi = work.get("doi")
            if doi:
                try:
                    identity = ("doi", normalize_doi(doi))
                except ValueError:
                    identity = None
            else:
                identity = None
            if identity is None and work.get("title") and work.get("year") is not None:
                identity = ("title-year", work["title"], work["year"])
            origin = {"query": query, "query_index": index, "rank": rank, "response": result["response"]}
            if identity is not None and identity in identities:
                works[identities[identity]]["origins"].append(origin)
            else:
                if identity is not None:
                    identities[identity] = len(works)
                works.append({**work, "origins": [origin]})
    record = {"source": "Crossref", "queries": results, "limit": limit,
              "status": "ok" if all(r["status"] == "ok" for r in results) else "partial",
              "returned": len(works), "works": works}
    save_record(directory, record)
    return record


def crossref_lookup(doi, directory):
    normalized = normalize_doi(doi)
    payload, response = get_json(CROSSREF + "/" + quote(normalized, safe=""), directory, "crossref-work.json")
    item = crossref_message(payload)
    if normalize_doi(item.get("DOI")) != normalized:
        raise ValueError("Crossref returned a different work")
    return item, response


def work_lookup(doi, directory, references=False):
    item, response = crossref_lookup(doi, directory)
    work = crossref_work(item, response)
    record = {"source": "Crossref", "requested_doi": doi, "response": response, "work": work}
    if references:
        refs = item.get("reference", [])
        if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
            raise ValueError("Crossref returned malformed references")
        record["references"] = [{"rank": rank, "originating_doi": item["DOI"],
                                 "reference": ref, "response": response}
                                for rank, ref in enumerate(refs, 1)]
        record["returned"] = len(refs)
    else:
        record["returned"] = 1
    save_record(directory, record)
    return record


def wb_pages(path, params, directory, prefix, stop=None):
    """Read every declared page unless stop explicitly accepts a prefix."""
    rows, responses, seen = [], [], set()
    page = 1
    expected_total = expected_pages = None
    while True:
        url = WB + path + "?" + urlencode({**params, "format": "json", "per_page": 1000, "page": page})
        payload, meta = get_json(url, directory, f"{prefix}-page-{page}.json")
        if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[0], dict):
            raise ValueError("World Bank returned malformed or error response")
        head, batch = payload
        try:
            current, pages, total = int(head["page"]), int(head["pages"]), int(head["total"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("World Bank response has invalid pagination") from None
        if current != page or pages < 0 or total < 0 or (batch is not None and not isinstance(batch, list)):
            raise ValueError("World Bank response has invalid page contents")
        if expected_total is None:
            expected_total, expected_pages = total, pages
        if (total, pages) != (expected_total, expected_pages):
            raise ValueError("World Bank pagination changed during retrieval")
        batch = batch or []
        if total and (not batch or pages < page):
            raise ValueError("World Bank returned an empty or unexpected page")
        fingerprint = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
        if batch and fingerprint in seen:
            raise ValueError("World Bank returned a duplicate page")
        seen.add(fingerprint)
        responses.append(meta)
        rows.extend(batch)
        if len(rows) > total:
            raise ValueError("World Bank returned more records than declared")
        if page >= pages or total == 0:
            if len(rows) != total:
                raise ValueError("World Bank returned fewer records than declared")
            return rows, responses, {"total": total, "pages": pages, "pages_retrieved": page, "complete": True}
        if stop and stop(rows):
            return rows, responses, {"total": total, "pages": pages, "pages_retrieved": page, "complete": False}
        page += 1


def indicators(query, directory, limit=None):
    tokens = query.casefold().split()
    if not tokens or (limit is not None and limit < 1):
        raise ValueError("Query must be nonempty and limit positive")
    def matches(row):
        if not isinstance(row, dict):
            raise ValueError("Malformed indicator metadata")
        haystack = " ".join(str(row.get(k) or "") for k in ("id", "name", "sourceNote", "sourceOrganization")).casefold()
        return all(token in haystack for token in tokens)
    rows, responses, paging = wb_pages("/indicator", {}, directory, "indicators", lambda rs: limit is not None and sum(matches(r) for r in rs) >= limit)
    found = [row for row in rows if matches(row)]
    result_complete = paging["complete"] and (limit is None or len(found) <= limit)
    result = found[:limit] if limit is not None else found
    record = {"source": "World Bank indicator catalog", "query": query, "match_fields": ["id", "name", "sourceNote", "sourceOrganization"],
              "limit": limit, "pagination": paging, "results_complete": result_complete,
              "returned": len(result), "responses": responses, "indicators": result}
    save_record(directory, record)
    return record


def series(indicator, countries, start, end, directory):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", indicator) or not countries or any(not re.fullmatch(r"[A-Za-z]{2,3}", c) for c in countries):
        raise ValueError("Supply a valid indicator ID and country codes")
    countries = [c.upper() for c in countries]
    if len(set(countries)) != len(countries) or start < 1 or end < start or end > 9999:
        raise ValueError("Country codes must be unique and the year range valid")
    definitions, definition_responses, definition_paging = wb_pages("/indicator/" + quote(indicator, safe=""), {}, directory, "definition")
    if len(definitions) != 1 or definitions[0].get("id", "").upper() != indicator.upper():
        raise ValueError("World Bank did not return the requested indicator definition")
    rows, responses, paging = wb_pages("/country/" + ";".join(countries) + "/indicator/" + quote(indicator, safe=""),
                                       {"date": f"{start}:{end}"}, directory, "series")
    observations, keys, covered, null_keys = [], set(), set(), []
    requested = set(countries)
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("country"), dict) or not isinstance(row.get("indicator"), dict):
            raise ValueError("Malformed World Bank observation")
        country = row.get("countryiso3code") or row["country"].get("id")
        source_country = row["country"].get("id")
        year = str(row.get("date", ""))
        matching = {str(country).upper(), str(source_country).upper()} & requested
        if (not country or len(matching) != 1
                or not re.fullmatch(r"\d{4}", year) or not start <= int(year) <= end
                or row["indicator"].get("id", "").upper() != indicator.upper()):
            raise ValueError("Observation does not match requested country, indicator and period")
        value = row.get("value")
        if ("value" not in row or isinstance(value, bool)
                or (value is not None and not isinstance(value, (int, float)))
                or (isinstance(value, float) and not math.isfinite(value))):
            raise ValueError("World Bank value must be a finite number or null")
        key = (country, year)
        if key in keys:
            raise ValueError(f"Duplicate country-year observation: {country} {year}")
        keys.add(key)
        requested_key = (next(iter(matching)), int(year))
        if requested_key in covered:
            raise ValueError(f"Duplicate requested country-year observation: {requested_key[0]} {year}")
        covered.add(requested_key)
        if value is None:
            null_keys.append({"country": requested_key[0], "year": requested_key[1]})
        observations.append({"country_code": country, "country_source_id": row["country"].get("id"), "country_name": row["country"].get("value"),
                             "year": int(year), "value": row.get("value"), "unit": row.get("unit"),
                             "obs_status": row.get("obs_status"), "decimal": row.get("decimal")})
    observations.sort(key=lambda r: (r["country_code"], r["year"]))
    csv_path = directory / "series.csv"
    fields = ["country_code", "country_source_id", "country_name", "year", "value", "unit", "obs_status", "decimal"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(observations)
    csv_bytes = stream.getvalue().encode("utf-8")
    atomic_write(csv_path, csv_bytes)
    expected = {(country, year) for country in countries for year in range(start, end + 1)}
    missing_keys = [{"country": country, "year": year} for country, year in sorted(expected - covered)]
    definition = definitions[0]
    name = definition.get("name") or ""
    unit_match = re.search(r"\(([^()]*)\)\s*$", name)
    unit = unit_match.group(1) if unit_match else definition.get("unit") or None
    if unit and unit.casefold() == "current us$" and re.search(r"\bper capita\b", name, re.IGNORECASE):
        unit += " per person"
    record = {"source": "World Bank World Development Indicators API", "indicator": indicator, "countries": countries,
              "start": start, "end": end, "grain": "country-year", "indicator_definition": definition,
              "measurement_unit": {"value": unit, "basis": "indicator name and unit field"},
              "definition_pagination": definition_paging, "definition_responses": definition_responses,
              "pagination": paging, "responses": responses, "observations": observations,
              "coverage": {"expected_count": len(expected), "observed_count": len(covered),
                           "complete": not missing_keys, "missing_keys": missing_keys,
                           "null_value_keys": sorted(null_keys, key=lambda k: (k["country"], k["year"]))},
              "missing_values": len(null_keys), "csv_path": str(csv_path.resolve()),
              "csv_sha256": hashlib.sha256(csv_bytes).hexdigest()}
    save_record(directory, record)
    return record


def fetch(url, directory, extract=False, kind="auto"):
    raw, response = retrieve(url, directory, "download.bin")
    record = {"source": "explicitly selected URL", "response": response}
    save_record(directory, record)
    if extract:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "econ-data" / "scripts"))
        from equity_sources import extract_document
        try:
            record["document"] = extract_document(raw, kind=kind, source_url=response["retrieval_url"])
        except ModuleNotFoundError as error:
            raise RuntimeError(f"Document extraction needs {error.name}; install the existing econ-data equity requirements") from None
    save_record(directory, record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    lit = sub.add_parser("literature")
    lit.add_argument("--query", required=True)
    lit.add_argument("--limit", type=int, default=20)
    multi = sub.add_parser("literature-multi")
    multi.add_argument("--query", action="append", required=True)
    multi.add_argument("--limit", type=int, default=20)
    work = sub.add_parser("work")
    work.add_argument("--doi", required=True)
    refs = sub.add_parser("references")
    refs.add_argument("--doi", required=True)
    ind = sub.add_parser("indicators")
    ind.add_argument("--query", required=True)
    ind.add_argument("--limit", type=int)
    ser = sub.add_parser("series")
    ser.add_argument("--indicator", required=True)
    ser.add_argument("--countries", nargs="+", required=True)
    ser.add_argument("--start", type=int, required=True)
    ser.add_argument("--end", type=int, required=True)
    doc = sub.add_parser("fetch")
    doc.add_argument("url")
    doc.add_argument("--extract", action="store_true")
    doc.add_argument("--kind", choices=("auto", "html", "pdf", "text"), default="auto")
    paged = sub.add_parser("search-paged")
    paged.add_argument("--query", action="append", required=True)
    paged.add_argument("--per-page", type=int, default=20)
    paged.add_argument("--pages", type=int, default=2)
    cites = sub.add_parser("citations")
    cites.add_argument("--doi", required=True)
    cites.add_argument("--per-page", type=int, default=20)
    cites.add_argument("--pages", type=int, default=2)
    corp = sub.add_parser("corpus")
    corpus_input = corp.add_mutually_exclusive_group(required=True)
    corpus_input.add_argument("--spec", type=Path)
    corpus_input.add_argument("--record", type=Path)
    corp.add_argument("--reuse", type=Path)
    corp.add_argument("--query")
    corp.add_argument("--limit", type=int)
    corp.add_argument("--select", help="Proposition selection filters as a JSON object")
    corp.add_argument("--metadata", action="append", type=Path, default=[], help="Existing work/works source record to refresh bibliography")
    corp.add_argument("--bibliography", action="append", type=Path, default=[], help="Local CSL-JSON bibliography export")
    for command in (lit, multi, work, refs, ind, ser, doc, paged, cites, corp):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("search-paged", "citations", "corpus"):
            import research_search
            owner = sys.modules[__name__]
            if args.command == "search-paged":
                result = research_search.search_paged(owner, args.query, args.output, args.per_page, args.pages)
            elif args.command == "citations":
                result = research_search.citations(owner, args.doi, args.output, args.per_page, args.pages)
            else:
                reuse = args.reuse
                if args.record is not None:
                    prior = json.loads(args.record.read_text(encoding="utf-8"))
                    if prior.get('kind') != 'local_corpus':
                        raise ValueError('record must be an existing local corpus')
                    if args.reuse is not None:
                        raise ValueError('record already identifies the source to reuse')
                    if not args.query:
                        raise ValueError('a new query is required when selecting from a record')
                    specification = {'query': args.query, 'limit': 20 if args.limit is None else args.limit,
                        'documents': [{key: row[key] for key in ('id', 'path', 'format')}
                                      for row in prior['documents']]}
                    reuse = args.record
                else:
                    specification = json.loads(args.spec.read_text(encoding="utf-8"))
                    if args.query is not None:
                        specification['query'] = args.query
                    if args.limit is not None:
                        specification['limit'] = args.limit
                if args.select is not None:
                    specification['selection'] = json.loads(args.select)
                metadata = {}
                for path in args.metadata:
                    raw_metadata = path.read_bytes()
                    record = json.loads(raw_metadata)
                    works = [record['work']] if 'work' in record else record.get('works', [])
                    if not works:
                        raise ValueError('metadata source record must contain work or works')
                    for work in works:
                        doi = normalize_doi(work.get('doi'))
                        work = {**work, 'metadata_source': {'path': str(path.resolve()),
                                'sha256': hashlib.sha256(raw_metadata).hexdigest()}}
                        if doi in metadata and metadata[doi] != work:
                            raise ValueError('conflicting bibliography updates for the same DOI')
                        metadata[doi] = work
                if metadata:
                    previous = json.loads(reuse.read_text(encoding='utf-8')) if reuse is not None else {'documents': []}
                    previous_docs = {row['id']: row for row in previous['documents']}
                    matched = set()
                    for document in specification['documents']:
                        bibliography = {**previous_docs.get(document['id'], {}).get('metadata', {}), **document.get('metadata', {})}
                        doi = normalize_doi(bibliography['doi']) if bibliography.get('doi') else None
                        if doi in metadata:
                            document['metadata'] = {**bibliography, **{key: value for key, value in metadata[doi].items()
                                if key != 'passages' and value is not None}}
                            matched.add(doi)
                    if matched != set(metadata):
                        raise ValueError('metadata DOI has no matching corpus document')
                if args.bibliography:
                    previous = json.loads(reuse.read_text(encoding='utf-8')) if reuse is not None else {'documents': []}
                    previous_docs = {row['id']: row for row in previous['documents']}
                    for path in args.bibliography:
                        raw_bibliography = path.read_bytes()
                        if len(raw_bibliography) > MAX_BYTES:
                            raise ValueError('bibliography exceeds size limit')
                        entries = json.loads(raw_bibliography)
                        if not isinstance(entries, list) or not entries:
                            raise ValueError('CSL bibliography must be a nonempty JSON array')
                        for entry in entries:
                            if not isinstance(entry, dict):
                                raise ValueError('CSL bibliography entries must be objects')
                            doi = normalize_doi(entry.get('DOI') or entry.get('doi')) if entry.get('DOI') or entry.get('doi') else None
                            citation_key = str(entry['id']) if entry.get('id') is not None else None
                            if not doi and not citation_key:
                                raise ValueError('CSL bibliography entry requires a stable id or DOI')
                            edition = entry.get('version') or entry.get('edition')
                            if edition is not None:
                                edition = str(edition)
                            matches = []
                            for document in specification['documents']:
                                bibliography = {**previous_docs.get(document['id'], {}).get('metadata', {}), **document.get('metadata', {})}
                                old_doi = normalize_doi(bibliography['doi']) if bibliography.get('doi') else None
                                old_edition = document.get('version', previous_docs.get(document['id'], {}).get('version'))
                                same_identity = (doi == old_doi if doi and old_doi else
                                    citation_key and citation_key in (document['id'], bibliography.get('citation_key')))
                                if old_edition == edition and same_identity:
                                    matches.append(document)
                            if len(matches) > 1:
                                raise ValueError('bibliography entry matches multiple corpus documents')
                            if matches:
                                document = matches[0]
                            else:
                                identity = doi or citation_key
                                if edition:
                                    identity += '@' + edition
                                document = {'id': 'csl:' + identity, 'path': None, 'format': 'metadata'}
                                if edition: document['version'] = edition
                                specification['documents'].append(document)
                            provenance = {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw_bibliography).hexdigest()}
                            fields = {'csl': entry, 'bibliography_source': provenance}
                            if doi: fields['doi'] = doi
                            if citation_key: fields['citation_key'] = citation_key
                            if entry.get('title'): fields['title'] = entry['title']
                            if entry.get('author'): fields['authors'] = entry['author']
                            if isinstance(entry.get('abstract'), str): fields['abstract'] = text_from_markup(entry['abstract'])
                            issued = entry.get('issued', {}).get('date-parts', []) if isinstance(entry.get('issued', {}), dict) else []
                            if issued and isinstance(issued[0], list) and issued[0]: fields['year'] = issued[0][0]
                            document['metadata'] = {**document.get('metadata', {}), **fields}
                result = research_search.corpus(owner, specification, args.output, reuse)
        elif args.command == "literature":
            result = literature(args.query, args.output, args.limit)
        elif args.command == "literature-multi":
            result = literature_multi(args.query, args.output, args.limit)
        elif args.command in ("work", "references"):
            result = work_lookup(args.doi, args.output, args.command == "references")
        elif args.command == "indicators":
            result = indicators(args.query, args.output, args.limit)
        elif args.command == "series":
            result = series(args.indicator, args.countries, args.start, args.end, args.output)
        else:
            result = fetch(args.url, args.output, args.extract, args.kind)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"error: {error}\n")
    print(json.dumps({"record": str((args.output / 'source_record.json').resolve()),
                      "returned": result.get("returned", len(result.get("observations", []))),
                      "status": result.get("status", "ok")}, ensure_ascii=False))
    if result.get("status") == "partial":
        return 1


if __name__ == "__main__":
    sys.exit(main())
