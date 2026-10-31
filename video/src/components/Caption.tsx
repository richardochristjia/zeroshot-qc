import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { C, SANS } from '../theme';

const FADE = 9;

export const Caption = ({ lines }: { lines: string[] }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  if (!lines.length) return null;
  const per = durationInFrames / lines.length;
  const i = Math.min(lines.length - 1, Math.floor(frame / per));
  const local = frame - i * per;
  const opacity = interpolate(local, [0, FADE, per - FADE, per], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 56,
        display: 'flex',
        justifyContent: 'center',
        opacity,
      }}
    >
      <div
        style={{
          background: C.surface,
          border: `1px solid ${C.line}`,
          color: C.ink,
          fontFamily: SANS,
          fontSize: 44,
          padding: '18px 36px',
          maxWidth: 1500,
          textAlign: 'center',
        }}
      >
        {lines[i]}
      </div>
    </div>
  );
};
