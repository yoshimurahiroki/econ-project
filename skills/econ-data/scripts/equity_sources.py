#!/usr/bin/env python3
"""Turn retrieved filings, IR documents and feeds into source-linked model inputs.

EDINET and e-Stat acquisition uses the caller's environment credentials; SEC
originals use a declared User-Agent. The same parsers read saved MCP documents
or local files and preserve source, units, contexts and filing versions.
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
import zipfile


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral() else float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def provenance(data: bytes, source_url: str | None) -> dict:
    """Keep source identity without credentials or URL fragments."""
    if source_url:
        parts = urlsplit(source_url)
        if parts.username or parts.password:
            raise ValueError("Source URLs must contain no credentials")
        from urllib.parse import parse_qsl, urlencode

        secrets = {"subscription-key", "api_key", "apikey", "token", "access_token", "appid"}
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if k.lower() not in secrets]
        source_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    return {"source_url": source_url, "sha256": hashlib.sha256(data).hexdigest()}


def _credential(variable: str, registration_url: str) -> str:
    value = os.environ.get(variable, "").strip()
    if not value:
        raise ValueError(f"Set your own {variable}; free registration: {registration_url}")
    return value


def _public_payload(value: Any, credential: str) -> Any:
    """Remove API credentials echoed in provider request metadata."""
    from urllib.parse import quote, quote_plus

    if isinstance(value, dict):
        secrets = {"appid", "subscriptionkey", "apikey", "accesstoken", "token", "authorization"}
        return {key: _public_payload(item, credential) for key, item in value.items()
                if re.sub(r"[-_@]", "", key).lower() not in secrets}
    if isinstance(value, list):
        return [_public_payload(item, credential) for item in value]
    if isinstance(value, str):
        for encoded in {credential, quote(credential, safe=""), quote_plus(credential)}:
            value = value.replace(encoded, "[redacted]")
    return value


def _edinet_request(function: Any, *args: Any, **kwargs: Any) -> Any:
    """Use the installed client with caller credentials and sanitized errors."""
    key = _credential("EDINET_API_KEY", "https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1")
    # Upstream diagnostics can include provider error bodies. The caller gets
    # the error type and public request identity, without credential-bearing URLs.
    logger = logging.getLogger("edinet_tools.api")
    previous = logger.disabled
    logger.disabled = True
    try:
        return function(*args, api_key=key, timeout=45, **kwargs)
    except Exception as error:
        status = getattr(error, "code", None)
        detail = f"HTTP {status}" if isinstance(status, int) else type(error).__name__
        raise RuntimeError(f"EDINET request failed ({detail}); check the credential and requested filing") from None
    finally:
        logger.disabled = previous


def edinet_list(day: str) -> dict:
    """Retrieve the official daily listing with the user's EDINET API key."""
    key = _credential("EDINET_API_KEY", "https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1")
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("EDINET listing date must use YYYY-MM-DD")
    from edinet_tools.api import fetch_documents_list

    data = _public_payload(_edinet_request(fetch_documents_list, day, type=2), key)
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    return {"source": "EDINET", "source_url":
            f"https://api.edinet-fsa.go.jp/api/v2/documents.json?date={day}&type=2",
            "payload_sha256": hashlib.sha256(encoded).hexdigest(), "hash_scope": "sanitized_json",
            "fetched_at": datetime.now(timezone.utc).isoformat(), "data": data}


def edinet_filing(document_id: str, *, directory: str | Path, source: str = "instance",
                   document_type: str | None = None, metadata: dict | None = None) -> dict:
    """Retrieve, save and parse one official EDINET archive with caller credentials."""
    key = _credential("EDINET_API_KEY", "https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1")
    if not re.fullmatch(r"S[0-9A-Z]{7}", document_id):
        raise ValueError("Use the EDINET document ID returned by edinet-list")
    if source not in {"csv", "instance", "xbrl"}:
        raise ValueError("EDINET source must be csv, instance or xbrl")
    metadata = _public_payload(metadata or {}, key)
    if metadata.get("docID", document_id) != document_id:
        raise ValueError("The listing metadata belongs to a different EDINET document")
    document_type = document_type or metadata.get("docTypeCode")
    if not document_type:
        raise ValueError("Supply --document-type or --metadata with the listing's docTypeCode")
    from edinet_tools.api import fetch_document, is_zip_payload

    kind = 5 if source == "csv" else 1
    raw = _edinet_request(fetch_document, document_id, type=kind)
    if not is_zip_payload(raw):
        raise RuntimeError("EDINET returned no ZIP archive; check the filing's xbrlFlag/csvFlag and credential")
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    original = destination / f"{document_id}-type{kind}.zip"
    from tempfile import NamedTemporaryFile

    temporary = None
    try:
        with NamedTemporaryFile("wb", dir=destination, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        temporary.replace(original)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    result = parse_edinet(raw, source=source, document_id=document_id,
                          document_type=str(document_type), metadata=metadata)
    return {**result, "original_path": str(original.resolve()),
            "announcement_id": f"EDINET:{document_id}",
            "parent_document_id": metadata.get("parentDocID"),
            "fetched_at": datetime.now(timezone.utc).isoformat()}


def estat(action: str = "data", *, stats_data_id: str | None = None,
          parameters: dict[str, str] | None = None) -> dict:
    """Retrieve e-Stat tables, metadata or every requested data page using ESTAT_APP_ID."""
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import urlopen

    key = _credential("ESTAT_APP_ID", "https://www.e-stat.go.jp/api/api-info/api-guide")
    operations = {"list": ("getStatsList", "GET_STATS_LIST"),
                  "metadata": ("getMetaInfo", "GET_META_INFO"),
                  "data": ("getStatsData", "GET_STATS_DATA")}
    if action not in operations:
        raise ValueError("e-Stat action must be list, metadata or data")
    params = {"lang": "J", **(parameters or {})}
    if any(re.sub(r"[-_]", "", k).lower() in {"appid", "apikey", "subscriptionkey", "token", "authorization"} for k in params):
        raise ValueError("Supply e-Stat credentials only through ESTAT_APP_ID")
    if action != "list":
        if not stats_data_id:
            raise ValueError("e-Stat data and metadata require --stats-data-id")
        params["statsDataId"] = stats_data_id
    endpoint, envelope = operations[action]
    base = f"https://api.e-stat.go.jp/rest/3.0/app/json/{endpoint}"
    pages, observations = [], []
    table = classes = None
    while True:
        public_url = base + "?" + urlencode(params)
        request_url = base + "?" + urlencode({**params, "appId": key})
        try:
            with urlopen(request_url, timeout=45) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            raise RuntimeError(f"e-Stat returned HTTP {error.code} for {public_url}") from None
        except (URLError, ValueError):
            raise RuntimeError(f"e-Stat request failed for {public_url}") from None
        payload = _public_payload(payload, key)
        body = payload.get(envelope, {})
        status = body.get("RESULT", {}).get("STATUS")
        if str(status) != "0":
            raise RuntimeError(f"e-Stat returned status {status} for {public_url}: "
                               f"{body.get('RESULT', {}).get('ERROR_MSG', 'invalid response')}")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        pages.append({"source_url": public_url, "payload_sha256": hashlib.sha256(encoded).hexdigest(),
                      "hash_scope": "sanitized_json", "fetched_at": datetime.now(timezone.utc).isoformat()})
        if action != "data":
            return {"source": "e-Stat", "data": payload, "acquisition": pages}
        statistical = body.get("STATISTICAL_DATA", {})
        table = statistical.get("TABLE_INF") or table
        classes = statistical.get("CLASS_INF") or classes
        values = statistical.get("DATA_INF", {}).get("VALUE", [])
        if isinstance(values, dict):
            values = [values]
        for item in values:
            raw = item.get("$", "")
            try:
                value = Decimal(str(raw).replace(",", ""))
                if not value.is_finite():
                    value = raw
            except ArithmeticError:
                value = raw
            observations.append({"value": value, "reported_value": raw, "unit": item.get("@unit"),
                                 "dimensions": {k[1:]: v for k, v in item.items() if k.startswith("@") and k != "@unit"}})
        next_position = statistical.get("RESULT_INF", {}).get("NEXT_KEY")
        if next_position in (None, "", 0, "0"):
            return {"source": "e-Stat", "stats_data_id": stats_data_id,
                    "table": table, "classes": classes,
                    "records": observations, "acquisition": pages}
        if int(next_position) <= int(params.get("startPosition", 1)):
            raise RuntimeError("e-Stat pagination did not advance")
        params["startPosition"] = str(next_position)
        time.sleep(1)


def normalize_sec(payload: dict, *, as_of: str | None = None,
                  start_date: str | None = None, end_date: str | None = None,
                  concepts: list[str] | None = None) -> dict:
    """Retain each SEC filing vintage, unit and fiscal duration separately."""
    if not isinstance(payload.get("facts"), dict) or "cik" not in payload:
        raise ValueError("Input must be a SEC companyfacts JSON object")
    for value in (as_of, start_date, end_date):
        if value and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Dates must use YYYY-MM-DD")
    cik = str(int(payload["cik"]))
    records, definitions = [], {}
    for taxonomy, tags in payload["facts"].items():
        for concept, definition in tags.items():
            key = f"{taxonomy}:{concept}"
            if concepts and key not in concepts and concept not in concepts:
                continue
            definitions[key] = {"label": definition.get("label"),
                                "description": definition.get("description")}
            for unit, observations in definition.get("units", {}).items():
                for observation in observations:
                    if as_of and observation.get("filed", "9999") > as_of:
                        continue
                    period_end = observation.get("end", "")
                    if start_date and period_end < start_date:
                        continue
                    if end_date and period_end > end_date:
                        continue
                    accession = observation.get("accn")
                    filing_url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                                  f"{accession.replace('-', '')}/") if accession else None
                    records.append({
                        "source": "SEC", "entity_id": cik, "taxonomy": taxonomy,
                        "concept": concept, "unit": unit, "value": observation["val"],
                        "start": observation.get("start"), "end": period_end,
                        "filed": observation.get("filed"), "form": observation.get("form"),
                        "accession": accession, "fiscal_year": observation.get("fy"),
                        "fiscal_period": observation.get("fp"), "frame": observation.get("frame"),
                        "dimensions": {}, "scope": "entity", "source_url": filing_url,
                    })
    return {"source": "SEC", "entity_id": cik, "company": payload.get("entityName"),
            "as_of": as_of, "definitions": definitions, "records": records}


def xbrl_records(facts: Any, *, source: str, metadata: dict,
                 source_url: str | None) -> list[dict]:
    """Keep filing-specific contexts, dimensions and resolved units together."""
    from edinet_tools.parsers.extraction import parse_decimal

    records = []
    for fact in facts.facts:
        contexts = facts.contexts_by_filing.get(fact.filing, facts.contexts)
        units = facts.units_by_filing.get(fact.filing, facts.units)
        context = contexts[fact.context_id]
        taxonomy, separator, concept = fact.element_id.partition(":")
        number = parse_decimal(fact.value) if fact.unit_id and not fact.nil else None
        raw_unit = units.get(fact.unit_id)
        unit = raw_unit.replace("iso4217:", "").replace("xbrli:", "") if raw_unit else raw_unit
        records.append({
            "source": source, "entity_id": context.entity,
            "taxonomy": taxonomy if separator else "", "concept": concept if separator else fact.element_id,
            "value": number if number is not None else fact.value,
            "unit": unit, "unit_definition": raw_unit, "unit_id": fact.unit_id,
            "context": fact.context_id, "dimensions": context.dimensions,
            "start": context.period_start, "end": context.instant or context.period_end,
            "period_type": "instant" if context.instant else "duration" if context.period_start else "forever",
            "decimals": fact.decimals, "nil": fact.nil,
            "filed": metadata.get("filed") or metadata.get("filingDate") or metadata.get("submitDateTime"),
            "accession": metadata.get("accession") or metadata.get("accessionNumber") or metadata.get("docID"),
            "form": metadata.get("form") or metadata.get("docTypeCode"),
            "source_file": fact.source_file, "filing": fact.filing, "source_url": source_url,
        })
    return records


def parse_xbrl_instance(data: bytes, *, source: str = "SEC", metadata: dict | None = None,
                        source_url: str | None = None) -> dict:
    """Read standard US/IFRS XBRL with the installed edinet-tools fact reader.

    SEC's EX-101.INS document contains custom concepts and segment dimensions.
    Its numeric fact values already carry their reporting scale; `decimals`
    specifies reporting precision and is retained without scaling the value.
    """
    from edinet_tools.parsers.xbrl_instance import read_instance

    metadata = metadata or {}
    origin = provenance(data, source_url)
    name = Path(urlsplit(origin["source_url"] or "").path).name or "instance.xml"
    facts = read_instance(data, name=name)
    records = xbrl_records(facts, source=source, metadata=metadata, source_url=origin["source_url"])
    return {"source": source, **origin, "metadata": metadata,
            "entity_ids": sorted({record["entity_id"] for record in records if record["entity_id"]}),
            "records": records}


def sec_filing(cik: str, *, directory: str | Path, accession: str | None = None,
               form: str | None = None, as_of: str | None = None,
               user_agent: str | None = None) -> dict:
    """Acquire an identified SEC filing, save its instance and normalize facts."""
    from urllib.error import HTTPError
    from urllib.parse import quote
    from urllib.request import Request, urlopen
    from tempfile import NamedTemporaryFile

    cik = re.sub(r"^CIK", "", str(cik), flags=re.IGNORECASE)
    if not re.fullmatch(r"\d{1,10}", cik):
        raise ValueError("CIK must contain 1 to 10 digits")
    padded = cik.zfill(10)
    if accession and not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
        raise ValueError("Use accession format 0000320193-26-000020")
    if as_of and date.fromisoformat(as_of).isoformat() != as_of:
        raise ValueError("Evaluation date must use YYYY-MM-DD")
    agent = user_agent or os.environ.get("SEC_USER_AGENT")
    if not agent or any(ord(c) < 32 for c in agent):
        raise ValueError("Set SEC_USER_AGENT or --user-agent to the application name and contact details")

    next_request = 0.0
    requests = []

    def fetch(url: str) -> bytes:
        nonlocal next_request
        delay = next_request - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        next_request = time.monotonic() + .11
        request = Request(url, headers={"User-Agent": agent,
                                        "Accept": "application/json, application/xml, text/html"})
        try:
            with urlopen(request, timeout=45) as response:
                data = response.read()
        except HTTPError as error:
            raise RuntimeError(f"SEC returned HTTP {error.code} for {url}") from None
        requests.append({**provenance(data, url), "bytes": len(data),
                         "fetched_at": datetime.now(timezone.utc).isoformat()})
        return data

    def choose(columns: dict) -> dict | None:
        choices = []
        for i, identifier in enumerate(columns.get("accessionNumber", [])):
            row = {key: values[i] for key, values in columns.items() if isinstance(values, list)}
            if accession and identifier != accession:
                continue
            if as_of and row["filingDate"] > as_of:
                continue
            if form and row.get("form") != form:
                continue
            if not accession and not row.get("isXBRL"):
                continue
            choices.append(row)
        return max(choices, key=lambda row: (row["filingDate"], row["accessionNumber"]), default=None)

    submissions_url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    submissions = json.loads(fetch(submissions_url))
    filing = choose(submissions.get("filings", {}).get("recent", {}))
    if filing is None:
        history = submissions.get("filings", {}).get("files", [])
        for older in sorted(history, key=lambda item: item.get("filingTo", ""), reverse=True):
            if as_of and older.get("filingFrom", "") > as_of:
                continue
            name = older["name"]
            if not re.fullmatch(r"CIK\d{10}-submissions-\d+\.json", name):
                raise ValueError("SEC submissions history contains an invalid filename")
            filing = choose(json.loads(fetch(f"https://data.sec.gov/submissions/{name}")))
            if filing is not None:
                break
    if filing is None:
        raise ValueError("No SEC XBRL filing matches the CIK, accession, form and evaluation date")
    identifier = filing["accessionNumber"]
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{identifier.replace('-', '')}/"
    index = json.loads(fetch(base + "index.json"))
    names = [item["name"] for item in index["directory"]["item"]]
    instances = [name for name in names if re.search(r"(?:_html?\.xml|\.xbrl)$", name, re.IGNORECASE)]
    if len(instances) != 1:
        from lxml import html

        filing_index = html.fromstring(fetch(base + identifier + "-index.html"))
        links = filing_index.xpath("//tr[td[normalize-space(.)='EX-101.INS']]//a/@href")
        instances = [Path(urlsplit(link).path).name for link in links]
        instances = list(dict.fromkeys(name for name in instances if name in names))
    if len(instances) != 1:
        raise ValueError(f"SEC filing index identifies {len(instances)} XBRL instances; select the original document with xbrl")
    filename = instances[0]
    if Path(filename).name != filename:
        raise ValueError("SEC instance filename must name one file")
    source_url = base + quote(filename, safe="")
    data = fetch(source_url)
    metadata = {**filing, "cik": padded, "company": submissions.get("name"),
                "primary_document_url": base + filing["primaryDocument"],
                "submissions_url": submissions_url, "filing_index_url": base + identifier + "-index.html"}
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    original = destination / f"{identifier}-{filename}"
    temporary = None
    try:
        with NamedTemporaryFile("wb", dir=destination, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, original)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    result = parse_xbrl_instance(data, source="SEC", metadata=metadata, source_url=source_url)
    return {**result, "original_path": str(original.resolve()), "as_of": as_of,
            "announcement_id": f"SEC:{int(cik)}:{identifier}",
            "acquisition": requests}


def parse_edinet(data: bytes, *, source: str = "csv", document_id: str = "",
                 document_type: str | None = None, metadata: dict | None = None) -> dict:
    """Use edinet-tools for Japanese GAAP/IFRS/US-GAAP filings and dimensions."""
    from edinet_tools import parse_xbrl
    from edinet_tools.parsers.extraction import extract_csv_from_zip, parse_decimal
    from edinet_tools.parsers.quarterly import parse_quarterly_report
    from edinet_tools.parsers.securities import parse_securities_report
    from edinet_tools.parsers.semi_annual import parse_semi_annual_report

    metadata = metadata or {}
    document_id = document_id or metadata.get("docID", "")
    document_type = document_type or metadata.get("docTypeCode") or "120"
    source_url = (f"https://api.edinet-fsa.go.jp/api/v2/documents/{document_id}"
                  f"?type={5 if source == 'csv' else 1}") if document_id else None
    # Bound the supplied archive before the package parser materializes members.
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(info.file_size for info in archive.infolist()) > 512 * 1024 * 1024:
            raise ValueError("EDINET uncompressed archive exceeds 512 MiB")
    records = []
    summary = None
    if source == "csv":
        files = extract_csv_from_zip(data)
        if not files:
            raise ValueError("EDINET archive contains no parsed CSV records")
        for member in files:
            for row in member["data"]:
                element = row.get("要素ID", "")
                if element == "要素ID":
                    continue
                taxonomy, separator, concept = element.partition(":")
                raw_value = row.get("値")
                number = parse_decimal(raw_value)
                records.append({
                    "source": "EDINET", "entity_id": metadata.get("edinetCode"),
                    "taxonomy": taxonomy if separator else "", "concept": concept if separator else element,
                    "label": row.get("項目名"), "value": number if number is not None else raw_value,
                    "unit": row.get("ユニットID"), "unit_label": row.get("単位"),
                    "context": row.get("コンテキストID"), "dimensions": None,
                    "relative_period": row.get("相対年度"), "consolidation": row.get("連結・個別"),
                    "period_type": row.get("期間・時点"), "start": row.get("period_start"),
                    "end": row.get("instant") or row.get("period_end"),
                    "filed": metadata.get("submitDateTime"), "accession": document_id,
                    "form": document_type, "source_file": member["filename"], "source_url": source_url,
                })
        parser = {"120": parse_securities_report, "130": parse_securities_report,
                  "140": parse_quarterly_report, "150": parse_quarterly_report,
                  "160": parse_semi_annual_report, "170": parse_semi_annual_report}.get(document_type)
        if parser:
            summary = parser(csv_files=files, doc_id=document_id,
                             doc_type_code=document_type).to_dict()
    else:
        from edinet_tools.parsers.ixbrl import read_inline_xbrl_package
        from edinet_tools.parsers.xbrl_instance import read_instance_package

        readers = {"instance": read_instance_package, "xbrl": read_inline_xbrl_package}
        if source not in readers:
            raise ValueError("EDINET source must be csv, instance or xbrl")
        facts = readers[source](data)
        records = xbrl_records(facts, source="EDINET", source_url=source_url,
                               metadata={**metadata, "docID": document_id, "docTypeCode": document_type})
        summary = parse_xbrl(data, document_type, source=source, doc_id=document_id).to_dict()
    if summary:
        summary.pop("raw_facts", None)
        for record in records:
            if not record["entity_id"]:
                record["entity_id"] = summary.get("filer_edinet_code")
    return {"source": "EDINET", **provenance(data, source_url), "document_id": document_id,
            "metadata": metadata, "summary": summary, "records": records}


def extract_document(data: bytes, *, kind: str = "auto", source_url: str | None = None) -> dict:
    """Preserve PDF page numbers and HTML report links with extracted text."""
    if kind == "auto":
        kind = "pdf" if data.lstrip().startswith(b"%PDF-") else "html"
    result = {"kind": kind, **provenance(data, source_url)}
    if kind == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [{"page": i + 1, "text": page.extract_text() or ""}
                 for i, page in enumerate(reader.pages)]
        return {**result, "title": (reader.metadata or {}).get("/Title"),
                "pages": pages, "text": "\n\n".join(p["text"] for p in pages)}
    if kind == "text":
        return {**result, "text": data.decode("utf-8-sig")}
    if kind != "html":
        raise ValueError("Document kind must be auto, html, pdf or text")
    import trafilatura
    from lxml import html

    extracted = trafilatura.extract(data, url=source_url, output_format="json",
                                    with_metadata=True, include_tables=True,
                                    include_links=True, include_comments=False,
                                    favor_recall=True)
    body = json.loads(extracted) if extracted else {}
    tree = html.fromstring(data)
    links = [{"url": urljoin(source_url or "", href), "title": label.strip()}
             for href, label in ((a.get("href", ""), a.text_content()) for a in tree.xpath("//a[@href]"))
             if href and not href.lower().startswith(("javascript:", "mailto:", "#"))]
    return {**result, "title": body.get("title"), "published": body.get("date"),
            "author": body.get("author"), "text": body.get("text", ""), "links": links}


def parse_feed(data: bytes, *, source_url: str | None = None) -> dict:
    """Read publisher RSS/Atom and retain original publication and source URLs."""
    import feedparser

    parsed = feedparser.parse(data)
    if not parsed.version:
        raise ValueError("Input must be an RSS or Atom feed")
    items = []
    for item in parsed.entries:
        link = urljoin(source_url or "", item.get("link", ""))
        record = {"id": item.get("id") or link, "title": item.get("title", ""),
                  "url": link, "published": item.get("published"),
                  "updated": item.get("updated"), "summary": item.get("summary", ""),
                  "source": dict(item.get("source", {})),
                  "content": [part.get("value", "") for part in item.get("content", [])]}
        record["content_sha256"] = hashlib.sha256(
            json.dumps(record, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        items.append(record)
    return {**provenance(data, source_url), "title": parsed.feed.get("title"),
            "publisher_url": parsed.feed.get("link"), "items": items}


def select_facts(payload: dict, mapping: dict) -> dict:
    """Map explicitly selected account, unit, period and context to model fields.

    Each field has a `where` dictionary and optional `multiplier`. The newest
    filed observation is selected inside that exact accounting definition.
    Distinct contexts or values remaining in that vintage require an explicit
    selector. No cross-unit or cross-period summation is performed.
    """
    output = {}
    for field, specification in mapping.items():
        where = specification["where"]
        if not {"concept", "unit"}.issubset(where) or not ("end" in where or "context" in where):
            raise ValueError(f"{field}: specify concept, unit and end or context")
        matches = [r for r in payload["records"] if all(r.get(k) == v for k, v in where.items())]
        if not matches:
            raise ValueError(f"{field}: no fact matches {where}")
        newest = max(r.get("filed") or "" for r in matches)
        matches = [r for r in matches if (r.get("filed") or "") == newest]
        # Retain cross-filing duplicates only when the accounting observation is identical.
        keys = {json.dumps({k: r.get(k) for k in ("taxonomy", "concept", "unit", "start", "end", "context", "dimensions", "value")},
                           sort_keys=True, default=json_value) for r in matches}
        if len(keys) != 1:
            raise ValueError(f"{field}: selector matches {len(keys)} distinct accounting facts")
        selected = matches[0]
        value = selected["value"]
        if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
            raise ValueError(f"{field}: the selected value is not numeric")
        multiplier = specification.get("multiplier", 1)
        output[field] = {"value": float(value) * multiplier,
                         "model_unit": specification.get("model_unit", selected["unit"]),
                         "multiplier": multiplier, "fact": selected}
    return output


def assemble_chunks(chunks: list[dict]) -> bytes:
    """Restore one original document returned by MCP document_bytes calls."""
    if not chunks:
        raise ValueError("At least one document_bytes chunk is required")
    chunks = [chunk.get("structuredContent", chunk) for chunk in chunks]
    chunks.sort(key=lambda chunk: chunk["offset"])
    first = chunks[0]
    expected = (first["documentId"], first["totalBytes"], first["sha256"])
    stream = io.BytesIO()
    for chunk in chunks:
        if (chunk["documentId"], chunk["totalBytes"], chunk["sha256"]) != expected:
            raise ValueError("Chunks must refer to one document and revision")
        if chunk["offset"] != stream.tell():
            raise ValueError(f"Expected byte offset {stream.tell()}, received {chunk['offset']}")
        stream.write(base64.b64decode(chunk["base64"], validate=True))
    data = stream.getvalue()
    if len(data) != expected[1] or hashlib.sha256(data).hexdigest() != expected[2]:
        raise ValueError("Document byte count or SHA-256 does not match its MCP source")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    acquisition = commands.add_parser("sec-filing", help="Acquire and normalize a SEC XBRL filing")
    acquisition.add_argument("--cik", required=True)
    acquisition.add_argument("--accession")
    acquisition.add_argument("--form", help="Filing form, such as 10-K, 10-Q or 20-F")
    acquisition.add_argument("--as-of", help="Latest permitted filing date (YYYY-MM-DD)")
    acquisition.add_argument("--directory", required=True, help="Directory for the original XBRL document")
    acquisition.add_argument("--user-agent", help="SEC declared application and contact; defaults to SEC_USER_AGENT")
    acquisition.add_argument("--output", "-o", help="Normalized JSON output; default stdout")
    listing = commands.add_parser("edinet-list", help="Retrieve a daily filing list using EDINET_API_KEY")
    listing.add_argument("--date", required=True)
    listing.add_argument("--output", "-o")
    filing = commands.add_parser("edinet-filing", help="Save and normalize a filing using EDINET_API_KEY")
    filing.add_argument("--document-id", required=True)
    filing.add_argument("--directory", required=True)
    filing.add_argument("--source", choices=("instance", "csv", "xbrl"), default="instance")
    filing.add_argument("--document-type")
    filing.add_argument("--metadata", help="One row from the daily EDINET listing")
    filing.add_argument("--output", "-o")
    statistics = commands.add_parser("estat", help="Retrieve official statistics using ESTAT_APP_ID")
    statistics.add_argument("--action", choices=("list", "metadata", "data"), default="data")
    statistics.add_argument("--stats-data-id")
    statistics.add_argument("--parameter", action="append", default=[], help="Official query parameter NAME=VALUE; repeatable")
    statistics.add_argument("--output", "-o")
    for command in ("sec", "xbrl", "edinet", "extract", "feed", "select", "assemble"):
        child = commands.add_parser(command)
        child.add_argument("input", help="Local input file; - reads stdin")
        child.add_argument("--output", "-o", required=command == "assemble",
                           help="Output file; default JSON to stdout")
        if command == "sec":
            child.add_argument("--as-of")
            child.add_argument("--start-date")
            child.add_argument("--end-date")
            child.add_argument("--concept", action="append")
        elif command == "xbrl":
            child.add_argument("--source", default="SEC", help="Filing authority or publisher")
            child.add_argument("--metadata", help="Filing record JSON with accession, filed and form")
            child.add_argument("--url", required=True, help="Original XBRL instance URL")
        elif command == "edinet":
            child.add_argument("--source", choices=("csv", "instance", "xbrl"), default="csv")
            child.add_argument("--document-id", default="")
            child.add_argument("--document-type")
            child.add_argument("--metadata", help="EDINET listing record JSON")
        elif command in ("extract", "feed"):
            child.add_argument("--url")
            if command == "extract":
                child.add_argument("--kind", choices=("auto", "html", "pdf", "text"), default="auto")
        elif command == "select":
            child.add_argument("--mapping", required=True, help="JSON field selectors")
    args = parser.parse_args()
    if args.command == "sec-filing":
        result = sec_filing(args.cik, directory=args.directory, accession=args.accession,
                            form=args.form, as_of=args.as_of, user_agent=args.user_agent)
    elif args.command == "edinet-list":
        result = edinet_list(args.date)
    elif args.command == "edinet-filing":
        metadata = json.loads(Path(args.metadata).read_text()) if args.metadata else None
        result = edinet_filing(args.document_id, directory=args.directory, source=args.source,
                               document_type=args.document_type, metadata=metadata)
    elif args.command == "estat":
        parameters = {}
        for item in args.parameter:
            key, separator, value = item.partition("=")
            if not separator or not key or key in parameters:
                raise ValueError("Use each --parameter NAME=VALUE once")
            parameters[key] = value
        result = estat(args.action, stats_data_id=args.stats_data_id, parameters=parameters)
    else:
        data = sys.stdin.buffer.read() if args.input == "-" else Path(args.input).read_bytes()
    if args.command == "sec":
        result = normalize_sec(json.loads(data), as_of=args.as_of, start_date=args.start_date,
                               end_date=args.end_date, concepts=args.concept)
        result.update(provenance(data, f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(result['entity_id']):010d}.json"))
    elif args.command == "xbrl":
        metadata = json.loads(Path(args.metadata).read_text()) if args.metadata else None
        result = parse_xbrl_instance(data, source=args.source, metadata=metadata, source_url=args.url)
    elif args.command == "edinet":
        metadata = json.loads(Path(args.metadata).read_text()) if args.metadata else None
        result = parse_edinet(data, source=args.source, document_id=args.document_id,
                              document_type=args.document_type, metadata=metadata)
    elif args.command == "extract":
        result = extract_document(data, kind=args.kind, source_url=args.url)
    elif args.command == "feed":
        result = parse_feed(data, source_url=args.url)
    elif args.command == "select":
        result = select_facts(json.loads(data), json.loads(Path(args.mapping).read_text()))
    elif args.command == "assemble":
        result = assemble_chunks(json.loads(data))
    encoded = result if isinstance(result, bytes) else (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False, default=json_value) + "\n"
    ).encode("utf-8")
    if args.output:
        from os import replace
        from tempfile import NamedTemporaryFile

        destination = Path(args.output)
        temporary = None
        try:
            with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
            replace(temporary, destination)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
    else:
        sys.stdout.buffer.write(encoded)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        message = str(error)
        for variable in ("EDINET_API_KEY", "ESTAT_APP_ID"):
            if credential := os.environ.get(variable, "").strip():
                message = _public_payload(message, credential)
        print(f"equity_sources: {message}", file=sys.stderr)
        raise SystemExit(2) from None
