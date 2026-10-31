import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { FPS } from '../script';
import { C, SANS } from '../theme';

const STEPS = [
  { title: 'Image', body: 'A photo of the part', color: C.ink },
  { title: 'SAM 3.1', body: 'Proposes candidate regions from text prompts', color: C.detect },
  { title: 'Muse Spark', body: 'Judges each against your rules and a known-good reference', color: C.accent },
  { title: 'Verdict', body: 'FAIL forced in code on any violated rule, missed defect, or wrong part', color: C.fail },
];
const GAP = 4 * FPS;

export const Pipeline = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 24 }}>
      {STEPS.map((s, i) => {
        const p = spring({ frame: frame - 15 - i * GAP, fps, config: { damping: 200 } });
        return (
          <div key={s.title} style={{ display: 'flex', alignItems: 'center', gap: 24, opacity: p }}>
            {i > 0 && <div style={{ width: 48, height: 2, background: C.line }} />}
            <div
              style={{
                width: 360,
                height: 360,
                background: C.surface,
                border: `1px solid ${C.line}`,
                borderTop: `4px solid ${s.color}`,
                padding: 28,
                fontFamily: SANS,
              }}
            >
              <div style={{ color: s.color, fontSize: 44, fontWeight: 600 }}>{s.title}</div>
              <div style={{ color: C.ink2, fontSize: 30, marginTop: 16, lineHeight: 1.3 }}>{s.body}</div>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
