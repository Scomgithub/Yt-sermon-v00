export type TextStyle = {
  text: string;
  font: string;          // family name registered in fonts[]
  size: number;          // px
  tracking: number;      // px added between glyphs (PIL-style, not after the last glyph)
  kerning: 'normal' | 'none';
  color: string;
  baseline: number;      // canvas y of the baseline
  ascent: number;        // font ascent in em (hhea/typo ascender / upem)
  descent: number;       // positive em
  x?: number;            // centre x, default width/2
};
export type CaptionWord = {text: string; start: number; end: number; x: number; verse?: boolean};
export type CaptionLine = {baseline: number; words: CaptionWord[]};
export type CaptionPage = {show: number; hide: number; lines: CaptionLine[]};
export type SermonProps = {
  width: number; height: number; fps: number;
  durationInFrames: number;
  contentStart: number;            // s on the timeline where audio, captions and spectrum start
  layoutStart: number;             // s where the static layout appears (under the wipe)
  fonts: {family: string; src: string}[];
  audio: string;                   // staticFile path
  audioWav?: string;               // staticFile path used for visualizeAudio
  background: string; blueShape: string; redCircle: string;
  portrait: {src: string; scale: number; dy: number};   // full-frame PNG, scaled about canvas centre then moved dy px
  spectrum: {video?: string; dy: number; xs: number[]; barWidth: number; baselineY: number; halfMin: number; halfClip: number; colors: string[]};
  title: TextStyle;
  speakerName: TextStyle;
  captions: {font: string; size: number; ascent: number; descent: number; black: string; red: string;
             kernOverrides: Record<string, number>; pages: CaptionPage[]};
  verses: {start: number; end: number; ref: string}[];       // clip time (s, relative to contentStart)
  verseLabel: Omit<TextStyle, 'text'>;
  intro: {cover: string; coverColor: string; hold: number; wipe: number};
  soundtrack?: {src: string; gainDb: number; fadeIn: number; fadeOut: number} | null;
};
