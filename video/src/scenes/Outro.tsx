import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, MONO, SANS } from '../theme';

export const Outro = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', gap: 40, opacity }}>
      <div style={{ color: C.ink, fontFamily: MONO, fontSize: 64, background: C.sunken, padding: '24px 48px' }}>
        docker compose up --build
      </div>
      <div style={{ color: C.accent, fontFamily: SANS, fontSize: 48 }}>
        github.com/richardochristjia/zeroshot-qc
      </div>
      <div style={{ color: C.ink2, fontFamily: SANS, fontSize: 26, maxWidth: 1400, textAlign: 'center', marginTop: 60 }}>
        Includes a downscaled subset of the MVTec AD dataset, (c) MVTec Software GmbH, CC BY-NC-SA 4.0.
        Non-commercial use only.
      </div>
    </AbsoluteFill>
  );
};
