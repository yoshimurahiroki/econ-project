import fs from "fs";
import path from "path";
import * as bibtexParse from "bibtex-parse-js";

function parseAuthorsBibtex(authorField) {
  if (!authorField) return [];
  return String(authorField)
    .split(/\s+and\s+/i)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((a) => {
      if (a.includes(",")) {
        const [last, first] = a.split(",").map((x) => x.trim());
        return [first, last].filter(Boolean).join(" ");
      }
      return a;
    });
}

function extractKeyFromBlock(block) {
  const m = block.match(/@[^{]+\{\s*([^,\s]+)\s*,/);
  return m ? m[1] : "";
}

function splitBibtexByBalancedBraces(str) {
  const entries = [];
  const re = /@[a-zA-Z]+\s*\{/g;
  let m;
  while ((m = re.exec(str)) !== null) {
    const startAt = m.index;
    let i = m.index;
    while (i < str.length && str[i] !== '{') i++;
    if (i >= str.length) break;
    let depth = 0;
    let endAt = -1;
    for (let j = i; j < str.length; j++) {
      const ch = str[j];
      if (ch === '{') depth++;
      else if (ch === '}') {
        depth--;
        if (depth === 0) {
          endAt = j;
          break;
        }
      }
    }
    if (endAt !== -1) {
      const block = str.slice(startAt, endAt + 1);
      entries.push(block);
      re.lastIndex = endAt + 1;
    } else {
      break;
    }
  }
  return entries;
}

function parseBibtex(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");

  function mapEntriesFromJSON(entries) {
    return entries.map((e) => {
      const f = e.entryTags || {};
      const entryType = e.entryType || f.entryType || "";
      const key = e.citationKey || f.key || "";
      const title = (f.title || "").replace(/[{}]/g, "").trim();
      const authors = parseAuthorsBibtex(f.author);
      const year = f.year ? Number(String(f.year).match(/\d{4}/)?.[0]) : undefined;
      const venue = f.journal || f.booktitle || f.publisher || "";
      const volume = f.volume || "";
      const number = f.number || "";
      const pages = f.pages || "";
      const issue = f.issue || "";
      const type = f.type || entryType || "";
      const doi = f.doi ? `https://doi.org/${String(f.doi).replace(/^https?:\/\/doi\.org\//, "")}` : "";
      const url = f.url || "";
      const abstract = f.abstract || "";
      const keywords = String(f.keywords || "")
        .split(/[;,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      return {
        key,
        title,
        authors,
        year,
        venue,
        volume,
        number,
        pages,
        issue,
        type,
        doi,
        url,
        abstract,
        keywords,
        pdf: "",
        code: "",
        tags: [],
      };
    });
  }

  // First try: parse entire file
  try {
    const entries = bibtexParse.toJSON(raw);
    return mapEntriesFromJSON(entries);
  } catch (err) {
    // Fallback: split by balanced braces and parse each entry independently
    const chunks = splitBibtexByBalancedBraces(raw);
    const ok = [];
    for (const chunk of chunks) {
      try {
        const r = bibtexParse.toJSON(chunk);
        if (Array.isArray(r) && r.length) ok.push(...r);
      } catch (e) {
        const key = extractKeyFromBlock(chunk) || "";
        console.warn(
          `Skipping malformed BibTeX entry due to parse error: ${(e && e.message) || e}\n for key: ${key}`
        );
      }
    }
    return mapEntriesFromJSON(ok);
  }
}

function parseCSLJSON(filePath) {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const arr = Array.isArray(raw) ? raw : [raw];
  return arr.map((r) => {
    const key = r.id || r.citekey || "";
    const title = (r.title || "").trim();
    const authors = (r.author || [])
      .map((a) => [a.given, a.family].filter(Boolean).join(" "))
      .filter(Boolean);
    const year = r.issued?.["date-parts"]?.[0]?.[0] || r.issued?.year || undefined;
    const venue = r["container-title"] || r.publisher || r["collection-title"] || "";
    const doi = r.DOI ? `https://doi.org/${r.DOI}` : "";
    const url = r.URL || "";
    const abstract = r.abstract || "";
    const keywords = (r.keyword || r.keywords || "")
      .split(/[;,]/)
      .map((s) => s.trim())
      .filter(Boolean);
    const code = r.code || "";
    return { key, title, authors, year, venue, doi, url, abstract, keywords, pdf: "", code, tags: [] };
  });
}

export function parseBibliography(inputPath) {
  const ext = path.extname(inputPath).toLowerCase();
  if (ext === ".bib") return parseBibtex(inputPath);
  if (ext === ".json" || ext === ".csljson") return parseCSLJSON(inputPath);
  throw new Error(`Unsupported bibliography format: ${ext}`);
}
