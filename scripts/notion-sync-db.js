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

const notion = new NotionClient({ auth: NOTION_TOKEN });

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

function toNotionProps(entry, pdfUrl) {
  const authorsText = (entry.authors || []).join("; ");
  const tags = entry.keywords?.length ? entry.keywords : DEFAULT_TAGS;
  return {
    "Bib Key": { rich_text: rich(entry.key || "") },
    Title: { title: titleProp(entry.title || entry.key || "(no title)") },
    Authors: { rich_text: rich(authorsText) },
    Year: { number: typeof entry.year === "number" ? entry.year : null },
    Venue: { rich_text: rich(entry.venue || "") },
    DOI: { url: entry.doi || null },
    URL: { url: entry.url || null },
    Abstract: { rich_text: rich(entry.abstract || "") },
    Code: { url: entry.code || null },
    Tags: { multi_select: multiSelect(tags) },
    Updated: { date: { start: new Date().toISOString() } },
    PDF: { files: filePropFromUrl(pdfUrl) },
  };
}

async function findExistingPage(entry) {
  // Prefer DOI, then URL, then Bib Key, then Title
  if (entry.doi) {
    const r = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "DOI", url: { equals: entry.doi } },
      page_size: 1,
    });
    if (r.results?.[0]) return r.results[0];
  }
  if (entry.url) {
    const r = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "URL", url: { equals: entry.url } },
      page_size: 1,
    });
    if (r.results?.[0]) return r.results[0];
  }
  if (entry.key) {
    const r = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "Bib Key", rich_text: { equals: entry.key } },
      page_size: 1,
    });
    if (r.results?.[0]) return r.results[0];
  }
  if (entry.title) {
    const r = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "Title", title: { equals: entry.title } },
      page_size: 1,
    });
    if (r.results?.[0]) return r.results[0];
  }
  return null;
}

async function upsertEntry(entry, pdfUrl) {
  const props = toNotionProps(entry, pdfUrl);
  const existing = await findExistingPage(entry);
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
  // 1) Read bibliography
  const bibPath = path.isAbsolute(BIB_SOURCE)
    ? BIB_SOURCE
    : path.join(process.cwd(), BIB_SOURCE);
  if (!fs.existsSync(bibPath)) {
    console.error(`BIB_SOURCE not found: ${bibPath}`);
    process.exit(1);
  }
  const entries = parseBibliography(bibPath);
  console.log(`Loaded ${entries.length} entries from ${BIB_SOURCE}`);

  // 2) Optionally list Drive PDFs
  let driveFiles = [];
  if (DRIVE_FOLDER_ID && GOOGLE_API_KEY) {
    driveFiles = await listDrivePdfs(DRIVE_FOLDER_ID);
    console.log(`Drive PDFs available: ${driveFiles.length}`);
  } else {
    console.log("Skipping Drive scan (GOOGLE_API_KEY or DRIVE_FOLDER_ID missing)");
  }

  // 3) Upsert entries to Notion
  let created = 0;
  let updated = 0;
  for (const e of entries) {
    const pdf = driveFiles.length ? matchPdf(e, driveFiles) : null;
    const pdfUrl = pdf?.webViewLink || null;
    try {
      const res = await upsertEntry(e, pdfUrl);
      if (res.action === "created") created++;
      else updated++;
    } catch (err) {
      console.error("Failed to upsert entry:", e.key || e.title, err?.message || err);
    }
  }
  console.log(`Done. Created: ${created}, Updated: ${updated}`);
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
