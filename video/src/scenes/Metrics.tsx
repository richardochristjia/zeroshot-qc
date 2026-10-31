import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { N_IMAGES, ROWS } from '../metrics';
import { C, SANS } from '../theme';

const MAX_W = 900;

export const Metrics = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ justifyContent: 'center', padding: '0 160px 120px', gap: 48, fontFamily: SANS }}>
      {ROWS.map((r, i) => {
        const p = spring({ frame: frame - 15 - i * 20, fps, config: { damping: 200 } });
        return (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 32, whiteSpace: 'nowrap' }}>
            <div style={{ width: 440, flexShrink: 0, color: C.ink, fontSize: 40 }}>{r.label}</div>
            <div style={{ width: MAX_W, flexShrink: 0, height: 48, background: C.sunken }}>
              <div style={{ width: MAX_W * r.f1 * p, height: '100%', background: C.data }} />
            </div>
            <div style={{ width: 120, flexShrink: 0, color: C.ink, fontSize: 48, fontVariantNumeric: 'tabular-nums' }}>
              {(r.f1 * p).toFixed(2)}
            </div>
            <div style={{ color: C.ink2, fontSize: 30, fontVariantNumeric: 'tabular-nums' }}>
              AUROC {r.auroc.toFixed(2)}
            </div>
          </div>
        );
      })}
      <div style={{ color: C.ink2, fontSize: 28 }}>
        F1 on {N_IMAGES} MVTec AD images, 5 categories
      </div>
    </AbsoluteFill>
  );
};
