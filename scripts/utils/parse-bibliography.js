import fs from "fs";
import path from "path";
import * as bibtexParse from "bibtex-parse-js";
import { Cite } from "@citation-js/core";
import "@citation-js/plugin-bibtex";

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
      // Skip non-entry constructs
      const head = block.slice(0, 32).toLowerCase();
      if (!/^@\s*(string|comment|preamble)\s*\{/.test(head)) {
        entries.push(block);
      }
      re.lastIndex = endAt + 1;
    } else {
      break;
    }
  }
  return entries;
}

function parseBibtex(filePath) {
  const raw0 = fs.readFileSync(filePath, "utf8");

  // Normalize bare numeric values like: year = 1994 -> year = {1994}
  function preNormalizeBibtex(s) {
    // Only within field assignments; conservative global replace of = <digits> followed by , or }
    return s.replace(/(=\s*)(\d+)(\s*[,}])/g, ($0, a, b, c) => `${a}{${b}}${c}`);
  }

  const raw = preNormalizeBibtex(raw0);

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
    if (Array.isArray(entries) && entries.length) {
      // If the balanced-brace detector shows many more entries, prefer per-entry fallback
      const estBlocks = splitBibtexByBalancedBraces(raw).length;
      if (estBlocks > entries.length * 1.2) {
        throw new Error(`Primary parser returned ${entries.length} < detected blocks ${estBlocks}; switching to per-entry fallback`);
      }
      return mapEntriesFromJSON(entries);
    }
    throw new Error("bibtex-parse-js returned empty");
  } catch (err) {
    // Fallback A: try Citation.js on entire file
    try {
      const cite = new Cite(raw);
      const data = cite.data || [];
      if (Array.isArray(data) && data.length) {
        return data.map((r) => {
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
    } catch (e2) {
      // continue to per-entry fallback
    }

    // Fallback B: split by balanced braces and parse each entry independently (try both parsers)
    const chunks = splitBibtexByBalancedBraces(raw);
    const ok = [];
    for (const chunk of chunks) {
      let pushed = false;
      try {
        const r = bibtexParse.toJSON(chunk);
        if (Array.isArray(r) && r.length) {
          ok.push(...r);
          pushed = true;
        }
      } catch (e) {
        // ignore; try citation.js next
      }
      if (!pushed) {
        try {
          const cite = new Cite(chunk);
          const data = cite.data || [];
          if (Array.isArray(data) && data.length) {
            // Convert CSL JSON to bibtex-parse-js-like for reuse of mapper
            for (const r of data) {
              const entryTags = {
                title: r.title,
                author: (r.author || [])
                  .map((a) => [a.given, a.family].filter(Boolean).join(" "))
                  .join(" and "),
                year: r.issued?.["date-parts"]?.[0]?.[0] || r.issued?.year || "",
                journal: r["container-title"] || "",
                booktitle: r["collection-title"] || "",
                publisher: r.publisher || "",
                volume: r.volume || "",
                number: r.number || "",
                pages: r.page || "",
                doi: r.DOI || "",
                url: r.URL || "",
                abstract: r.abstract || "",
                keywords: (r.keyword || r.keywords || ""),
                type: r.type || "",
              };
              ok.push({ entryTags, entryType: r.type || "", citationKey: r.id || r.citekey || extractKeyFromBlock(chunk) || "" });
            }
            pushed = true;
          }
        } catch (e3) {
          const key = extractKeyFromBlock(chunk) || "";
          console.warn(
            `Skipping malformed BibTeX entry due to parse error: ${(e3 && e3.message) || e3}\n for key: ${key}`
          );
        }
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
