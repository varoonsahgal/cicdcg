// Builds docs/labN.html from labs/*.md using the shared site shell.
// Usage:  cd tools && npm install && npm run build
import { marked } from 'marked';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const LABS = path.join(ROOT, 'labs');
const DOCS = path.join(ROOT, 'docs');
const DL = path.join(DOCS, 'downloads');
// Where the repository lives on GitHub (used for links to folders that are not
// part of the published site). Override:  REPO_URL=https://github.com/you/repo npm run build
const REPO_URL = process.env.REPO_URL || 'https://github.com/varoonsahgal/cicdcg';

// page id → { md file, nav title, short, hue, number }
const PAGES = [
  { id: 'lab1', md: 'lab1-codebuild.md',               title: 'Lab 1 · CodeBuild',               short: 'Build it',    hue: 'hue-lab1', dot: '#38BDF8' },
  { id: 'lab2', md: 'lab2-codepipeline-codedeploy.md', title: 'Lab 2 · CodePipeline + CodeDeploy', short: 'Ship it', hue: 'hue-lab2', dot: '#22C55E' },
  { id: 'lab3', md: 'lab3-broken-pipeline.md',         title: 'Lab 3 · The broken pipeline',     short: 'Fix it',      hue: 'hue-lab3', dot: '#EF4444' },
  { id: 'lab4', md: 'lab4-ecs-ecr.md',                 title: 'Lab 4 · Containers on ECS',       short: 'Contain it',  hue: 'hue-lab4', dot: '#F59E0B' },
  { id: 'lab5', md: 'lab5-eks.md',                     title: 'Lab 5 · Kubernetes on EKS',       short: 'Orchestrate it', hue: 'hue-lab5', dot: '#A78BFA' },
  { id: 'instructor', md: 'instructor-guide.md',       title: 'Instructor guide',                short: '',            hue: 'hue-lab2', dot: '#64748B', hidden: true },
];

// Files students download. Copied into docs/downloads/ so GitHub Pages can serve them.
const DOWNLOADS = [
  'lab1-codebuild/MessageUtil.zip',
  'lab2-codepipeline-codedeploy/SampleApp.zip',
  'lab4-ecs/app.zip',
  'lab5-eks/lab5-manifests.zip',
];

fs.mkdirSync(DL, { recursive: true });
for (const rel of DOWNLOADS) {
  const src = path.join(ROOT, rel);
  if (fs.existsSync(src)) fs.copyFileSync(src, path.join(DL, path.basename(rel)));
}

const mdToPage = Object.fromEntries(PAGES.map(p => [p.md, p.id + '.html']));

function nav(current) {
  return PAGES.filter(p => !p.hidden).map(p =>
    `<a href="${p.id}.html" data-lab="${p.id}" style="--d:${p.dot}"${current === p.id ? ' aria-current="page"' : ''}><span class="dot"></span>${p.title.split(' · ')[0]}<span class="lbl-long"> · ${p.short}</span><span class="done">★</span></a>`
  ).join('\n      ');
}

const shell = ({ id, title, hue, body, kicker, lede, meta, prev, next }) => `<!doctype html>
<html lang="en" class="${hue}" data-page="${id}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} · Pipeline Academy</title>
<meta name="description" content="${lede.replace(/"/g, '&quot;')}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#0B1220">
<script>try{var t=localStorage.getItem('pipeline-academy:theme');if(t)document.documentElement.setAttribute('data-theme',JSON.parse(t))}catch(e){}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="assets/site.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230B1220'/%3E%3Ccircle cx='8' cy='16' r='4' fill='%2322C55E'/%3E%3Ccircle cx='16' cy='16' r='4' fill='%2338BDF8'/%3E%3Ccircle cx='24' cy='16' r='4' fill='%23F59E0B'/%3E%3C/svg%3E">
</head>
<body data-page="${id}">
<a class="skip" href="#main">Skip to content</a>
<div id="readbar" aria-hidden="true"></div>
<header class="topbar"><div class="topbar-in">
  <a class="brand" href="index.html"><svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#0B1220"/><circle cx="8" cy="16" r="4" fill="#22C55E"/><circle cx="16" cy="16" r="4" fill="#38BDF8"/><circle cx="24" cy="16" r="4" fill="#F59E0B"/><path d="M12 16h0M20 16h0" stroke="#fff"/></svg>Pipeline Academy <span>· AWS CI/CD labs</span></a>
  <nav class="nav" aria-label="Labs">
      <a href="index.html">Start here</a>
      ${nav(id)}
  </nav>
  <div class="tools">
    <button class="iconbtn" id="theme" type="button" aria-label="Switch theme"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9z"/></svg></button>
    <button class="iconbtn menu-btn" type="button" aria-label="Menu" aria-expanded="false"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
  </div>
</div></header>

<section class="mast"><canvas class="mast-fx" aria-hidden="true"></canvas><div class="mast-in">
  <div>
    <p class="eyebrow">${kicker}</p>
    <h1>${title}</h1>
    <p class="lede">${lede}</p>
    <div class="mast-meta">${meta}</div>
  </div>
</div></section>

<main id="main" class="labwrap">
${body}
<div class="pager">
  ${prev ? `<a href="${prev.id}.html"><small>Previous</small>← ${prev.title}</a>` : '<span></span>'}
  ${next ? `<a href="${next.id}.html" style="text-align:right"><small>Next</small>${next.title} →</a>` : '<span></span>'}
</div>
</main>
<footer><span>Pipeline Academy · hands-on AWS CI/CD labs</span><span>Built from <code>labs/*.md</code> · screenshots taken in a real account, then torn down.</span></footer>
<script src="assets/site.js"></script>
</body>
</html>`;

// ── Markdown pre/post processing ─────────────────────────────────────────────
function rewriteLinks(md) {
  return md
    .replace(/\(\.\.\/docs\/images\//g, '(images/')
    .replace(/\(\.\.\/docs\/index\.html\)/g, '(index.html)')
    .replace(/\(\.\.\/docs\/index\.html#([^)]*)\)/g, '(index.html#$1)')
    .replace(/\(([a-z0-9-]+\.md)\)/g, (m, f) => `(${mdToPage[f] || f})`)
    .replace(/\(\.\.\/([a-z0-9-]+\/[A-Za-z0-9-]+\.zip)\)/g, (m, f) => `(downloads/${path.basename(f)})`)
    .replace(/\(\.\.\/([a-z0-9-]+\/[^)]*)\)/g, (m, f) => `(${REPO_URL}/tree/main/${f})`);
}

// GitHub alerts  > [!NOTE] … → callouts; "> ✅ **Checkpoint**" → checkpoint
function alerts(html) {
  const kinds = { NOTE: ['note', '📝'], TIP: ['tip', '💡'], IMPORTANT: ['important', '❗'], WARNING: ['warning', '⚠️'], CAUTION: ['caution', '🛑'] };
  html = html.replace(/<blockquote>\s*<p>\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(?:<br>)?\s*/g, (m, k) => {
    const [cls, ico] = kinds[k];
    return `<div class="callout ${cls}"><div class="ico">${ico}</div><div><span class="box-lbl">${k.charAt(0) + k.slice(1).toLowerCase()}</span><p>`;
  });
  // close those callouts: the matching </blockquote> after our opener
  html = html.replace(/<div class="callout ([a-z]+)"><div class="ico">([^<]*)<\/div><div><span class="box-lbl">([^<]*)<\/span>([\s\S]*?)<\/blockquote>/g,
    (m, cls, ico, lbl, inner) => `<div class="callout ${cls}"><div class="ico">${ico}</div><div><span class="box-lbl">${lbl}</span>${inner}</div></div>`);
  html = html.replace(/<blockquote>\s*<p>✅ <strong>Checkpoint<\/strong>/g, '<blockquote class="checkpoint"><p>✅ <strong>Checkpoint</strong>');
  return html;
}

// <details> → styled reveals, classified by summary text
function reveals(html) {
  return html.replace(/<details>\s*<summary>([\s\S]*?)<\/summary>([\s\S]*?)<\/details>/g, (m, sum, body) => {
    const t = sum.replace(/<[^>]+>/g, '');
    const cls = /hint/i.test(t) ? 'hint' : /solution|answer key|facilitator/i.test(t) ? 'solution' : /^\s*\d+\./.test(t) ? 'quiz' : 'plain';
    return `<details class="reveal ${cls}"><summary>${sum}</summary><div class="body">${body}</div></details>`;
  });
}

function images(html) {
  return html
    .replace(/<img src="(images\/diagrams\/[^"]+)" alt="([^"]*)">/g, '<img class="diagram" src="$1" alt="$2" loading="lazy">')
    .replace(/<img src="(images\/[^"]+\.png)" alt="([^"]*)">/g, '<img class="shot" src="$1" alt="$2" loading="lazy" title="Click to zoom">');
}

function slug(s) { return s.toLowerCase().replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); }

function toc(html) {
  const items = [];
  html = html.replace(/<h2>([\s\S]*?)<\/h2>/g, (m, t) => { const id = slug(t); items.push({ id, t: t.replace(/<[^>]+>/g, '') }); return `<h2 id="${id}">${t}</h2>`; });
  const list = `<details class="toc" open><summary>On this page</summary><ol>${items.map(i => `<li><a href="#${i.id}">${i.t}</a></li>`).join('')}</ol></details>`;
  return { html, list };
}

function build(p, i) {
  const src = path.join(LABS, p.md);
  if (!fs.existsSync(src)) { console.log('skip (missing)', p.md); return; }
  let md = rewriteLinks(fs.readFileSync(src, 'utf8'));
  // Pull title, tagline and the "at a glance" table out of the markdown for the masthead.
  const titleM = md.match(/^# (.+)$/m); const title = titleM ? titleM[1].replace(/^Lab \d+ · /, '') : p.title;
  md = md.replace(/^# .+$\n/m, '');
  const tagM = md.match(/^> \*(.+)\*\s*$/m); const lede = tagM ? tagM[1] : '';
  if (tagM) md = md.replace(tagM[0] + '\n', '');
  // at-a-glance table → chips
  let meta = '';
  const tbl = md.match(/^\| \| \|\n\|---\|---\|\n((?:\|.*\|\n)+)/m);
  if (tbl) {
    const rows = tbl[1].trim().split('\n').map(r => r.split('|').slice(1, -1).map(c => c.trim()));
    meta = rows.filter(([k]) => !/Handout/.test(k)).map(([k, v]) => `<span class="chip"><b>${k.replace(/\*\*/g, '')}</b> ${marked.parseInline(v)}</span>`).join('');
    md = md.replace(tbl[0], '');
  }
  let html = marked.parse(md, { gfm: true, breaks: false });
  html = alerts(html); html = reveals(html); html = images(html);
  const t = toc(html); html = t.list + t.html;
  const vis = PAGES.filter(x => !x.hidden);
  const idx = vis.findIndex(x => x.id === p.id);
  const kicker = p.hidden ? 'For the instructor' : `Lab ${idx + 1} of ${vis.length} · ${p.short}`;
  const out = shell({ id: p.id, title, hue: p.hue, body: html, kicker, lede, meta, prev: idx > 0 ? vis[idx - 1] : null, next: idx >= 0 && idx < vis.length - 1 ? vis[idx + 1] : null });
  fs.writeFileSync(path.join(DOCS, p.id + '.html'), out);
  console.log('built', p.id + '.html', `(${Math.round(out.length / 1024)} KB)`);
}

PAGES.forEach(build);
