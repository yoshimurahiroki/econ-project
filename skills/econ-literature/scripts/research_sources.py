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
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 20 * 1024 * 1024
TIMEOUT = 45
WB = "https://api.worldbank.org/v2"
CROSSREF = "https://api.crossref.org/works"
DOLEAC_SHEET = 'https://docs.google.com/spreadsheets/d/1zyRB708QpsxG_8vNCRl7gv5FyrPE81w3mF_kMVJlHbY'
DOLEAC_RESOURCES = 'https://jenniferdoleac.com/resources/'


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
    def __init__(self, *, credential_request=False):
        super().__init__()
        self.credential_request = credential_request

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if self.credential_request:
            raise RuntimeError("Authenticated Census requests do not follow redirects")
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def retrieve(url, directory, name, *, census_api_key=None):
    """Fetch bounded response and preserve exact bytes and retrieval identity."""
    validate_url(url)
    request_url, credential_values = url, set()
    if census_api_key is not None:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.hostname != 'api.census.gov' or parts.port not in (None, 443)
                or not re.fullmatch(r'/data/[0-9]{4}/acs/acs5', parts.path)):
            raise ValueError('Census credentials apply only to the official ACS observation endpoint')
        if not isinstance(census_api_key, str) or not census_api_key.strip():
            raise ValueError('Census credentials must be a nonempty string')
        census_api_key = census_api_key.strip()
        credential_values = {census_api_key, quote(census_api_key, safe=''),
                             urlencode({'key': census_api_key}).partition('=')[2]}
        request_url = parts._replace(query=urlencode([
            *parse_qsl(parts.query, keep_blank_values=True), ('key', census_api_key)])).geturl()
    request = Request(request_url, headers={"User-Agent": "EconomicsResearchSources/1.0 (public research)", "Accept": "*/*"})
    for attempt in range(3):
        try:
            with build_opener(SafeRedirect(credential_request=bool(credential_values))).open(request, timeout=TIMEOUT) as response:
                if credential_values:
                    if response.geturl() != request_url:
                        raise ValueError('Authenticated Census response changed its request identity')
                    final_url = url
                else:
                    final_url = validate_url(response.geturl())
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_BYTES:
                    raise ValueError("Response exceeds size limit")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("Response exceeds size limit")
                content_type = response.headers.get("Content-Type")
                last_modified = response.headers.get('Last-Modified')
                etag = response.headers.get('ETag')
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
        except Exception as exc:
            if credential_values:
                raise RuntimeError(f"Authenticated Census request failed ({type(exc).__name__})") from None
            raise
    if any(value.encode() in raw for value in credential_values):
        raise RuntimeError('Census response echoed credentials; the response was not saved')
    if credential_values:
        for value in credential_values:
            content_type = content_type.replace(value, '[redacted]') if content_type else content_type
            last_modified = last_modified.replace(value, '[redacted]') if last_modified else last_modified
            etag = etag.replace(value, '[redacted]') if etag else etag
    digest = hashlib.sha256(raw).hexdigest()
    requested_name = Path(name)
    path = directory / f"{requested_name.stem}-{digest}{requested_name.suffix}"
    atomic_write(path, raw)
    return raw, {"request_url": url, "retrieval_url": final_url,
                 "retrieved_at": datetime.now(timezone.utc).isoformat(),
                 "raw_sha256": digest,
                 "raw_path": str(path.resolve()), "bytes": len(raw), "content_type": content_type,
                 "last_modified": last_modified, "etag": etag}


class SourceResponseError(ValueError):
    def __init__(self, message, response):
        super().__init__(message)
        self.response = response


def get_json(url, directory, name, *, census_api_key=None):
    raw, meta = (retrieve(url, directory, name) if census_api_key is None else
                 retrieve(url, directory, name, census_api_key=census_api_key))
    try:
        return json.loads(raw), meta
    except (ValueError, UnicodeDecodeError):
        raise SourceResponseError("Source returned malformed JSON", meta) from None


def record_paths(record, directory, *, relative=False):
    """Resolve retained source files at their record, or encode them for publication."""
    directory = Path(directory).resolve()

    def convert(value, field=None):
        if isinstance(value, list):
            return [convert(item, field) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: convert(item, 'design_source' if field == 'design_sources' else key)
                  for key, item in value.items()}
        paths = [key for key, digest_key in (('raw_path', 'raw_sha256'),
                 ('csv_path', 'csv_sha256'), ('text_path', 'text_sha256')) if digest_key in value]
        if (field in {'metadata_source', 'bibliography_source', 'ranking_input', 'design_source'}
                or value.get('kind') == 'supplied_connector_response'
                or {'path', 'format', 'pages', 'raw_sha256'} <= value.keys()):
            paths.append('path')
        for key in paths:
            location = value.get(key)
            if isinstance(location, str):
                path = Path(location)
                if relative and path.is_absolute():
                    result[key] = os.path.relpath(path, directory)
                elif not relative and not path.is_absolute():
                    result[key] = str((directory / path).resolve())
        return result

    return convert(record)


def read_record(path, raw=None):
    path = Path(path)
    return record_paths(json.loads(path.read_bytes() if raw is None else raw), path.parent)


def save_record(directory, record):
    path = directory / "source_record.json"
    saved = record_paths(record, path.parent, relative=True)
    atomic_write(path, (json.dumps(saved, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
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


def work_identity(work):
    if work.get('doi'):
        return ('doi', normalize_doi(work['doi']))
    if work.get('id'):
        return ('id', str(work['id']))
    authors = work.get('authors')
    if work.get('title') and work.get('year') is not None and isinstance(authors, list) and authors:
        return ('metadata', ' '.join(work['title'].casefold().split()), work['year'],
                json.dumps(authors, ensure_ascii=False, sort_keys=True))
    return None


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
    publication_dates = {}
    for name in ('published-online', 'published-print', 'published', 'issued', 'accepted', 'posted'):
        parts = item.get(name, {}).get('date-parts', []) if isinstance(item.get(name, {}), dict) else []
        if parts and parts[0]:
            values = parts[0]
            if (not isinstance(values, list) or not 1 <= len(values) <= 3
                    or any(type(value) is not int for value in values)):
                raise ValueError('Crossref returned invalid publication date parts')
            datetime(*(values + [1] * (3-len(values))))
            publication_dates[name.replace('-', '_')] = '-'.join(
                str(value).zfill(4 if i == 0 else 2) for i, value in enumerate(values))
    containers = item.get('container-title', [])
    if not isinstance(containers, list) or any(not isinstance(value, str) for value in containers):
        raise ValueError('Crossref returned malformed container titles')
    work = {"doi": item.get("DOI"), "title": item["title"][0] if item["title"] else None,
            "authors": authors, "year": dates[0][0] if dates and dates[0] else None,
            "author_records": author_records, "type": item.get('type'),
            "container_title": containers[0] if containers else None, "container_titles": containers,
            "publisher": item.get('publisher'), "publication_dates": publication_dates,
            "volume": item.get('volume'), "issue": item.get('issue'), "pages": item.get('page'),
            "issn": item.get('ISSN', []), "version": item.get('version'),
            "metadata_response": response,
            "url": item.get("URL"), "links": item.get("link", []), "relations": item.get("relation", {}),
            "reference_ids": [{k: ref[k] for k in ("DOI", "key", "unstructured") if k in ref}
                              for ref in refs],
            "abstract": abstract,
            "passages": ([{"location": "Crossref metadata abstract", "text": abstract,
                           "source_url": response["retrieval_url"],
                           "raw_sha256": response["raw_sha256"]}] if abstract else [])}
    import research_search
    work['publication_status'] = research_search.publication_details(work)['status']
    work['publication_status_inferred'] = True
    return work


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
            identity = work_identity(work)
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


class DiscoveryHTML(HTMLParser):
    """Read published links and table cells without executing page scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.rows, self.row_numbers, self.text = [], [], [], []
        self.anchor = self.row = self.cell = None
        self.header = self.row_number = None
        self.section = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'script', 'style', 'noscript'}:
            self.hidden += 1
        if tag == 'a' and attrs.get('href'):
            self.anchor = {'href': attrs['href'], 'label': '', 'section': self.section}
        if tag == 'tr':
            self.row = []
            self.row_number = None
        if tag == 'td':
            self.cell = []
        if tag == 'th':
            self.header = []

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self.hidden:
            self.hidden -= 1
        if tag == 'a' and self.anchor is not None:
            self.anchor['label'] = ' '.join(self.anchor['label'].split())
            self.links.append(self.anchor)
            self.anchor = None
        if tag == 'td' and self.cell is not None:
            if self.row is not None:
                self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        if tag == 'th' and self.header is not None:
            value = ''.join(self.header).strip()
            if value.isdigit():
                self.row_number = int(value)
            self.header = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row_numbers.append(self.row_number)
            self.row = None

    def handle_data(self, data):
        if self.hidden:
            return
        self.text.append(data)
        text = data.strip().casefold()
        if text.startswith('economics of crime research'):
            self.section = 'economics_of_crime'
        elif 'literature reviews' in text:
            self.section = 'literature_reviews'
        elif self.anchor is None and (text.endswith(':') or text == 'women in economics'):
            self.section = None
        if self.anchor is not None:
            self.anchor['label'] += data
        if self.cell is not None:
            self.cell.append(data)
        if self.header is not None:
            self.header.append(data)


def supplied_metadata(path):
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('metadata response exceeds size limit')
    record = json.loads(raw)
    if not isinstance(record, dict) or record.get('isError'):
        raise ValueError('metadata must be a successful JSON object response')
    value = record.get('structuredContent', record)
    if not isinstance(value, dict):
        raise ValueError('metadata response has no structured object')
    return value, {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
                   'kind': 'supplied_connector_response', 'imported_at': datetime.now(timezone.utc).isoformat()}


def doleac(directory, *, as_of=None, sheet_metadata=None, file_metadata=None, older_years=None, theme=None):
    import research_search
    plan = research_search.search_plan(['crime'], as_of, theme)
    responses, failures = [], []
    links = []
    try:
        raw, response = retrieve(DOLEAC_RESOURCES, directory, 'doleac-resources.html')
        responses.append(response)
        page = DiscoveryHTML()
        page.feed(raw.decode('utf-8'))
        for link in page.links:
            if link['section'] not in {'economics_of_crime', 'literature_reviews'}:
                continue
            url = urljoin(response['retrieval_url'], link['href'])
            if urlsplit(url).scheme in {'https', 'http'}:
                links.append({'label': link['label'], 'url': url, 'section': link['section'], 'response': response})
        if not any(link['section'] == 'economics_of_crime' for link in links) or not any(link['section'] == 'literature_reviews' for link in links):
            raise ValueError('Resources page has no current crime-research and literature-review links')
    except (ValueError, RuntimeError, OSError) as error:
        failures.append({'source': DOLEAC_RESOURCES, 'error': str(error)})
    sheet_base = DOLEAC_SHEET
    published_sheets = {re.match(r"https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+", link["url"]).group(0)
        for link in links if link["section"] == "economics_of_crime"
        and re.match(r"https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+", link["url"])}
    if len(published_sheets) == 1:
        sheet_base = published_sheets.pop()
    elif len(published_sheets) > 1:
        raise ValueError("Resources identifies multiple crime spreadsheets; resolve the source identity")
    if sheet_metadata is not None:
        metadata, response = supplied_metadata(sheet_metadata)
        responses.append(response)
        sheets = metadata.get('sheets')
        if not isinstance(sheets, list):
            raise ValueError('sheet metadata requires sheets[].properties')
        tabs = [{'title': row['properties']['title'], 'sheetId': row['properties']['sheetId']}
                for row in sheets if isinstance(row, dict) and isinstance(row.get('properties'), dict)]
    else:
        raw, response = retrieve(sheet_base + '/htmlview', directory, 'doleac-tabs.html')
        responses.append(response)
        pattern = r'items\.push\(\{name:\s*("(?:\\.|[^"\\])*"),\s*pageUrl:\s*("(?:\\.|[^"\\])*"),\s*gid:\s*"(\d+)"'
        tabs = [{'title': json.loads(name), 'sheetId': int(gid)} for name, _, gid in re.findall(pattern, raw.decode('utf-8'))]
    if (not tabs or any(type(row['sheetId']) is not int or row['sheetId'] < 0 or
            not isinstance(row['title'], str) or not row['title'].strip() for row in tabs)
            or len({row['sheetId'] for row in tabs}) != len(tabs) or len({row['title'] for row in tabs}) != len(tabs)):
        raise ValueError('Doleac metadata must contain distinct actual sheet IDs and titles; supply current connector metadata')
    by_title = {row['title']: row for row in tabs}
    years = sorted((int(title) for title in by_title if re.fullmatch(r'\d{4}', title) and int(title) <= plan['year']), reverse=True)
    if 'Accepted' not in by_title or 'Overview' not in by_title or not years:
        raise ValueError('Doleac metadata must include Accepted, Overview and an existing annual tab')
    selected = ['Accepted', *(str(year) for year in years[:3])]
    for year in older_years or []:
        if str(year) not in by_title:
            raise ValueError('requested annual tab is absent: ' + str(year))
        if str(year) not in selected:
            selected.append(str(year))
    selected.append('Overview')
    modified_time = None
    modified_source = None
    if file_metadata is not None:
        metadata, response = supplied_metadata(file_metadata)
        if metadata.get('id') != sheet_base.rsplit('/', 1)[1]:
            raise ValueError('Drive file metadata must identify the selected Doleac spreadsheet')
        responses.append(response)
        modified_time = metadata.get('modifiedTime', metadata.get('modified_time'))
        if not isinstance(modified_time, str) or not modified_time.strip():
            raise ValueError('file metadata requires the returned modifiedTime/modified_time')
        datetime.fromisoformat(modified_time.replace('Z', '+00:00'))
        modified_source = response
    extracted, works, coverage = [], [], []
    for title in selected:
        tab = by_title[title]
        url = sheet_base + '/htmlview/sheet?' + urlencode({'headers': 'true', 'gid': tab['sheetId']})
        try:
            raw, response = retrieve(url, directory, 'doleac-' + title + '.html')
            responses.append(response)
            page = DiscoveryHTML()
            page.feed(raw.decode('utf-8'))
            rows = [(number, row) for number, row in zip(page.row_numbers, page.rows) if any(row)]
            if any(number is None for number, _ in rows):
                raise ValueError('sheet table is missing its original row labels')
            extracted.append({**tab, 'url': url, 'response': response, 'rows': rows})
            if title == 'Overview':
                header = next((row for _, row in rows if 'Last updated' in row), None)
                if header is None:
                    raise ValueError('Overview has no Last updated coverage column')
                column = header.index('Last updated')
                for number, row in rows:
                    if len(row) > column and row[0] and row[column] and row[column] != 'Last updated':
                        coverage.append({'venue': row[0], 'coverage_date': row[column], 'row': number,
                                         'column': column+1, 'response': response})
                continue
            header = next((row for _, row in rows if {'Title', 'Authors', 'Journal', 'Link'} <= set(row)), None)
            if header is None:
                raise ValueError('annual/Accepted sheet has no Title, Authors, Journal and Link columns')
            positions = {key: header.index(key) for key in ('Title', 'Authors', 'Journal', 'Link')}
            for number, row in rows:
                if len(row) <= max(positions.values()) or row == header or not row[positions['Title']]:
                    continue
                link = row[positions['Link']]
                doi = None
                if link.startswith(('http://', 'https://')):
                    parts = urlsplit(link)
                    values = [value for key, value in parse_qsl(parts.query) if key in {'id', 'doi'}]
                    if parts.hostname in {'doi.org', 'dx.doi.org'}:
                        values.append(parts.path.lstrip('/'))
                    for value in values:
                        if re.fullmatch(r'10\.\d{4,9}/\S+', value):
                            doi = normalize_doi(value)
                            break
                works.append({'id': f'doleac:{tab["sheetId"]}:row:{number}', 'title': row[positions['Title']],
                              'authors': row[positions['Authors']], 'container_title': row[positions['Journal']],
                              'url': link, 'doi': doi, 'year': int(title) if title.isdigit() else None,
                              'type': 'journal-article', 'publication_status': 'forthcoming' if title == 'Accepted' else 'published',
                              'publication_dates': {'published': title} if title.isdigit() else {},
                              'metadata_response': response, 'metadata_location': {'sheetId': tab['sheetId'], 'row': number},
                              'publication_status_basis': 'Doleac ' + title + ' tab'})
        except (ValueError, RuntimeError, OSError) as error:
            failures.append({'tab': title, 'sheetId': tab['sheetId'], 'error': str(error)})
    if modified_time is None:
        failures.append({'metadata': 'modified_time', 'error': 'supply current Drive file metadata through --file-metadata'})
    record = {'source': 'Jennifer Doleac crime research', 'kind': 'crime_discovery', 'as_of': plan['as_of'],
              'spreadsheet_url': sheet_base + '/edit', 'tabs': tabs, 'selected_tabs': [by_title[name] for name in selected],
              'latest_existing_year': years[0], 'source_modified_time': modified_time, 'modified_time_source': modified_source,
              'coverage': coverage, 'sheet_contents': extracted, 'resources': links, 'responses': responses,
              'works': works, 'returned': len(works), 'supplemental_search_plan': plan,
              'years_after_latest_tab': list(range(years[0]+1, plan['year']+1)),
              'failures': failures, 'status': 'partial' if failures else 'ok'}
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
    corp.add_argument("--priority", type=Path, help="Shared literature selection specification")
    plan = sub.add_parser('search-plan')
    plan.add_argument('--field', action='append', default=[])
    plan.add_argument('--theme')
    ranking = sub.add_parser('rank')
    ranking.add_argument('--record', type=Path, required=True)
    ranking.add_argument('--spec', type=Path, required=True)
    ranking.add_argument('--limit', type=int, default=20)
    crime = sub.add_parser('doleac')
    crime.add_argument('--sheet-metadata', type=Path, help='Current Sheets metadata JSON, including native connector responses')
    crime.add_argument('--file-metadata', type=Path, help='Current Drive file metadata JSON with modifiedTime/modified_time')
    crime.add_argument('--older-year', action='append', type=int, default=[])
    crime.add_argument('--theme')
    for command in (plan, ranking, corp, paged, crime):
        command.add_argument('--as-of', help='Execution date YYYY-MM-DD; default is the runtime calendar date')
    paged.add_argument('--window', choices=('R0', 'R1', 'R2', 'R3'))
    paged.add_argument('--venue', help='Crossref query.container-title value')
    view = sub.add_parser('view')
    view.add_argument('--limit', type=int, default=20)
    view.add_argument('--document', action='append')
    view.add_argument('--as-of')
    passage = sub.add_parser('passage')
    passage.add_argument('--document', required=True)
    passage.add_argument('--page', required=True, type=int)
    passage.add_argument('--start', type=int)
    passage.add_argument('--end', type=int)
    passage.add_argument('--max-chars', type=int, default=12000)
    for command in (view, passage):
        command.add_argument('--record', type=Path, required=True)
        command.add_argument('--sha256', required=True)
    for command in (lit, multi, work, refs, ind, ser, doc, paged, cites, corp, plan, ranking, crime):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in {'view', 'passage'}:
            import research_search
            if args.command == 'view':
                result = research_search.corpus_view(args.record, args.sha256, limit=args.limit,
                    document_ids=args.document, as_of=args.as_of)
            else:
                result = research_search.corpus_passage(args.record, args.sha256, args.document, args.page,
                    args.start, args.end, max_chars=args.max_chars)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == 'doleac':
            result = doleac(args.output, as_of=args.as_of, sheet_metadata=args.sheet_metadata,
                            file_metadata=args.file_metadata, older_years=args.older_year, theme=args.theme)
        elif args.command in ("search-paged", "citations", "corpus", 'search-plan', 'rank'):
            import research_search
            owner = sys.modules[__name__]
            if args.command == 'search-plan':
                result = {'kind': 'literature_search_plan', **research_search.search_plan(args.field, args.as_of, args.theme)}
                save_record(args.output, result)
            elif args.command == 'rank':
                raw = args.record.read_bytes()
                result = read_record(args.record, raw)
                spec = json.loads(args.spec.read_text(encoding='utf-8'))
                result['search_priority'] = research_search.rank_studies(result, spec, args.as_of, args.limit)
                result['ranking_input'] = {'path': str(args.record.resolve()), 'sha256': hashlib.sha256(raw).hexdigest()}
                save_record(args.output, result)
            elif args.command == "search-paged":
                result = research_search.search_paged(owner, args.query, args.output, args.per_page, args.pages,
                                                      as_of=args.as_of, window=args.window, venue=args.venue)
            elif args.command == "citations":
                result = research_search.citations(owner, args.doi, args.output, args.per_page, args.pages)
            else:
                reuse = args.reuse
                if args.record is not None:
                    prior = read_record(args.record)
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
                if args.priority is not None:
                    specification['search_priority'] = json.loads(args.priority.read_text(encoding='utf-8'))
                elif args.record is not None and prior.get('search_priority'):
                    specification['search_priority'] = prior['search_priority']['specification']
                metadata = {}
                for path in args.metadata:
                    raw_metadata = path.read_bytes()
                    record = read_record(path, raw_metadata)
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
                if metadata or args.bibliography:
                    if args.record is not None:
                        previous = prior
                    elif reuse is not None:
                        previous = read_record(reuse)
                    else:
                        previous = {'documents': []}
                    previous_docs = {row['id']: row for row in previous['documents']}
                if metadata:
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
                            for source_key, key in (('container-title', 'container_title'), ('publisher', 'publisher'),
                                                    ('volume', 'volume'), ('issue', 'issue'), ('type', 'type'), ('URL', 'url')):
                                if entry.get(source_key): fields[key] = entry[source_key]
                            if isinstance(entry.get('abstract'), str): fields['abstract'] = text_from_markup(entry['abstract'])
                            issued = entry.get('issued', {}).get('date-parts', []) if isinstance(entry.get('issued', {}), dict) else []
                            if issued and isinstance(issued[0], list) and issued[0]: fields['year'] = issued[0][0]
                            document['metadata'] = {**document.get('metadata', {}), **fields}
                result = research_search.corpus(owner, specification, args.output, reuse, as_of=args.as_of)
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
    summary = {"record": str((args.output / 'source_record.json').resolve()),
                      "returned": result.get("returned", len(result.get("observations", []))),
                      "status": result.get("status", "ok")}
    if args.command == 'search-plan':
        summary.update(result)
    if result.get('search_priority'):
        summary['search_priority'] = research_search.compact_priority(result['search_priority'])
    print(json.dumps(summary, ensure_ascii=False))
    if result.get("status") == "partial":
        return 1


if __name__ == "__main__":
    sys.exit(main())
