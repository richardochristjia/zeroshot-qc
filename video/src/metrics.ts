import samOnly from '../../backend/demo/runs/20261027T090316Z-sam_only/summary.json';
import samJudge from '../../backend/demo/runs/20261027T091346Z-sam_judge/summary.json';
import samJudgeRef from '../../backend/demo/runs/20261027T094406Z-sam_judge_ref/summary.json';

const row = (label: string, s: typeof samOnly) => ({
  label,
  f1: s.metrics.overall.f1,
  auroc: s.metrics.overall.auroc,
});

export const ROWS = [
  row('Detection only', samOnly),
  row('+ Judge', samJudge),
  row('+ Judge + reference', samJudgeRef),
];

export const N_IMAGES = samJudgeRef.metrics.overall.n;
