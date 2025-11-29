// Notion PDF OCR uploader
// -----------------------
// This script provides two modes:
//   1) Single page mode: identify one Notion page by PAGE_ID or BIB_KEY
//      and OCR its associated PDF into a toggle block.
//   2) Recent pages mode: when OCR_RECENT_LIMIT is set, scan the most
//      recently edited pages in the database and OCR each one that has
//      an associated PDF URL.
//
// Env:
// - NOTION_TOKEN (required)
// - NOTION_DB_ID (required)
// - PAGE_ID (optional, single-page mode)
// - BIB_KEY (optional, single-page mode fallback)
// - OCR_RECENT_LIMIT (optional, switch to batch mode when set)
// - GOOGLE_API_KEY (optional, for Google Drive downloads)
// - DRIVE_FOLDER_ID (optional, for Drive name-based matching)
// - CHUNK_SIZE (optional, default 1500)
// - MIN_TEXT_LENGTH (optional, default 50)
// - TESS_LANG (default 'eng') e.g., 'eng+jpn'
// - TESS_PSM (default '1'), TESS_OEM (default '1'), TESS_DPI (default '300'), TESS_EXTRA_ARGS

import fs from 'fs';
import os from 'os';
import path from 'path';
import { spawnSync } from 'child_process';
import fetch from 'node-fetch';
import { Client as NotionClient } from '@notionhq/client';

function env(name, optional = false) {
  const v = process.env[name];
  if (!optional && !v) {
    console.error(`Missing env ${name}`);
    process.exit(1);
  }
  return v;
}

const NOTION_TOKEN = env('NOTION_TOKEN');
const NOTION_DB_ID = env('NOTION_DB_ID');
const PAGE_ID = process.env.PAGE_ID || '';
const BIB_KEY = process.env.BIB_KEY || '';
const OCR_RECENT_LIMIT = Number(process.env.OCR_RECENT_LIMIT || '0');
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || '';
const DRIVE_FOLDER_ID = process.env.DRIVE_FOLDER_ID || '';
const CHUNK_SIZE = Number(process.env.CHUNK_SIZE || '1500');
const MIN_TEXT_LENGTH = Number(process.env.MIN_TEXT_LENGTH || '50');

const notion = new NotionClient({ auth: NOTION_TOKEN });

function hasCommand(cmd) {
  const p = spawnSync('bash', ['-lc', `command -v ${cmd} >/dev/null 2>&1 && echo yes || echo no`]);
  return String(p.stdout || '').toString().trim() === 'yes';
}

function findTitlePropName(dbProps) {
  for (const [name, def] of Object.entries(dbProps)) {
    if (def?.type === 'title') return name;
  }
  return null;
}

function hasProp(dbProps, name, type) {
  const p = dbProps[name];
  return p && (!type || p.type === type);
}

function rich(text) {
  return [{ type: 'text', text: { content: text ?? '' } }];
}

function richChunks(text, max = 2000) {
  const s = String(text || '');
  if (!s) return [{ type: 'text', text: { content: '' } }];
  const out = [];
  for (let i = 0; i < s.length; i += max) {
    out.push({ type: 'text', text: { content: s.slice(i, i + max) } });
  }
  return out;
}

async function getDbProps() {
  const db = await notion.databases.retrieve({ database_id: NOTION_DB_ID });
  return db.properties || {};
}

async function findPageByBibKey(dbProps, bibKey) {
  if (!bibKey) return null;
  if (!hasProp(dbProps, 'Bib Key', 'rich_text')) return null;
  const r = await notion.databases.query({
    database_id: NOTION_DB_ID,
    filter: { property: 'Bib Key', rich_text: { equals: bibKey } },
    page_size: 1,
  });
  return r.results?.[0] || null;
}

function getPropText(page, name, type) {
  const p = page.properties?.[name];
  if (!p) return '';
  if (type === 'title') return p.title?.[0]?.plain_text || '';
  if (type === 'rich_text') return p.rich_text?.[0]?.plain_text || '';
  if (type === 'url') return p.url || '';
  if (type === 'number') return p.number || '';
  return '';
}

function extractDriveIdFromUrl(url) {
  if (!url) return '';
  const m1 = url.match(/\/file\/d\/([^/]+)\//);
  if (m1) return m1[1];
  const m2 = url.match(/[?&]id=([^&]+)/);
  if (m2) return m2[1];
  return '';
}

async function downloadPdfFromUrl(url, outPath) {
  if (/^https?:\/\/drive\.google\.com\//.test(url)) {
    const id = extractDriveIdFromUrl(url);
    if (!id) throw new Error('Cannot extract Drive file id from URL');
    if (!GOOGLE_API_KEY) throw new Error('GOOGLE_API_KEY required to download Drive file');
    const dl = new URL(`https://www.googleapis.com/drive/v3/files/${id}`);
    dl.searchParams.set('alt', 'media');
    dl.searchParams.set('key', GOOGLE_API_KEY);
    const res = await fetch(dl.toString());
    if (!res.ok) throw new Error(`Drive download failed: ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    fs.writeFileSync(outPath, buf);
    return outPath;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`PDF download failed: ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outPath, buf);
  return outPath;
}

function ocrPdfToText(pdfPath) {
  if (hasCommand('pdftotext')) {
    try {
      const tmpTxt = pdfPath.replace(/\.pdf$/i, '.txt');
      const ext = spawnSync('pdftotext', ['-layout', '-nopgbrk', pdfPath, tmpTxt], { encoding: 'utf8' });
      if (ext.status === 0 && fs.existsSync(tmpTxt)) {
        const raw = fs.readFileSync(tmpTxt, 'utf8').trim();
        if (raw && raw.replace(/\s+/g, ' ').length > MIN_TEXT_LENGTH) {
          return raw;
        }
      }
    } catch {
      // fall through to OCR
    }
  }

  if (!hasCommand('pdftoppm') || !hasCommand('tesseract')) {
    throw new Error("Missing OCR deps. Install 'poppler-utils' and 'tesseract-ocr'.");
  }
  const tessLang = process.env.TESS_LANG || 'eng';
  const tessPsm = process.env.TESS_PSM || '1';
  const tessOem = process.env.TESS_OEM || '1';
  const tessDpi = process.env.TESS_DPI || '300';
  const tessExtra = (process.env.TESS_EXTRA_ARGS || '').split(/\s+/).filter(Boolean);

  const base = pdfPath.replace(/\.pdf$/i, '');
  const conv = spawnSync('pdftoppm', ['-png', '-r', tessDpi, pdfPath, base], { encoding: 'utf8' });
  if (conv.status !== 0) {
    throw new Error(`pdftoppm failed: ${conv.status} ${conv.stderr || conv.stdout || ''}`);
  }

  const dir = path.dirname(base);
  const bn = path.basename(base);
  const imgs = fs
    .readdirSync(dir)
    .filter((f) => f.startsWith(bn + '-') && f.endsWith('.png'))
    .sort((a, b) => {
      const ai = Number(a.replace(/^.*-(\d+)\.png$/, '$1'));
      const bi = Number(b.replace(/^.*-(\d+)\.png$/, '$1'));
      return ai - bi;
    });

  let full = '';
  for (const img of imgs) {
    const imgPath = path.join(dir, img);
    const args = [imgPath, 'stdout', '--psm', tessPsm, '--oem', tessOem, '-l', tessLang, ...tessExtra];
    const ocr = spawnSync('tesseract', args, { encoding: 'utf8' });
    if (ocr.status === 0) {
      full += (ocr.stdout || '') + '\n\n';
    }
  }
  return full.trim();
}

function chunkText(text, size) {
  const chunks = [];
  let i = 0;
  while (i < text.length) {
    chunks.push(text.slice(i, i + size));
    i += size;
  }
  return chunks;
}

async function listTopLevelBlocks(pageId) {
  const blocks = [];
  let cursor = undefined;
  while (true) {
    const r = await notion.blocks.children.list({ block_id: pageId, page_size: 100, start_cursor: cursor });
    blocks.push(...(r.results || []));
    if (!r.has_more) break;
    cursor = r.next_cursor;
  }
  return blocks;
}

async function archiveBlock(blockId) {
  await notion.blocks.update({ block_id: blockId, archived: true });
}

function isOcrToggle(block) {
  if (block.type !== 'toggle') return false;
  const txt = block.toggle?.rich_text?.[0]?.plain_text || '';
  return /^OCR\s*Text$/i.test(txt) || /^OCR$/i.test(txt);
}

async function clearExistingOcr(pageId) {
  try {
    const blocks = await listTopLevelBlocks(pageId);
    const targets = blocks.filter(isOcrToggle);
    for (const b of targets) {
      await archiveBlock(b.id);
    }
  } catch (e) {
    console.warn('Failed to clear existing OCR blocks:', e?.message || e);
  }
}

async function appendOcrBlocks(pageId, text) {
  const chunks = chunkText(text, CHUNK_SIZE);
  const children = chunks.map((c) => ({ type: 'paragraph', paragraph: { rich_text: richChunks(c, 2000) } }));

  const parent = {
    type: 'toggle',
    toggle: {
      rich_text: rich('OCR Text'),
      children: [],
    },
  };

  const res = await notion.blocks.children.append({ block_id: pageId, children: [parent] });
  const toggleId = res.results?.[0]?.id;
  if (!toggleId) throw new Error('Failed to create OCR toggle block');

  for (let i = 0; i < children.length; i += 80) {
    const batch = children.slice(i, i + 80);
    await notion.blocks.children.append({ block_id: toggleId, children: batch });
  }
}

async function resolvePdfUrlForPage(page, dbProps) {
  if (dbProps['File Path']) {
    const t = dbProps['File Path'].type;
    if (t === 'url') {
      const url = page.properties?.['File Path']?.url;
      if (url) return url;
    } else if (t === 'rich_text') {
      const txt = page.properties?.['File Path']?.rich_text?.[0]?.plain_text;
      if (txt) return txt;
    }
  }
  if (hasProp(dbProps, 'PDF', 'files')) {
    const files = page.properties?.['PDF']?.files || [];
    for (const f of files) {
      if (f.type === 'external' && f.external?.url) return f.external.url;
    }
  }
  return '';
}

// ---- Optional Drive matching fallback ----
function normalize(s) {
  return String(s || '').toLowerCase();
}

function slugTitle(s) {
  return normalize(s)
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function compact(s) {
  return normalize(s).replace(/\W+/g, '');
}

function firstAuthor(authorsText) {
  return (authorsText || '').split(';')[0] || (authorsText || '').split(',')[0] || '';
}

function buildNameCandidates(title, authorsText, year) {
  const last = normalize(firstAuthor(authorsText)).split(/\s+/).slice(-1)[0] || '';
  const t = slugTitle(title || '');
  const y = year ? String(year) : '';
  return [`${last}${y}-${t}`, `${last}_${y}-${t}`, `${last}${y}_${t}`, `${last}-${y}-${t}`, `${last}${y}${t}`].filter(Boolean);
}

async function listDrivePdfs(folderId) {
  if (!folderId || !GOOGLE_API_KEY) return [];
  const url = new URL('https://www.googleapis.com/drive/v3/files');
  url.searchParams.set('q', `'${folderId}' in parents and mimeType='application/pdf' and trashed=false`);
  url.searchParams.set('fields', 'files(id,name,webViewLink,modifiedTime)');
  url.searchParams.set('key', GOOGLE_API_KEY);
  const res = await fetch(url.toString());
  if (!res.ok) return [];
  const data = await res.json();
  return data.files || [];
}

function matchPdf(title, authorsText, year, files) {
  if (!files?.length) return null;
  const candidates = buildNameCandidates(title, authorsText, year);
  const nameMap = new Map();
  for (const f of files) nameMap.set(normalize(f.name.replace(/\.pdf$/i, '')), f);
  for (const c of candidates) if (nameMap.has(c)) return nameMap.get(c);
  const byCompact = new Map();
  for (const f of files) byCompact.set(compact(f.name), f);
  for (const c of candidates) {
    const k = compact(c);
    if (byCompact.has(k)) return byCompact.get(k);
  }
  const titleSlug = slugTitle(title || '');
  let best = null;
  let bestLen = 0;
  for (const f of files) {
    const base = slugTitle(f.name.replace(/\.pdf$/i, ''));
    if (base.includes(titleSlug) && titleSlug.length > bestLen) {
      best = f;
      bestLen = titleSlug.length;
    }
  }
  return best;
}

async function resolvePdfUrlWithFallback(page, dbProps) {
  let url = await resolvePdfUrlForPage(page, dbProps);
  if (url) return url;
  if (!DRIVE_FOLDER_ID || !GOOGLE_API_KEY) return '';

  const titleProp = findTitlePropName(dbProps) || 'Title';
  const titleText = getPropText(page, titleProp, 'title');
  const authorsText = hasProp(dbProps, 'Authors', 'rich_text')
    ? getPropText(page, 'Authors', 'rich_text')
    : hasProp(dbProps, 'Author', 'rich_text')
    ? getPropText(page, 'Author', 'rich_text')
    : '';
  const yearVal = hasProp(dbProps, 'Year', 'number') ? page.properties['Year']?.number : undefined;
  const files = await listDrivePdfs(DRIVE_FOLDER_ID);
  const m = matchPdf(titleText, authorsText, yearVal, files);
  return m?.webViewLink || '';
}

async function ocrPage(page, dbProps) {
  const titleProp = findTitlePropName(dbProps) || 'Title';
  const title = getPropText(page, titleProp, 'title');
  console.log(`Processing page: ${title || '(untitled)'} (${page.id})`);

  const pdfUrl = await resolvePdfUrlWithFallback(page, dbProps);
  if (!pdfUrl) {
    console.warn('  Skipping: no PDF URL found');
    return false;
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ocr-'));
  const pdfPath = path.join(tmpDir, 'doc.pdf');
  await downloadPdfFromUrl(pdfUrl, pdfPath);

  const text = ocrPdfToText(pdfPath);
  if (!text) {
    console.warn('  Skipping: OCR produced empty text');
    return false;
  }

  await clearExistingOcr(page.id);
  await appendOcrBlocks(page.id, text);
  console.log('  OCR text uploaded.');
  return true;
}

async function queryRecentPages(limit) {
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

async function main() {
  const dbProps = await getDbProps();

  if (OCR_RECENT_LIMIT > 0) {
    const pages = await queryRecentPages(OCR_RECENT_LIMIT);
    console.log(`Running batch OCR on ${pages.length} recent pages (limit=${OCR_RECENT_LIMIT})`);
    let ok = 0;
    for (const page of pages) {
      try {
        const done = await ocrPage(page, dbProps);
        if (done) ok += 1;
      } catch (e) {
        console.warn('Error OCR-ing page', page.id, e?.message || e);
      }
    }
    console.log(`Batch OCR complete. Updated pages: ${ok}`);
    return;
  }

  if (!PAGE_ID && !BIB_KEY) {
    console.error('Provide PAGE_ID or BIB_KEY for single-page OCR, or set OCR_RECENT_LIMIT for batch mode.');
    process.exit(1);
  }

  let page = null;
  if (PAGE_ID) {
    page = await notion.pages.retrieve({ page_id: PAGE_ID });
  } else {
    page = await findPageByBibKey(dbProps, BIB_KEY);
  }
  if (!page) {
    console.error('Target Notion page not found');
    process.exit(1);
  }

  const ok = await ocrPage(page, dbProps);
  if (!ok) {
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
