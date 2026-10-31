import { useEffect } from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  getStaticFiles,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type { Zoom } from '../script';
import { C, MONO, SANS } from '../theme';

const Placeholder = ({ id, path }: { id: string; path: string }) => {
  useEffect(() => {
    console.warn(`Missing recording ${path} (scene ${id}); placeholder rendered`);
  }, [id, path]);
  return (
    <AbsoluteFill
      style={{ background: C.sunken, alignItems: 'center', justifyContent: 'center', gap: 20 }}
    >
      <div style={{ color: C.detect, fontFamily: SANS, fontSize: 40 }}>Recording missing: {id}</div>
      <div style={{ color: C.ink, fontFamily: MONO, fontSize: 32 }}>{path}</div>
      <div style={{ color: C.ink2, fontFamily: SANS, fontSize: 28 }}>See video/SHOTS.md</div>
    </AbsoluteFill>
  );
};

export const Recording = ({ id, file, zoom = [] }: { id: string; file: string; zoom?: Zoom[] }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const name = `recordings/${file}`;
  if (!getStaticFiles().some((f) => f.name === name)) return <Placeholder id={id} path={`video/public/${name}`} />;

  const at = zoom.map((k) => k.at * fps);
  const lerp = (pick: (k: Zoom) => number, fallback: number) =>
    zoom.length < 2
      ? (zoom[0] ? pick(zoom[0]) : fallback)
      : interpolate(frame, at, zoom.map(pick), {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
  const s = lerp((k) => k.scale, 1);
  const x = lerp((k) => k.x, 0.5);
  const y = lerp((k) => k.y, 0.5);
  // Centre the focus point, but never pan past the frame edge.
  const tx = Math.min(0, Math.max(width * (1 - s), width * (0.5 - s * x)));
  const ty = Math.min(0, Math.max(height * (1 - s), height * (0.5 - s * y)));
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <AbsoluteFill style={{ transformOrigin: '0 0', transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
        <OffthreadVideo src={staticFile(name)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
