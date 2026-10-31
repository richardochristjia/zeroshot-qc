import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, SANS } from '../theme';

export const Title = ({ captions: [name, tagline] }: { captions: string[] }) => {
  const frame = useCurrentFrame();
  const fade = (from: number) => interpolate(frame, [from, from + 20], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', gap: 32 }}>
      <div style={{ opacity: fade(0), color: C.ink, fontFamily: SANS, fontWeight: 600, fontSize: 168 }}>{name}</div>
      <div style={{ opacity: fade(30), color: C.accent, fontFamily: SANS, fontSize: 56 }}>{tagline}</div>
    </AbsoluteFill>
  );
};
