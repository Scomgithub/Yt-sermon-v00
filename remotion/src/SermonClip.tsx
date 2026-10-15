import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, continueRender, delayRender, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/fonts';
import {useAudioData, visualizeAudio} from '@remotion/media-utils';
import type {SermonProps, TextStyle} from './types';

const full: React.CSSProperties = {position: 'absolute', left: 0, top: 0, width: '100%', height: '100%'};

const useFonts = (fonts: SermonProps['fonts']) => {
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    Promise.all(fonts.map((f) => loadFont({family: f.family, url: staticFile(f.src)})))
      .then(() => continueRender(handle))
      .catch((e) => { console.error(e); continueRender(handle); });
  }, [fonts, handle]);
};

// PIL-style tracked text: letter-spacing after every glyph, minus the trailing one, centred on x.
const Line: React.FC<{s: TextStyle; text?: string; width: number}> = ({s, text, width}) => {
  const lh = (s.ascent + s.descent) * s.size;
  return (
    <div style={{position: 'absolute', left: 0, width, top: s.baseline - s.ascent * s.size, height: lh,
      display: 'flex', justifyContent: 'center', transform: s.x !== undefined ? `translateX(${s.x - width / 2}px)` : undefined}}>
      <span style={{fontFamily: s.font, fontSize: s.size, lineHeight: `${lh}px`, color: s.color, whiteSpace: 'pre',
        letterSpacing: s.tracking, marginRight: -s.tracking, fontKerning: s.kerning,
        fontFeatureSettings: s.kerning === 'none' ? '"kern" 0' : undefined}}>{text ?? s.text}</span>
    </div>
  );
};

// Word text with optional pair overrides (font units), e.g. {"Al": -30}.
const WordText: React.FC<{text: string; overrides: Record<string, number>; size: number}> = ({text, overrides, size}) => {
  const parts: React.ReactNode[] = [];
  let buf = '';
  for (let i = 0; i < text.length; i++) {
    const pair = text.slice(i - 1, i + 1);
    if (i > 0 && overrides[pair] !== undefined) {
      parts.push(buf);
      buf = '';
      parts.push(<span key={i} style={{marginLeft: (overrides[pair] * size) / 1000}}>{text[i]}</span>);
      continue;
    }
    buf += text[i];
  }
  parts.push(buf);
  return <>{parts}</>;
};

const Captions: React.FC<{p: SermonProps}> = ({p}) => {
  const frame = useCurrentFrame();
  const t = frame / p.fps;
  const c = p.captions;
  const page = c.pages.find((pg) => t >= pg.show && t < pg.hide);
  if (!page) return null;
  const lh = (c.ascent + c.descent) * c.size;
  return (
    <AbsoluteFill>
      {page.lines.flatMap((line, li) => line.words.map((w, wi) => {
        const spoken = t >= w.start && t < w.end;
        return (
          <div key={`${li}-${wi}`} style={{position: 'absolute', left: w.x, top: line.baseline - c.ascent * c.size,
            fontFamily: c.font, fontSize: c.size, lineHeight: `${lh}px`, height: lh, whiteSpace: 'pre',
            fontKerning: 'normal', color: spoken ? c.red : c.black}}>
            <WordText text={w.text} overrides={c.kernOverrides} size={c.size} />
          </div>
        );
      }))}
    </AbsoluteFill>
  );
};

const LiveSpectrum: React.FC<{p: SermonProps}> = ({p}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const data = useAudioData(staticFile(p.audioWav ?? p.audio));
  const s = p.spectrum;
  if (!data) return null;
  const n = s.xs.length;
  const vals = visualizeAudio({fps, frame, audioData: data, numberOfSamples: 64, optimizeFor: 'speed'});
  return (
    <AbsoluteFill>
      {s.xs.map((x, i) => {
        const band = i % (n / 2);
        const v = Math.min(1, Math.pow(vals[Math.min(vals.length - 1, 1 + band * 3)] * 4, 0.6));
        const half = Math.min(s.halfClip, Math.round(1.5 * (8 + Math.pow(v, 1.7) * 50)));
        return <div key={i} style={{position: 'absolute', left: x, width: s.barWidth, top: s.baselineY - half, height: half * 2, background: s.colors[i % s.colors.length]}} />;
      })}
    </AbsoluteFill>
  );
};

const Wipe: React.FC<{color: string; dur: number}> = ({color, dur}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const n = Math.round(dur * fps);
  const t = (frame + 0.5) / n;
  const ease = (u: number) => (u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2);
  const [x0, x1] = t < 0.5 ? [0, ease(t / 0.5) * width] : [ease((t - 0.5) / 0.5) * width, width];
  const a = Math.round(x0), b = Math.round(x1);
  return <div style={{position: 'absolute', top: 0, bottom: 0, left: a, width: Math.max(0, b - a), background: color}} />;
};

export const SermonClip: React.FC<SermonProps> = (p) => {
  useFonts(p.fonts);
  const {fps} = p;
  const f = (s: number) => Math.round(s * fps);
  const layoutFrom = f(p.layoutStart), contentFrom = f(p.contentStart);
  const end = p.durationInFrames;
  const img = (src: string, style?: React.CSSProperties) => <Img src={staticFile(src)} style={{...full, ...style}} />;
  const st = p.soundtrack;
  return (
    <AbsoluteFill style={{background: '#000'}}>
      {img(p.background)}
      <Sequence from={layoutFrom} durationInFrames={end - layoutFrom} layout="none">{img(p.blueShape)}</Sequence>
      <Sequence from={contentFrom} durationInFrames={end - contentFrom} layout="none">
        {p.spectrum.video
          ? <OffthreadVideo src={staticFile(p.spectrum.video)} muted transparent style={{...full, transform: `translateY(${p.spectrum.dy}px)`}} />
          : <LiveSpectrum p={p} />}
      </Sequence>
      <Sequence from={layoutFrom} durationInFrames={end - layoutFrom} layout="none">
        {img(p.redCircle)}
        {img(p.portrait.src, {transform: `translateY(${p.portrait.dy}px) scale(${p.portrait.scale})`, transformOrigin: '50% 50%'})}
        <Line s={p.title} width={p.width} />
      </Sequence>
      <Sequence from={contentFrom} durationInFrames={end - contentFrom} layout="none">
        <Captions p={p} />
        <Audio src={staticFile(p.audio)} />
        {p.verses.map((v, i) => (
          <Sequence key={i} from={f(v.start)} durationInFrames={f(v.end) - f(v.start)} layout="none">
            <Line s={{...p.verseLabel, text: v.ref}} width={p.width} />
          </Sequence>
        ))}
      </Sequence>
      <Sequence from={layoutFrom} durationInFrames={end - layoutFrom} layout="none">
        <Line s={p.speakerName} width={p.width} />
      </Sequence>
      <Sequence from={0} durationInFrames={f(p.intro.hold + p.intro.wipe / 2)} layout="none">{img(p.intro.cover)}</Sequence>
      <Sequence from={f(p.intro.hold)} durationInFrames={f(p.intro.wipe)} layout="none"><Wipe color={p.intro.coverColor} dur={p.intro.wipe} /></Sequence>
      {st ? (
        <Audio src={staticFile(st.src)} volume={(fr) => {
          const g = Math.pow(10, st.gainDb / 20);
          return g * Math.min(interpolate(fr, [0, f(st.fadeIn) || 1], [0, 1], {extrapolateRight: 'clamp'}),
            interpolate(fr, [end - (f(st.fadeOut) || 1), end], [1, 0], {extrapolateLeft: 'clamp'}));
        }} />
      ) : null}
    </AbsoluteFill>
  );
};
