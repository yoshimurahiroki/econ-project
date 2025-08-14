// Sync bibliography entries to a Notion database and attach matching PDFs from Google Drive
// Env:
// - NOTION_TOKEN (required)
// - NOTION_DB_ID (required)
// - BIB_SOURCE (required) path to .bib or CSL-JSON file
// - GOOGLE_API_KEY (optional) for public Drive listing
// - DRIVE_FOLDER_ID (optional) Google Drive folder to search PDFs
// - DEFAULT_TAGS (optional) comma-separated default tags

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import fetch from "node-fetch";
import { Client as NotionClient } from "@notionhq/client";
import { parseBibliography } from "./utils/parse-bibliography.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function env(name, optional = false) {
  const v = process.env[name];
  if (!optional && !v) {
    console.error(`Missing env ${name}`);
    process.exit(1);
  }
  return v;
}

const NOTION_TOKEN = env("NOTION_TOKEN");
const NOTION_DB_ID = env("NOTION_DB_ID");
const BIB_SOURCE = env("BIB_SOURCE");
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || "";
const DRIVE_FOLDER_ID = process.env.DRIVE_FOLDER_ID || "";
const DEFAULT_TAGS = (process.env.DEFAULT_TAGS || "")
  .split(/[,;]+/)
  .map((s) => s.trim())
  .filter(Boolean);
const SKIP_PDF = /^(1|true|yes)$/i.test(String(process.env.SKIP_PDF || ""));

const notion = new NotionClient({ auth: NOTION_TOKEN });

// ---- Notion DB schema helpers ----
async function getDatabaseSchema(dbId) {
  const db = await notion.databases.retrieve({ database_id: dbId });
  // properties: { Name: {id, type, ...}, ... }
  return db.properties || {};
}

function findTitlePropName(dbProps) {
  // find first property typed 'title'
  for (const [name, def] of Object.entries(dbProps)) {
    if (def?.type === "title") return name;
  }
  return null;
}

function prop(dbProps, name) {
  return dbProps[name] || null;
}

function hasProp(dbProps, name, type) {
  const p = prop(dbProps, name);
  if (!p) return false;
  return type ? p.type === type : true;
}

// ---- Google Drive helpers ----
async function listDrivePdfs(folderId) {
  if (!folderId || !GOOGLE_API_KEY) return [];
  const url = new URL("https://www.googleapis.com/drive/v3/files");
  // Only public/anyone-with-link files can be listed with API key
  url.searchParams.set(
    "q",
    `'${folderId}' in parents and mimeType='application/pdf' and trashed=false`
  );
  url.searchParams.set("fields", "files(id,name,webViewLink,modifiedTime)");
  url.searchParams.set("key", GOOGLE_API_KEY);
  const res = await fetch(url.toString());
  if (!res.ok) {
    const t = await res.text();
    console.warn("Drive list failed:", res.status, t);
    return [];
  }
  const data = await res.json();
  return data.files || [];
}

// ---- Matching helpers ----
function normalize(s) {
  return String(s || "").toLowerCase();
}
function slugTitle(s) {
  return normalize(s).replace(/[^a-z0-9]+/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "");
}
function firstAuthorLast(authors) {
  if (!authors?.length) return "";
  const a0 = authors[0].trim();
  const parts = a0.split(/\s+/);
  return parts.length ? parts[parts.length - 1] : a0;
}
function firstAuthorFull(authors) {
  return (authors && authors.length) ? authors[0] : "";
}
function buildNameCandidates(entry) {
  const last = normalize(firstAuthorLast(entry.authors));
  const year = entry.year ? String(entry.year) : "";
  const t = slugTitle(entry.title || "");
  const variants = [
    `${last}${year}-${t}`,
    `${last}_${year}-${t}`,
    `${last}${year}_${t}`,
    `${last}-${year}-${t}`,
    `${last}${year}${t}`,
  ].filter(Boolean);
  return variants;
}
function compact(s) {
  return normalize(s).replace(/\W+/g, "");
}
function matchPdf(entry, files) {
  if (!files?.length) return null;
  const candidates = buildNameCandidates(entry);
  const nameMap = new Map();
  for (const f of files) nameMap.set(normalize(f.name.replace(/\.pdf$/i, "")), f);
  // exact candidate match
  for (const c of candidates) {
    if (nameMap.has(c)) return nameMap.get(c);
  }
  // compact match
  const byCompact = new Map();
  for (const f of files) byCompact.set(compact(f.name), f);
  for (const c of candidates) {
    const k = compact(c);
    if (byCompact.has(k)) return byCompact.get(k);
  }
  // longest title substring
  const title = slugTitle(entry.title || "");
  let best = null;
  let bestLen = 0;
  for (const f of files) {
    const base = slugTitle(f.name.replace(/\.pdf$/i, ""));
    if (base.includes(title) && title.length > bestLen) {
      best = f;
      bestLen = title.length;
    }
  }
  return best;
}

// ---- Notion helpers ----
function rich(text) {
  return [{ type: "text", text: { content: text ?? "" } }];
}
function titleProp(text) {
  return [{ type: "text", text: { content: text ?? "" } }];
}
function multiSelect(tags) {
  return (tags || []).map((t) => ({ name: String(t) }));
}
function filePropFromUrl(url) {
  if (!url) return [];
  return [
    {
      name: "PDF",
      type: "external",
      external: { url },
    },
  ];
}

function toNotionProps(entry, pdfUrl, dbProps) {
  const authorsText = (entry.authors || []).join("; ");
  const tags = entry.keywords?.length ? entry.keywords : DEFAULT_TAGS;
  const out = {};

  // Title: use actual title property name
  const titleName = findTitlePropName(dbProps) || "Title";
  if (hasProp(dbProps, titleName, "title")) {
    out[titleName] = { title: titleProp(entry.title || entry.key || "(no title)") };
  }

  // Bib Key (rich_text)
  if (hasProp(dbProps, "Bib Key", "rich_text")) {
    out["Bib Key"] = { rich_text: rich(entry.key || "") };
  }

  // Authors / Author
  if (hasProp(dbProps, "Authors", "rich_text")) {
    out["Authors"] = { rich_text: rich(authorsText) };
  } else if (hasProp(dbProps, "Author", "rich_text")) {
    out["Author"] = { rich_text: rich(authorsText) };
  }

  // First Author
  if (hasProp(dbProps, "First Author", "rich_text")) {
    out["First Author"] = { rich_text: rich(firstAuthorFull(entry.authors)) };
  }

  // Year
  if (hasProp(dbProps, "Year", "number")) {
    out["Year"] = { number: typeof entry.year === "number" ? entry.year : null };
  }

  // Venue / Journal: prefer rich_text; fallback select
  if (hasProp(dbProps, "Venue", "rich_text")) {
    out["Venue"] = { rich_text: rich(entry.venue || "") };
  } else if (hasProp(dbProps, "Venue", "select")) {
    const v = (entry.venue || "").trim();
    out["Venue"] = { select: v ? { name: v } : null };
  } else if (hasProp(dbProps, "Journal", "rich_text")) {
    out["Journal"] = { rich_text: rich(entry.venue || "") };
  }

  // Volume / Number / Pages / Issue / Type
  if (hasProp(dbProps, "Volume", "rich_text")) out["Volume"] = { rich_text: rich(entry.volume || "") };
  if (hasProp(dbProps, "Number", "rich_text")) out["Number"] = { rich_text: rich(entry.number || "") };
  if (hasProp(dbProps, "Pages", "rich_text")) out["Pages"] = { rich_text: rich(entry.pages || "") };
  if (hasProp(dbProps, "Issue", "rich_text")) out["Issue"] = { rich_text: rich(entry.issue || "") };
  if (hasProp(dbProps, "Type", "rich_text")) out["Type"] = { rich_text: rich(entry.type || "") };

  // DOI: support url or rich_text
  if (prop(dbProps, "DOI")) {
    const t = prop(dbProps, "DOI").type;
    if (t === "url") out["DOI"] = { url: entry.doi || null };
    else if (t === "rich_text") out["DOI"] = { rich_text: rich(entry.doi || "") };
  }

  // URL: support url or rich_text
  if (prop(dbProps, "URL")) {
    const t = prop(dbProps, "URL").type;
    if (t === "url") out["URL"] = { url: entry.url || null };
    else if (t === "rich_text") out["URL"] = { rich_text: rich(entry.url || "") };
  }

  // Abstract
  if (hasProp(dbProps, "Abstract", "rich_text")) {
    out["Abstract"] = { rich_text: rich(entry.abstract || "") };
  } else if (hasProp(dbProps, "Abstract Origin", "rich_text")) {
    out["Abstract Origin"] = { rich_text: rich(entry.abstract || "") };
  }

  // Code
  if (prop(dbProps, "Code")) {
    const t = prop(dbProps, "Code").type;
    if (t === "url") out["Code"] = { url: entry.code || null };
    else if (t === "rich_text") out["Code"] = { rich_text: rich(entry.code || "") };
  }

  // Tags: multi_select or select
  if (hasProp(dbProps, "Tags", "multi_select")) {
    out["Tags"] = { multi_select: multiSelect(tags) };
  } else if (hasProp(dbProps, "Tags", "select")) {
    const first = (tags || [])[0];
    out["Tags"] = { select: first ? { name: first } : null };
  }

  // Updated
  if (hasProp(dbProps, "Updated", "date")) {
    out["Updated"] = { date: { start: new Date().toISOString() } };
  }

  // PDF / File Path (skip if SKIP_PDF)
  if (!SKIP_PDF) {
    if (hasProp(dbProps, "PDF", "files")) {
      out["PDF"] = { files: filePropFromUrl(pdfUrl) };
    }
    if (prop(dbProps, "File Path")) {
      const t = prop(dbProps, "File Path").type;
      if (t === "url") out["File Path"] = { url: pdfUrl || null };
      else if (t === "rich_text") out["File Path"] = { rich_text: rich(pdfUrl || "") };
    }
  }

  return out;
}

async function findExistingPage(entry, dbProps) {
  // Prefer DOI, then URL, then Bib Key, then Title (type-aware)
  if (entry.doi && prop(dbProps, "DOI")) {
    const t = prop(dbProps, "DOI").type;
    const filter = t === "url"
      ? { property: "DOI", url: { equals: entry.doi } }
      : { property: "DOI", rich_text: { equals: entry.doi } };
    const r = await notion.databases.query({ database_id: NOTION_DB_ID, filter, page_size: 1 });
    if (r.results?.[0]) return r.results[0];
  }

  if (entry.url && prop(dbProps, "URL")) {
    const t = prop(dbProps, "URL").type;
    const filter = t === "url"
      ? { property: "URL", url: { equals: entry.url } }
      : { property: "URL", rich_text: { equals: entry.url } };
    const r = await notion.databases.query({ database_id: NOTION_DB_ID, filter, page_size: 1 });
    if (r.results?.[0]) return r.results[0];
  }

  if (entry.key && hasProp(dbProps, "Bib Key", "rich_text")) {
    const r = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "Bib Key", rich_text: { equals: entry.key } },
      page_size: 1,
    });
    if (r.results?.[0]) return r.results[0];
  }

  const titleName = findTitlePropName(dbProps);
  if (entry.title && titleName) {
    const r = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: titleName, title: { equals: entry.title } },
      page_size: 1,
    });
    if (r.results?.[0]) return r.results[0];
  }
  return null;
}

async function upsertEntry(entry, pdfUrl, dbProps) {
  const props = toNotionProps(entry, pdfUrl, dbProps);
  const existing = await findExistingPage(entry, dbProps);
  if (existing) {
    await notion.pages.update({ page_id: existing.id, properties: props });
    return { id: existing.id, action: "updated" };
  }
  const created = await notion.pages.create({
    parent: { database_id: NOTION_DB_ID },
    properties: props,
  });
  return { id: created.id, action: "created" };
}

async function main() {
  // 1) Read bibliography (local path or URL)
  let bibPath = BIB_SOURCE;
  if (/^https?:\/\//i.test(BIB_SOURCE)) {
    // fetch remote and store to temp file with inferred extension
    const res = await fetch(BIB_SOURCE);
    if (!res.ok) {
      console.error(`Failed to fetch BIB_SOURCE URL: ${BIB_SOURCE} -> ${res.status}`);
      process.exit(1);
    }
    const raw = await res.text();
    const ext = BIB_SOURCE.toLowerCase().endsWith(".json") || BIB_SOURCE.toLowerCase().endsWith(".csljson")
      ? ".json"
      : ".bib";
    const tmp = path.join(process.cwd(), `.bibsource-${Date.now()}${ext}`);
    fs.writeFileSync(tmp, raw, "utf8");
    bibPath = tmp;
  } else {
    bibPath = path.isAbsolute(BIB_SOURCE) ? BIB_SOURCE : path.join(process.cwd(), BIB_SOURCE);
  }
  if (!fs.existsSync(bibPath)) {
    console.error(`BIB_SOURCE not found: ${bibPath}`);
    process.exit(1);
  }
  const entries = parseBibliography(bibPath);
  console.log(`Loaded ${entries.length} entries from ${BIB_SOURCE}`);

  // 2) Optionally list Drive PDFs (skip if SKIP_PDF)
  let driveFiles = [];
  if (SKIP_PDF) {
    console.log("SKIP_PDF enabled: skipping Drive scan and PDF updates");
  } else if (DRIVE_FOLDER_ID && GOOGLE_API_KEY) {
    driveFiles = await listDrivePdfs(DRIVE_FOLDER_ID);
    console.log(`Drive PDFs available: ${driveFiles.length}`);
  } else {
    console.log("Skipping Drive scan (GOOGLE_API_KEY or DRIVE_FOLDER_ID missing)");
  }

  // 3) Load Notion DB schema
  const dbProps = await getDatabaseSchema(NOTION_DB_ID);

  // 4) Upsert entries to Notion
  let created = 0;
  let updated = 0;
  const touched = [];
  for (const e of entries) {
  const pdf = !SKIP_PDF && driveFiles.length ? matchPdf(e, driveFiles) : null;
  const pdfUrl = !SKIP_PDF ? (pdf?.webViewLink || null) : null;
    try {
      const res = await upsertEntry(e, pdfUrl, dbProps);
      if (res.action === "created") created++;
      else updated++;
      touched.push({ bibKey: e.key || "", pageId: res.id, action: res.action });
    } catch (err) {
      console.error("Failed to upsert entry:", e.key || e.title, err?.message || err);
    }
  }
  console.log(`Done. Created: ${created}, Updated: ${updated}`);

  // Write out list of touched entries for downstream jobs (e.g., OCR per paper)
  try {
    const outDir = path.join(process.cwd(), "scripts", ".out");
    fs.mkdirSync(outDir, { recursive: true });
    const outPath = path.join(outDir, "updated.json");
    fs.writeFileSync(outPath, JSON.stringify(touched, null, 2));
    console.log(`Wrote ${touched.length} touched entries to ${outPath}`);
  } catch (e) {
    console.warn("Failed to write touched entries:", e?.message || e);
  }
}

// Execute when run directly (ESM-compatible main check)
const isMain = (() => {
  try {
    return (
      process.argv[1] &&
      path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
    );
  } catch {
    return false;
  }
})();

if (isMain) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
