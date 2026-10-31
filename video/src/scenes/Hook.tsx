import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { C, SANS } from '../theme';

export const Hook = ({ captions }: { captions: string[] }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const per = durationInFrames / captions.length;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: 160 }}>
      {captions.map((text, i) => {
        const t = frame - i * per;
        const opacity = interpolate(t, [0, 15, per - 15, per], [0, 1, 1, i === captions.length - 1 ? 1 : 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <div
            key={text}
            style={{
              position: 'absolute',
              opacity,
              color: i === 0 ? C.ink : C.ink2,
              fontFamily: SANS,
              fontSize: i === 0 ? 96 : 72,
              textAlign: 'center',
              maxWidth: i === 0 ? 1700 : 1500,
              lineHeight: 1.2,
            }}
          >
            {text}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
