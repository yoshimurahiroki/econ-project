// Drive → OCR → Notion child blocks pipeline
// Env requirements:
// - GOOGLE_API_KEY (for public/shared files) or implement OAuth for private files (not covered here)
// - DRIVE_FOLDER_ID (Google Drive folder to scan PDFs)
// - NOTION_TOKEN (Notion integration token)
// - NOTION_DB_ID (target database to upsert metadata)
// - CHUNK_SIZE (optional, default 1000)
// - MAX_FILES (optional, limit processed files per run)
// - ENABLE_SQLITE (optional, store chunks locally in sqlite)
// - VECTOR_DB_PATH (optional, path to sqlite db; default ./vector.db)
// - ENABLE_EMBEDDINGS (optional, if true try local embeddings via @xenova/transformers)
// - EMBEDDING_MODEL (optional, default Xenova/all-MiniLM-L6-v2)
// - TESS_LANG (default eng; e.g., 'eng+jpn'), TESS_PSM (default 1), TESS_OEM (default 1), TESS_DPI (default 300), TESS_EXTRA_ARGS

import fs from "fs";
import os from "os";
import path from "path";
import { spawnSync } from "child_process";
import { Client as NotionClient } from "@notionhq/client";
import sqlite3 from "sqlite3";
import fetch from "node-fetch";
import { parseBibliography } from "./utils/parse-bibliography.js";

const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || "";
const DRIVE_FOLDER_ID = process.env.DRIVE_FOLDER_ID || "";
const NOTION_TOKEN = process.env.NOTION_TOKEN || "";
const NOTION_DB_ID = process.env.NOTION_DB_ID || "";
const CHUNK_SIZE = Number(process.env.CHUNK_SIZE || 1000);
const MAX_FILES = process.env.MAX_FILES ? Number(process.env.MAX_FILES) : undefined;
const ENABLE_SQLITE = /^(1|true|yes)$/i.test(String(process.env.ENABLE_SQLITE || "false"));
const VECTOR_DB_PATH = process.env.VECTOR_DB_PATH || path.join(process.cwd(), "vector.db");
const ENABLE_EMBEDDINGS = /^(1|true|yes)$/i.test(String(process.env.ENABLE_EMBEDDINGS || "false"));
const EMBEDDING_MODEL = process.env.EMBEDDING_MODEL || "Xenova/all-MiniLM-L6-v2";
const BIB_SOURCE = process.env.BIB_SOURCE || path.join(process.cwd(), "data/papers/library.bib");

if (!DRIVE_FOLDER_ID || !NOTION_TOKEN || !NOTION_DB_ID) {
  console.error("Required env missing: DRIVE_FOLDER_ID, NOTION_TOKEN, NOTION_DB_ID");
  process.exit(1);
}

const notion = new NotionClient({ auth: NOTION_TOKEN });

function hasCommand(cmd) {
  const p = spawnSync("bash", ["-lc", `command -v ${cmd} >/dev/null 2>&1 && echo yes || echo no`]);
  return String(p.stdout || "").toString().trim() === "yes";
}

async function listDriveFiles(folderId) {
  // Public files listing via API key; for private folders use OAuth/Service Account (not covered here)
  const url = new URL("https://www.googleapis.com/drive/v3/files");
  url.searchParams.set("q", `'${folderId}' in parents and mimeType='application/pdf' and trashed=false`);
  url.searchParams.set("fields", "files(id,name,webViewLink,modifiedTime)");
  if (GOOGLE_API_KEY) url.searchParams.set("key", GOOGLE_API_KEY);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Drive list failed: ${res.status} ${await res.text()}`);
  const data = await res.json();
  return data.files || [];
}

async function downloadDriveFile(fileId, destPath) {
  const url = new URL(`https://www.googleapis.com/drive/v3/files/${fileId}`);
  url.searchParams.set("alt", "media");
  if (GOOGLE_API_KEY) url.searchParams.set("key", GOOGLE_API_KEY);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Drive download failed: ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(destPath, buf);
}

function normalizeKey(s) {
  return String(s || "").toLowerCase().replace(/\.pdf$/i, "").replace(/[^a-z0-9]+/g, " ").trim();
}
function compact(s) {
  return normalizeKey(s).replace(/\s+/g, "");
}
function slugifyAuthorLast(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "").trim();
}
function slugifyTitle(s) {
  // mimic filename-friendly pattern: spaces -> '_', drop other punct, collapse '_'
  return String(s || "")
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]+/g, "")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}
function firstAuthorLastName(rec) {
  const a0 = (rec.authors || [])[0] || ""; // "First Last" 形式を想定
  const parts = String(a0).trim().split(/\s+/);
  return parts.length ? parts[parts.length - 1] : "";
}
function authorYearTitleCandidates(rec) {
  const last = slugifyAuthorLast(firstAuthorLastName(rec));
  const year = rec.year ? String(rec.year) : "";
  const titleSlug = slugifyTitle(rec.title || "");
  const variants = [
    `${last}${year}-${titleSlug}`,
    `${last}_${year}-${titleSlug}`,
    `${last}${year}_${titleSlug}`,
    `${last}-${year}-${titleSlug}`,
    `${last}${year}${titleSlug}`,
  ];
  return variants.filter(Boolean);
}
function buildBibIndex(records) {
  const byKey = new Map();
  const byTitle = new Map();
  const byExact = new Map();
  const byCompact = new Map();
  const byDoi = new Map();
  const byUrl = new Map();
  for (const r of records) {
    if (r.key) {
      const k = normalizeKey(r.key);
      byKey.set(k, r);
      byCompact.set(compact(r.key), r);
    }
    if (r.title) {
      const t = normalizeKey(r.title);
      byTitle.set(t, r);
      byCompact.set(compact(r.title), r);
    }
    for (const v of authorYearTitleCandidates(r)) {
      byExact.set(v.toLowerCase(), r);
      byCompact.set(compact(v), r);
    }
    if (r.doi) byDoi.set(r.doi.replace(/^https?:\/\/doi\.org\//i, "").toLowerCase(), r);
    if (r.url) byUrl.set(String(r.url).trim(), r);
  }
  return { byKey, byTitle, byExact, byCompact, byDoi, byUrl, records };
}
function matchBibForFile(file, idx) {
  const name = String(file?.name || "");
  const base = name.replace(/\.pdf$/i, "").toLowerCase();
  const nameNorm = normalizeKey(name);
  const nameComp = compact(name);
  // 1) exact author+year+title candidates match
  if (idx.byExact.has(base)) return idx.byExact.get(base);
  if (idx.byKey.has(nameNorm)) return idx.byKey.get(nameNorm);
  if (idx.byTitle.has(nameNorm)) return idx.byTitle.get(nameNorm);
  if (idx.byCompact.has(nameComp)) return idx.byCompact.get(nameComp);
  // Heuristic: longest title substring match within filename
  let best = null;
  let bestLen = 0;
  for (const r of idx.records || []) {
    const t = r.title ? normalizeKey(r.title) : "";
    if (t && t.length >= 10 && (nameNorm.includes(t) || nameComp.includes(t.replace(/\s+/g, "")))) {
      if (t.length > bestLen) {
        best = r;
        bestLen = t.length;
      }
    }
  }
  return best;
}

function extractTextWithTesseract(pdfPath) {
  if (!hasCommand("pdftoppm") || !hasCommand("tesseract")) {
    throw new Error("pdftoppm or tesseract not found. Install 'poppler-utils' and 'tesseract-ocr'.");
  }
  const tessLang = process.env.TESS_LANG || "eng"; // e.g., 'eng+jpn'
  const tessPsm = process.env.TESS_PSM || "1"; // auto page seg + OSD
  const tessOem = process.env.TESS_OEM || "1"; // LSTM only
  const tessDpi = process.env.TESS_DPI || "300";
  const tessExtra = (process.env.TESS_EXTRA_ARGS || "").split(/\s+/).filter(Boolean);

  const outBase = pdfPath.replace(/\.pdf$/i, "");
  // Convert PDF pages to PNG@DPI: outBase-1.png, outBase-2.png, ...
  const conv = spawnSync("pdftoppm", ["-png", "-r", tessDpi, pdfPath, outBase], { encoding: "utf8" });
  if (conv.status !== 0) {
    throw new Error(`pdftoppm failed: ${conv.status} ${conv.stderr || conv.stdout || ""}`);
  }
  const dir = path.dirname(outBase);
  const baseName = path.basename(outBase);
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.startsWith(baseName + "-") && f.endsWith(".png"))
    .sort((a, b) => {
      const ai = Number(a.replace(/^.*-(\d+)\.png$/, "$1"));
      const bi = Number(b.replace(/^.*-(\d+)\.png$/, "$1"));
      return ai - bi;
    });

  let fullText = "";
  for (const img of files) {
    const imgPath = path.join(dir, img);
    const args = [imgPath, "stdout", "--psm", tessPsm, "--oem", tessOem, "-l", tessLang, ...tessExtra];
    const ocr = spawnSync("tesseract", args, { encoding: "utf8" });
    if (ocr.status === 0) fullText += (ocr.stdout || "") + "\n\n";
  }
  return fullText.trim();
}

function splitIntoChunks(text, size) {
  const chunks = [];
  for (let i = 0; i < text.length; i += size) {
    chunks.push(text.slice(i, i + size));
  }
  return chunks;
}

function richText(text) {
  return [{ type: "text", text: { content: text ?? "" } }];
}
function titleProp(text) {
  return [{ type: "text", text: { content: text ?? "" } }];
}
function urlProp(url) {
  return url || null;
}
function numberProp(n) {
  return typeof n === "number" && !Number.isNaN(n) ? n : null;
}
function multiSelectProp(tags) {
  return (tags || []).map((t) => ({ name: t }));
}
function selectProp(name) {
  return name ? { name } : null;
}
function filesProp(filePathOrUrl) {
  if (!filePathOrUrl) return [];
  if (/^https?:\/\//.test(filePathOrUrl)) {
    return [{ name: path.basename(filePathOrUrl), type: "external", external: { url: filePathOrUrl } }];
  }
  return [];
}

function toNotionPropsFromFile(file) {
  const title = file.name?.replace(/\.pdf$/i, "") || file.name || "(no title)";
  const url = file.webViewLink || null;
  const defaultTags = (process.env.DEFAULT_TAGS || "").split(/[,;]+/).map((s) => s.trim()).filter(Boolean);
  return {
    Title: { title: titleProp(title) },
    Authors: { rich_text: richText("") },
    Year: { number: numberProp(null) },
    Venue: { select: selectProp(null) },
    Tags: { multi_select: multiSelectProp(defaultTags) },
    DOI: { url: urlProp(null) },
    URL: { url: urlProp(url) },
    Abstract: { rich_text: richText("") },
    Code: { url: urlProp(null) },
    Updated: { date: { start: new Date().toISOString() } },
    PDF: { files: filesProp(url) }
  };
}

function toNotionPropsFromBib(rec, file) {
  const defaultTags = (process.env.DEFAULT_TAGS || "").split(/[,;]+/).map((s) => s.trim()).filter(Boolean);
  const doiUrl = rec.doi
    ? `https://doi.org/${String(rec.doi).replace(/^https?:\/\/doi\.org\//i, "")}`
    : null;
  const pdfUrl = file?.webViewLink || "";
  return {
    Title: { title: titleProp(rec.title || rec.key || "(no title)") },
    Authors: { rich_text: richText((rec.authors || []).join("; ")) },
    Year: { number: numberProp(rec.year) },
    Venue: { select: selectProp(rec.venue || null) },
    Tags: { multi_select: multiSelectProp(rec.tags?.length ? rec.tags : rec.keywords || defaultTags) },
    DOI: { url: urlProp(doiUrl) },
    URL: { url: urlProp(rec.url || null) },
    Abstract: { rich_text: richText(rec.abstract || "") },
    Code: { url: urlProp(rec.code || null) },
    Updated: { date: { start: new Date().toISOString() } },
    PDF: { files: filesProp(pdfUrl) }
  };
}

async function findPageByUrl(dbId, url) {
  if (!url) return null;
  const res = await notion.databases.query({
    database_id: dbId,
    filter: { property: "URL", url: { equals: url } },
    page_size: 1
  });
  return res.results?.[0] || null;
}

async function findPageForBib(rec) {
  // Prefer DOI, then URL, then Title
  if (rec?.doi) {
    const doiUrl = `https://doi.org/${String(rec.doi).replace(/^https?:\/\/doi\.org\//i, "")}`;
    const res = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "DOI", url: { equals: doiUrl } },
      page_size: 1
    });
    if (res.results?.[0]) return res.results[0];
  }
  if (rec?.url) {
    const res = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "URL", url: { equals: String(rec.url).trim() } },
      page_size: 1
    });
    if (res.results?.[0]) return res.results[0];
  }
  if (rec?.title) {
    const res = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: { property: "Title", title: { equals: rec.title } },
      page_size: 1
    });
    if (res.results?.[0]) return res.results[0];
  }
  return null;
}

async function ensurePageForFile(file, rec) {
  if (rec) {
    const existing = await findPageForBib(rec);
    const props = toNotionPropsFromBib(rec, file);
    if (existing) {
      await notion.pages.update({ page_id: existing.id, properties: props });
      return existing.id;
    }
    const page = await notion.pages.create({ parent: { database_id: NOTION_DB_ID }, properties: props });
    return page.id;
  }
  // Fallback: no bib match; use file-based props and look up by URL
  const url = file.webViewLink || null;
  const props = toNotionPropsFromFile(file);
  const existing = await findPageByUrl(NOTION_DB_ID, url);
  if (existing) {
    await notion.pages.update({ page_id: existing.id, properties: props });
    return existing.id;
  }
  const page = await notion.pages.create({ parent: { database_id: NOTION_DB_ID }, properties: props });
  return page.id;
}

async function appendChildren(pageId, chunks) {
  // Notion API: 100 children per request
  const blocks = chunks.map((content) => ({
    object: "block",
    type: "paragraph",
    paragraph: { rich_text: [{ type: "text", text: { content } }] }
  }));
  for (let i = 0; i < blocks.length; i += 100) {
    await notion.blocks.children.append({ block_id: pageId, children: blocks.slice(i, i + 100) });
  }
}

function openVectorDb() {
  if (!ENABLE_SQLITE) return null;
  const db = new sqlite3.Database(VECTOR_DB_PATH);
  db.serialize(() => {
    db.run(
      `CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        text TEXT NOT NULL,
        embedding TEXT,
        notion_page_id TEXT,
        url TEXT
      )`
    );
    db.run("CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id)");
    db.run("CREATE INDEX IF NOT EXISTS idx_chunks_page_id ON chunks(notion_page_id)");
  });
  return db;
}

function ensureColumn(db, table, column, type) {
  return new Promise((resolve, reject) => {
    db.all(`PRAGMA table_info(${table})`, (err, rows) => {
      if (err) return reject(err);
      const has = rows.some((r) => r.name === column);
      if (has) return resolve();
      db.run(`ALTER TABLE ${table} ADD COLUMN ${column} ${type}`, (e) => (e ? reject(e) : resolve()));
    });
  });
}

async function maybeMigrateDb(db) {
  if (!db) return;
  await ensureColumn(db, "chunks", "notion_page_id", "TEXT").catch(() => {});
  await ensureColumn(db, "chunks", "url", "TEXT").catch(() => {});
  await ensureColumn(db, "chunks", "embedding", "TEXT").catch(() => {});
}

async function getEmbedderIfEnabled() {
  if (!ENABLE_EMBEDDINGS) return null;
  try {
    const { pipeline } = await import("@xenova/transformers");
    const embedder = await pipeline("feature-extraction", EMBEDDING_MODEL);
    return async (text) => {
      const output = await embedder(text);
      // output: [tokens][dims]
      const arr = Array.isArray(output) ? output : output?.data || output?.tensor || output;
      const tokens = arr.length;
      const dims = arr[0]?.length || 0;
      const mean = new Array(dims).fill(0);
      for (let i = 0; i < tokens; i++) {
        const row = arr[i];
        for (let j = 0; j < dims; j++) mean[j] += row[j];
      }
      for (let j = 0; j < dims; j++) mean[j] /= Math.max(1, tokens);
      return mean;
    };
  } catch (e) {
    console.warn("Embeddings disabled: @xenova/transformers not installed or failed to load.");
    return null;
  }
}

async function embedChunks(embedder, chunks) {
  if (!embedder) return chunks.map(() => null);
  const out = [];
  for (const c of chunks) {
    try {
      const v = await embedder(c);
      out.push(v);
    } catch {
      out.push(null);
    }
  }
  return out;
}

function storeChunks(db, fileId, chunks, notionPageId, url, embeddings) {
  if (!db) return;
  const stmt = db.prepare(
    "INSERT INTO chunks (file_id, chunk_index, text, embedding, notion_page_id, url) VALUES (?,?,?,?,?,?)"
  );
  for (let i = 0; i < chunks.length; i++) {
    const text = chunks[i];
    const emb = embeddings ? embeddings[i] : null;
    const embStr = emb ? JSON.stringify(emb) : null;
    stmt.run(fileId, i, text, embStr, notionPageId || null, url || null);
  }
  stmt.finalize();
}

async function main() {
  console.log("Listing Drive PDFs…");
  const files = await listDriveFiles(DRIVE_FOLDER_ID);
  const targets = MAX_FILES ? files.slice(0, MAX_FILES) : files;
  console.log(`Found ${files.length} PDFs; processing ${targets.length}`);

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "drive-ocr-"));
  const db = openVectorDb();
  if (db) await maybeMigrateDb(db);
  const embedder = await getEmbedderIfEnabled();

  // Load bibliography and build indices for matching
  let bibIdx = { byKey: new Map(), byTitle: new Map(), byDoi: new Map(), byUrl: new Map() };
  try {
    const bibRecords = parseBibliography(BIB_SOURCE);
    bibIdx = buildBibIndex(bibRecords);
    console.log(`Loaded bibliography records: ${bibRecords.length}`);
  } catch (e) {
    console.warn(`Bibliography load failed or not provided (${BIB_SOURCE}): ${e?.message || e}`);
  }

  for (const f of targets) {
    try {
      const pdfPath = path.join(tmpDir, `${f.id}.pdf`);
      console.log("Downloading:", f.name, f.id);
      await downloadDriveFile(f.id, pdfPath);

      console.log("Extracting text:", f.name);
      const text = extractTextWithTesseract(pdfPath);
      if (!text) {
        console.warn("Empty text; skipping Notion append for:", f.name);
        continue;
      }
      const chunks = splitIntoChunks(text, CHUNK_SIZE);

  console.log("Upserting Notion page for:", f.name);
  const rec = matchBibForFile(f, bibIdx);
  const pageId = await ensurePageForFile(f, rec);

      console.log("Appending", chunks.length, "chunks to Notion…");
      await appendChildren(pageId, chunks);

      if (db) {
  const embeddings = await embedChunks(embedder, chunks);
  storeChunks(db, f.id, chunks, pageId, f.webViewLink || null, embeddings);
      }

      console.log("Done:", f.name);
    } catch (e) {
      console.error("Failed for file:", f?.name, e?.message || e);
    }
  }

  if (db) db.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
