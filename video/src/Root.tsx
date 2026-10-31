import '@fontsource/fira-sans/400.css';
import '@fontsource/fira-sans/600.css';
import '@fontsource/fira-code/400.css';
import { Composition } from 'remotion';
import { Main } from './Main';
import { FPS, totalFrames } from './script';

export const Root = () => (
  <Composition
    id="Main"
    component={Main}
    durationInFrames={totalFrames()}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
