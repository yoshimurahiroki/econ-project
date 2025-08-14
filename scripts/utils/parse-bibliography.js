import fs from "fs";
import path from "path";
import * as bibtexParse from "bibtex-parse-js";

function parseAuthorsBibtex(authorField) {
  if (!authorField) return [];
  return authorField
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

function parseBibtex(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");

  function mapEntries(entries) {
    return entries.map((e) => {
      const f = e.entryTags || {};
      const key = e.citationKey || f.key || "";
      const title = (f.title || "").replace(/[{}]/g, "").trim();
      const authors = parseAuthorsBibtex(f.author);
      const year = f.year ? Number(String(f.year).match(/\d{4}/)?.[0]) : undefined;
      const venue = f.journal || f.booktitle || f.publisher || "";
      const doi = f.doi ? `https://doi.org/${String(f.doi).replace(/^https?:\/\/doi\.org\//, "")}` : "";
      const url = f.url || "";
      const abstract = f.abstract || "";
      const keywords = String(f.keywords || "")
        .split(/[;,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      return { key, title, authors, year, venue, doi, url, abstract, keywords, pdf: "", code: "", tags: [] };
    });
  }

  // First try: parse entire file
  try {
    const entries = bibtexParse.toJSON(raw);
    return mapEntries(entries);
  } catch (err) {
    // Fallback: parse entry-by-entry and skip malformed ones
    const chunks = raw.split(/(?=@[a-zA-Z]+\s*\{)/g).filter((c) => c.trim().startsWith("@"));
    const ok = [];
    for (const chunk of chunks) {
      try {
        const r = bibtexParse.toJSON(chunk);
        // Filter out non-standard or empty results
        if (Array.isArray(r) && r.length) ok.push(...r);
      } catch (e) {
        // Skip bad chunk with a lightweight notice to stderr
        console.warn("Skipping malformed BibTeX entry due to parse error:", (e && e.message) || e);
      }
    }
    return mapEntries(ok);
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
