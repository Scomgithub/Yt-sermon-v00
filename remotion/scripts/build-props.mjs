#!/usr/bin/env node
// Build Remotion props for a sermon clip.
//   node scripts/build-props.mjs <config.json>
// Config: see README. Writes clips/<name>.props.json and copies assets to public/clips/<name>/.
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import * as fontkit from 'fontkit';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const cfgPath = process.argv[2];
if (!cfgPath) { console.error('usage: node scripts/build-props.mjs <config.json>'); process.exit(1); }
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const FF = cfg.ffmpeg ?? 'ffmpeg';
const FP = cfg.ffprobe ?? 'ffprobe';
const W = 1080, H = 1920, FPS = 30;
const L = { // 04b layout figures (matched to the original CapCut build)
  layoutStart: 1.0, contentStart: 1.5, hold: 0.5, wipe: 1.0,
  capSize: 86, capLineH: 86, capMaxW: 960, capTop: 70 + 150, capDy: 0.12093023255813962 * 960 + 1.5, linesPerPage: 4, // capDy +1.5 px matches the CapCut export
  kernOverrides: {Al: -30},
  portraitScale: 1.1659289187643025, portraitDy: -0.032558139534883734 * 960,
  spectrumDy: -0.23299418604651168 * 960,
  titleBaseline: 138.5, nameBaseline: 1668, labelBaseline: 802.5, nameTracking: 7.6,
  ...(cfg.layout ?? {}),
};

const name = cfg.name;
const pub = path.join(ROOT, 'public', 'clips', name);
fs.mkdirSync(pub, {recursive: true});
const put = (src, dst) => { if (!src) return undefined; const out = path.join(pub, dst ?? path.basename(src)); fs.copyFileSync(src, out); return `clips/${name}/${path.basename(out)}`; };

// ---- audio
const audioOut = path.join(pub, 'audio.m4a');
execFileSync(FF, ['-y', '-v', 'error', '-i', cfg.audio, '-vn', '-c:a', 'aac', '-b:a', '256k', audioOut]);
execFileSync(FF, ['-y', '-v', 'error', '-i', cfg.audio, '-vn', '-ac', '1', '-ar', '22050', '-c:a', 'pcm_s16le', path.join(pub, 'audio.wav')]);
const dur = parseFloat(execFileSync(FP, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', audioOut]).toString());

// ---- fonts
const FONTS = path.join(ROOT, 'public', 'fonts');
const fk = (f) => fontkit.openSync(path.join(FONTS, f));
const momo = fk('MomoTrustDisplay-Regular.ttf'), arch = fk('Archivo-Medium.ttf');
const em = (f) => ({ascent: f.ascent / f.unitsPerEm, descent: -f.descent / f.unitsPerEm});

// ---- words
const normTok = (s) => s.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]/g, '');
let words;
if (cfg.timeline) {
  words = JSON.parse(fs.readFileSync(cfg.timeline, 'utf8')).map((w) => ({...w}));
} else {
  const wj = JSON.parse(fs.readFileSync(cfg.words, 'utf8'));
  const wt = (wj.words ?? wj.segments.flatMap((s) => s.words)).map((w) => ({n: normTok(w.word ?? w.text), start: w.start, end: w.end}));
  const md = fs.readFileSync(cfg.script, 'utf8').split('\n').filter((l) => l.trim() && !l.startsWith('#'));
  const st = [];
  md.forEach((para) => para.trim().split(/\s+/).forEach((t) => st.push({text: t, n: normTok(t)})));
  // DP alignment: 1:1, script word = 2 whisper words, 2 script words = 1 whisper word, skips.
  const sim = (a, b) => { if (a === b) return 0; const m = a.length, n = b.length; const d = Array.from({length: m + 1}, (_, i) => [i, ...Array(n).fill(0)]); for (let j = 1; j <= n; j++) d[0][j] = j; for (let i = 1; i <= m; i++) for (let j = 1; j <= n; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); return Math.min(1, d[m][n] / Math.max(m, n, 1)); };
  const S = st.length, T = wt.length, INF = 1e9;
  const C = Array.from({length: S + 1}, () => Array(T + 1).fill(INF)), B = Array.from({length: S + 1}, () => Array(T + 1).fill(null));
  C[0][0] = 0;
  for (let i = 0; i <= S; i++) for (let j = 0; j <= T; j++) {
    const c = C[i][j]; if (c >= INF) continue;
    const relax = (ni, nj, cost, op) => { if (ni <= S && nj <= T && c + cost < C[ni][nj]) { C[ni][nj] = c + cost; B[ni][nj] = [i, j, op]; } };
    if (i < S && j < T) relax(i + 1, j + 1, sim(st[i].n, wt[j].n) * 1.5, '11');
    if (i < S && j + 1 < T) relax(i + 1, j + 2, sim(st[i].n, wt[j].n + wt[j + 1].n) * 1.5 + 0.2, '12');
    if (i + 1 < S && j < T) relax(i + 2, j + 1, sim(st[i].n + st[i + 1].n, wt[j].n) * 1.5 + 0.2, '21');
    if (i < S) relax(i + 1, j, 1, 's');
    if (j < T) relax(i, j + 1, 1, 'w');
  }
  for (let i = S, j = T; i > 0 || j > 0;) {
    const [pi, pj, op] = B[i][j];
    if (op === '11') Object.assign(st[pi], {start: wt[pj].start, end: wt[pj].end});
    if (op === '12') Object.assign(st[pi], {start: wt[pj].start, end: wt[pj + 1].end});
    if (op === '21') { const a = st[pi], b = st[pi + 1], w = wt[pj], k = a.n.length / (a.n.length + b.n.length || 1), mid = w.start + (w.end - w.start) * k; Object.assign(a, {start: w.start, end: mid}); Object.assign(b, {start: mid, end: w.end}); }
    i = pi; j = pj;
  }
  // interpolate unmatched script words
  for (let i = 0; i < S; i++) if (st[i].start === undefined) {
    let k = i; while (k < S && st[k].start === undefined) k++;
    const a = i > 0 ? st[i - 1].end : 0, b = k < S ? st[k].start : dur, step = (b - a) / (k - i);
    for (let m = i; m < k; m++) Object.assign(st[m], {start: a + step * (m - i), end: a + step * (m - i + 1)});
    console.warn('unaligned:', st.slice(i, k).map((x) => x.text).join(' '));
  }
  // verse flags: a quoted span whose first word matches a configured verse; force a page break at its start and after it
  words = st.map((w) => ({text: w.text, start: +w.start.toFixed(3), end: +w.end.toFixed(3), verse: false}));
  for (const v of cfg.verses ?? []) {
    const i0 = words.findIndex((w) => w.text.startsWith('"') && normTok(w.text).startsWith(normTok(v.startsWith)));
    if (i0 < 0) throw new Error('verse not found: ' + v.startsWith);
    let i1 = i0; while (i1 < words.length && !/"[.,!?]*$/.test(words[i1].text)) i1++;
    for (let k = i0; k <= i1; k++) words[k].verse = true;
    words[i0].brk = true; if (words[i1 + 1]) words[i1 + 1].brk = true;
  }
}

// ---- caption layout (mirrors render_captions_momo.py: GPOS kerning + overrides, greedy wrap, 4 lines per page)
const scale = L.capSize / momo.unitsPerEm;
const measure = (t) => {
  const run = momo.layout(t, ['kern']);
  let w = run.positions.reduce((a, p) => a + p.xAdvance, 0);
  for (let i = 1; i < t.length; i++) w += L.kernOverrides[t[i - 1] + t[i]] ?? 0;
  return w * scale;
};
const space = momo.layout(' ').positions[0].xAdvance * scale;
const lineW = (line) => line.reduce((a, w) => a + measure(w.text), 0) + space * (line.length - 1);
const groups = [[]];
for (const w of words) { if (w.brk && groups.at(-1).length) groups.push([]); groups.at(-1).push(w); }
const blocks = [];
for (const g of groups) {
  const lines = []; let cur = [];
  for (const w of g) { if (cur.length && lineW([...cur, w]) > L.capMaxW) { lines.push(cur); cur = [w]; } else cur.push(w); }
  if (cur.length) lines.push(cur);
  for (let i = 0; i < lines.length; i += L.linesPerPage) blocks.push(lines.slice(i, i + L.linesPerPage));
}
const asc = Math.ceil(momo.ascent * scale); // PIL getmetrics rounds the ascent up
const baseline0 = L.capTop + asc + L.capDy;
const show = [0];
for (let i = 1; i < blocks.length; i++) show.push(Math.max(blocks[i - 1].at(-1).at(-1).end, show[i - 1]));
const pages = blocks.map((b, i) => ({
  show: show[i], hide: i + 1 < blocks.length ? show[i + 1] : dur + 10,
  lines: b.map((line, li) => {
    let x = (W - lineW(line)) / 2;
    return {baseline: baseline0 + li * L.capLineH, words: line.map((w) => { const o = {text: w.text, start: w.start, end: w.end, x, verse: !!w.verse}; x += measure(w.text) + space; return o; })};
  }),
}));

// verse ranges: from the page where the verse starts to the first page after it
const verses = (cfg.verses ?? []).map((v) => {
  const vw = words.filter((w) => w.verse);
  const pi0 = pages.findIndex((p) => p.lines.some((l) => l.words.some((w) => w.verse)));
  let pi1 = pi0; while (pi1 < pages.length && pages[pi1].lines.some((l) => l.words.some((w) => w.verse))) pi1++;
  return {start: pages[pi0].show, end: pi1 < pages.length ? pages[pi1].show : vw.at(-1).end, ref: v.ref};
});

const a = em(arch), sb = em(fk('Archivo-SemiBold.ttf'));
const props = {
  width: W, height: H, fps: FPS,
  durationInFrames: Math.round((L.contentStart + dur) * FPS),
  contentStart: L.contentStart, layoutStart: L.layoutStart,
  fonts: [
    {family: 'MomoTrustDisplay', src: 'fonts/MomoTrustDisplay-Regular.ttf'},
    {family: 'Archivo-Medium', src: 'fonts/Archivo-Medium.ttf'},
    {family: 'Archivo-SemiBold', src: 'fonts/Archivo-SemiBold.ttf'},
  ],
  audio: `clips/${name}/audio.m4a`, audioWav: `clips/${name}/audio.wav`,
  background: 'layout/bg.png', blueShape: 'layout/blue.png', redCircle: 'layout/red_circle.png',
  portrait: {src: put(cfg.portrait, 'portrait.png'), scale: L.portraitScale, dy: L.portraitDy},
  spectrum: {video: put(cfg.spectrumVideo, 'spectrum.mov'), dy: L.spectrumDy,
    xs: [...Array(10).keys()].map((i) => 33 + i * 34).concat([...Array(10).keys()].map((i) => 729 + i * 34)),
    barWidth: 16, baselineY: 1302 + L.spectrumDy, halfMin: 12, halfClip: 64, colors: ['#E8242B', '#1F56D6', '#F4C40E']},
  title: {text: cfg.title, font: 'Archivo-Medium', size: 34, tracking: 6, kerning: 'none', color: '#000000', baseline: L.titleBaseline, ...a},
  speakerName: {text: cfg.speakerName, font: 'Archivo-SemiBold', size: 30, tracking: L.nameTracking, kerning: 'none', color: '#FFFFFF', baseline: L.nameBaseline, ...sb},
  captions: {font: 'MomoTrustDisplay', size: L.capSize, ...em(momo), black: '#000000', red: '#E8242B', kernOverrides: L.kernOverrides, pages},
  verses,
  verseLabel: {font: 'Archivo-Medium', size: 34, tracking: 0, kerning: 'normal', color: '#000000', baseline: L.labelBaseline, ...a},
  intro: {cover: put(cfg.cover, 'cover.png'), coverColor: cfg.coverColor ?? '#E8242B', hold: L.hold, wipe: L.wipe},
  soundtrack: cfg.soundtrack ? {src: put(cfg.soundtrack.path, 'soundtrack' + path.extname(cfg.soundtrack.path)), gainDb: cfg.soundtrack.gainDb ?? -18, fadeIn: cfg.soundtrack.fadeIn ?? 1, fadeOut: cfg.soundtrack.fadeOut ?? 2} : null,
};
const out = path.join(ROOT, 'clips', `${name}.props.json`);
fs.writeFileSync(out, JSON.stringify(props, null, 1));
fs.writeFileSync(path.join(ROOT, 'clips', `${name}.words.json`), JSON.stringify(words, null, 0));
console.log(`props ${out}\nwords ${words.length} pages ${pages.length} verses ${JSON.stringify(verses)} duration ${dur.toFixed(3)}s frames ${props.durationInFrames}`);
