// Attach PDFs from Google Drive to existing Notion pages, in a separate fast workflow
// Env:
// - NOTION_TOKEN (required)
// - NOTION_DB_ID (required)
// - GOOGLE_API_KEY (required)
// - DRIVE_FOLDER_ID (required)
// - MATCH_WINDOW (optional) limit to N recent pages by last edited time to reduce work

import path from "path";
import { fileURLToPath } from "url";
import fetch from "node-fetch";
import { Client as NotionClient } from "@notionhq/client";

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
const GOOGLE_API_KEY = env("GOOGLE_API_KEY");
const DRIVE_FOLDER_ID = env("DRIVE_FOLDER_ID");
const MATCH_WINDOW = Number(process.env.MATCH_WINDOW || "200");

const notion = new NotionClient({ auth: NOTION_TOKEN });

function normalize(s) { return String(s || '').toLowerCase(); }
function slugTitle(s) { return normalize(s).replace(/[^a-z0-9]+/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, ""); }
function compact(s) { return normalize(s).replace(/\W+/g, ""); }

async function listDrivePdfs(folderId) {
  const url = new URL("https://www.googleapis.com/drive/v3/files");
  url.searchParams.set("q", `'${folderId}' in parents and mimeType='application/pdf' and trashed=false`);
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

function buildNameCandidates(title, authorsText, year) {
  const last = normalize((authorsText || '').split(';')[0] || '').split(/\s+/).slice(-1)[0] || '';
  const t = slugTitle(title || '');
  const y = year ? String(year) : '';
  return [
    `${last}${y}-${t}`,
    `${last}_${y}-${t}`,
    `${last}${y}_${t}`,
    `${last}-${y}-${t}`,
    `${last}${y}${t}`,
  ].filter(Boolean);
}

function matchPdf(title, authorsText, year, files) {
  if (!files?.length) return null;
  const candidates = buildNameCandidates(title, authorsText, year);
  const nameMap = new Map();
  for (const f of files) nameMap.set(normalize(f.name.replace(/\.pdf$/i, "")), f);
  for (const c of candidates) { if (nameMap.has(c)) return nameMap.get(c); }
  const byCompact = new Map();
  for (const f of files) byCompact.set(compact(f.name), f);
  for (const c of candidates) { const k = compact(c); if (byCompact.has(k)) return byCompact.get(k); }
  const titleSlug = slugTitle(title || "");
  let best = null; let bestLen = 0;
  for (const f of files) {
    const base = slugTitle(f.name.replace(/\.pdf$/i, ""));
    if (base.includes(titleSlug) && titleSlug.length > bestLen) { best = f; bestLen = titleSlug.length; }
  }
  return best;
}

async function getDbProperties() {
  const db = await notion.databases.retrieve({ database_id: NOTION_DB_ID });
  return db.properties || {};
}

function findTitlePropName(dbProps) {
  for (const [name, def] of Object.entries(dbProps)) if (def?.type === 'title') return name; return null;
}

function hasProp(dbProps, name, type) { const p = dbProps[name]; return p && (!type || p.type === type); }
function rich(text) { return [{ type: 'text', text: { content: text ?? '' } }]; }

async function queryRecentPages(limit) {
  // Query pages sorted by last edited time desc to cap work per run
  const results = [];
  let cursor = undefined;
  while (results.length < limit) {
    const r = await notion.databases.query({
      database_id: NOTION_DB_ID,
      sorts: [{ timestamp: 'last_edited_time', direction: 'descending' }],
      page_size: Math.min(100, limit - results.length),
      start_cursor: cursor,
    });
    results.push(...r.results);
    if (!r.has_more) break;
    cursor = r.next_cursor;
  }
  return results;
}

function getTextProp(page, name, type) {
  const p = page.properties?.[name];
  if (!p) return '';
  if (type === 'title') return (p.title?.[0]?.plain_text) || '';
  if (type === 'rich_text') return (p.rich_text?.[0]?.plain_text) || '';
  if (type === 'url') return p.url || '';
  if (type === 'number') return p.number || '';
  return '';
}

async function attachPdf(pageId, props) {
  await notion.pages.update({ page_id: pageId, properties: props });
}

async function main() {
  const dbProps = await getDbProperties();
  const titleName = findTitlePropName(dbProps) || 'Title';

  const pages = await queryRecentPages(MATCH_WINDOW);
  console.log(`Scanning ${pages.length} recent Notion pages for PDF attachment`);

  const files = await listDrivePdfs(DRIVE_FOLDER_ID);
  console.log(`Drive PDFs available: ${files.length}`);

  let updated = 0;
  for (const page of pages) {
    const title = getTextProp(page, titleName, 'title');
    const authors = hasProp(dbProps, 'Authors', 'rich_text')
      ? getTextProp(page, 'Authors', 'rich_text')
      : hasProp(dbProps, 'Author', 'rich_text')
      ? getTextProp(page, 'Author', 'rich_text')
      : '';
    const yearVal = hasProp(dbProps, 'Year', 'number') ? page.properties['Year']?.number : undefined;

    const pdf = matchPdf(title, authors, yearVal, files);
    const pdfUrl = pdf?.webViewLink || null;
    if (!pdfUrl) continue;

    const props = {};
    if (hasProp(dbProps, 'PDF', 'files')) {
      props['PDF'] = { files: [{ name: 'PDF', type: 'external', external: { url: pdfUrl } }] };
    }
    if (dbProps['File Path']) {
      const t = dbProps['File Path'].type;
      if (t === 'url') props['File Path'] = { url: pdfUrl };
      else if (t === 'rich_text') props['File Path'] = { rich_text: rich(pdfUrl) };
    }

    if (Object.keys(props).length) {
      try {
        await attachPdf(page.id, props);
        updated++;
      } catch (e) {
        console.warn('Failed to attach PDF for page', page.id, e?.message || e);
      }
    }
  }
  console.log(`PDF attach complete. Updated: ${updated}`);
}

const isMain = (() => {
  try { return (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))); } catch { return false; }
})();

if (isMain) {
  main().catch((e) => { console.error(e); process.exit(1); });
}
