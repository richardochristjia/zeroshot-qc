import type { ComponentType } from 'react';
import { AbsoluteFill, Series } from 'remotion';
import { Caption } from './components/Caption';
import { Recording } from './components/Recording';
import { Hook } from './scenes/Hook';
import { Metrics } from './scenes/Metrics';
import { Outro } from './scenes/Outro';
import { Pipeline } from './scenes/Pipeline';
import { Title } from './scenes/Title';
import { FPS, SCENES } from './script';
import { C } from './theme';

// Hook and Title draw their captions as headlines; every other scene gets a lower third.
const GRAPHICS: Record<string, ComponentType<{ captions: string[] }>> = {
  hook: Hook,
  title: Title,
  pipeline: Pipeline,
  proof: Metrics,
  outro: Outro,
};
const HEADLINE = new Set(['hook', 'title']);

export const Main = () => (
  <AbsoluteFill style={{ background: C.ground }}>
    <Series>
      {SCENES.map((s) => {
        const Graphic = GRAPHICS[s.id];
        return (
          <Series.Sequence key={s.id} durationInFrames={s.seconds * FPS}>
            {s.recording ? <Recording id={s.id} file={s.recording} zoom={s.zoom} /> : <Graphic captions={s.captions} />}
            {!HEADLINE.has(s.id) && <Caption lines={s.captions} />}
          </Series.Sequence>
        );
      })}
    </Series>
  </AbsoluteFill>
);
