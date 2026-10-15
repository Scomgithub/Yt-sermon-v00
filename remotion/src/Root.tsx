import React from 'react';
import {Composition} from 'remotion';
import {SermonClip} from './SermonClip';
import type {SermonProps} from './types';
import defaults from '../clips/default-props.json';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="SermonClip"
    component={SermonClip as unknown as React.FC<Record<string, unknown>>}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={defaults as unknown as Record<string, unknown>}
    calculateMetadata={({props}) => {
      const p = props as unknown as SermonProps;
      return {durationInFrames: p.durationInFrames, fps: p.fps, width: p.width, height: p.height};
    }}
  />
);
