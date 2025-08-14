// OCR a single paper's PDF and upload text chunks to its Notion page
// Env:
// - NOTION_TOKEN (required)
// - NOTION_DB_ID (required)
// - BIB_KEY (required unless PAGE_ID is provided)
// - PAGE_ID (optional alternative to BIB_KEY)
// - GOOGLE_API_KEY (optional, required to download from Drive webViewLink)
// - DRIVE_FOLDER_ID (optional, for fallback matching)
// - CHUNK_SIZE (optional, default 1500)
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
const BIB_KEY = process.env.BIB_KEY || '';
const PAGE_ID = process.env.PAGE_ID || '';
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || '';
const DRIVE_FOLDER_ID = process.env.DRIVE_FOLDER_ID || '';
const CHUNK_SIZE = Number(process.env.CHUNK_SIZE || '1500');

const notion = new NotionClient({ auth: NOTION_TOKEN });

function hasCommand(cmd) {
  const p = spawnSync('bash', ['-lc', `command -v ${cmd} >/dev/null 2>&1 && echo yes || echo no`]);
  return String(p.stdout || '').toString().trim() === 'yes';
}

function findTitlePropName(dbProps) {
  for (const [name, def] of Object.entries(dbProps)) if (def?.type === 'title') return name;
  return null;
}
function hasProp(dbProps, name, type) { const p = dbProps[name]; return p && (!type || p.type === type); }
function rich(text) { return [{ type: 'text', text: { content: text ?? '' } }]; }

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
  // direct URL fetch
  const res = await fetch(url);
  if (!res.ok) throw new Error(`PDF download failed: ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outPath, buf);
  return outPath;
}

function ocrPdfToText(pdfPath) {
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
  if (conv.status !== 0) throw new Error(`pdftoppm failed: ${conv.status} ${conv.stderr || conv.stdout || ''}`);

  const dir = path.dirname(base);
  const bn = path.basename(base);
  const imgs = fs.readdirSync(dir).filter(f => f.startsWith(bn + '-') && f.endsWith('.png')).sort((a,b) => {
    const ai = Number(a.replace(/^.*-(\d+)\.png$/, '$1'));
    const bi = Number(b.replace(/^.*-(\d+)\.png$/, '$1'));
    return ai - bi;
  });

  let full = '';
  for (const img of imgs) {
    const imgPath = path.join(dir, img);
    const args = [imgPath, 'stdout', '--psm', tessPsm, '--oem', tessOem, '-l', tessLang, ...tessExtra];
    const ocr = spawnSync('tesseract', args, { encoding: 'utf8' });
    if (ocr.status === 0) full += (ocr.stdout || '') + '\n\n';
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
  const children = chunks.map(c => ({ type: 'paragraph', paragraph: { rich_text: rich(c) } }));
  // Wrap into a single toggle
  const parent = {
    type: 'toggle',
    toggle: {
      rich_text: rich('OCR Text'),
      children: [],
    },
  };

  // Append in batches under the toggle
  // First create the toggle
  const res = await notion.blocks.children.append({ block_id: pageId, children: [parent] });
  const toggleId = res.results?.[0]?.id;
  if (!toggleId) throw new Error('Failed to create OCR toggle block');

  for (let i = 0; i < children.length; i += 80) {
    const batch = children.slice(i, i + 80);
    await notion.blocks.children.append({ block_id: toggleId, children: batch });
  }
}

async function resolvePdfUrlForPage(page, dbProps) {
  // Prefer File Path url, then PDF files external url
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

async function main() {
  if (!BIB_KEY && !PAGE_ID) {
    console.error('Provide BIB_KEY or PAGE_ID');
    process.exit(1);
  }
  const dbProps = await getDbProps();
  const titleProp = findTitlePropName(dbProps) || 'Title';

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

  const title = getPropText(page, titleProp, 'title');
  console.log(`Target page: ${title} (${page.id})`);

  let pdfUrl = await resolvePdfUrlForPage(page, dbProps);
  if (!pdfUrl) {
    console.error('No PDF URL found on page (File Path or PDF external)');
    process.exit(1);
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ocr-one-'));
  const pdfPath = path.join(tmpDir, 'doc.pdf');
  await downloadPdfFromUrl(pdfUrl, pdfPath);

  const text = ocrPdfToText(pdfPath);
  if (!text) {
    console.error('OCR produced empty text');
    process.exit(1);
  }

  await clearExistingOcr(page.id);
  await appendOcrBlocks(page.id, text);
  console.log('OCR text uploaded successfully.');
}

main().catch(e => { console.error(e); process.exit(1); });
