/** Typed API client for the ZeroShot QC backend (HANDOFF §8).

Every backend call the four pages need flows through here. Boundary
rule (write-typescript): `unknown` in, parsed domain types out — each
parser validates the JSON payload at runtime and throws on mismatch,
so pages never cast. No secrets here: same-origin relative URLs only
(the Vite dev proxy forwards `/api` + `/files` to the backend).
*/

const JSON_HEADERS = { Accept: "application/json" };

// ---------------------------------------------------------------------------
// Domain types (Pydantic sources in `backend/app/schemas.py`, plus the
// router-defined shapes with no Pydantic model: eval rows/summaries and
// the synth generate response).
// ---------------------------------------------------------------------------

export interface MaskRle {
  size: number[];
  counts: string;
}

export interface Detection {
  id: string;
  label: string;
  score: number;
  bbox: [number, number, number, number];
  maskRle: MaskRle;
  areaPx: number;
  lengthPx: number;
  areaMm2: number | null;
  lengthMm: number | null;
}

export interface DefectRuling {
  detectionId: string;
  isRealDefect: boolean;
  ruleViolated: string | null;
  reason: string;
}

export type VerdictWord = "PASS" | "FAIL";

export interface Verdict {
  verdict: VerdictWord;
  confidence: number;
  rulings: DefectRuling[];
  missedDefects: string[];
  summary: string;
}

export interface ProductProfile {
  id: string;
  name: string;
  defectPrompts: string[];
  rules: string;
  mmPerPx: number | null;
  minScore: number;
  referenceImage: string | null;
}

export interface InspectionTimings {
  segment: number;
  judge: number;
  total: number;
}

export interface InspectionResult {
  id: string;
  profileId: string;
  detections: Detection[];
  verdict: Verdict;
  overlayUrl: string;
  timingsMs: InspectionTimings;
}

/** One `results.jsonl` row (keys per `backend/app/eval/run.py:179-190`)
 * plus the `image_url` the eval router injects per row (`routers/eval.py`). */
export interface EvalResultRow {
  category: string;
  image: string;
  label: "good" | "defective";
  defectType: string;
  verdict: VerdictWord;
  confidence: number;
  failScore: number;
  nDetections: number;
  iou: number | null;
  imageUrl: string | null;
}

export interface CategoryMetrics {
  precision: number;
  recall: number;
  f1: number;
  accuracy: number;
  auroc: number;
  n: number;
  tp: number;
  tn: number;
  fp: number;
  fn: number;
  iou: number | null;
}

export interface EvalMetrics {
  perCategory: Record<string, CategoryMetrics>;
  overall: CategoryMetrics;
}

/** A `summary.json` document (keys per `run.py:202-213`). Optional keys
 * stay optional: pre-M6 runs may lack `source` and other keys the
 * current writer emits, so pages must not assume them. */
export interface EvalRunSummary {
  runId: string;
  mode: string;
  source: string;
  adapter: string | null;
  seed: number | null;
  categories: string[];
  nGood: number | null;
  nDefective: number | null;
  rules: string | null;
  metrics: EvalMetrics | null;
}

export interface EvalRunDetail {
  summary: EvalRunSummary;
  results: EvalResultRow[];
}

export interface SynthPair {
  imageUrl: string;
  maskUrl: string | null;
}

/** `POST /api/synth/generate` response (`routers/synth.py:63-77`). */
export interface SynthGenerateResponse {
  profileId: string;
  defect: string;
  count: number;
  pairs: SynthPair[];
}

export interface SynthGenerateRequest {
  profileId: string;
  defect: string;
  n: number;
  seed?: number;
}

/** `POST /api/profiles/from-sop` body (`routers/profiles.py:22-24`). */
export interface SopDraftRequest {
  sopText: string;
  categoryName: string;
}

// ---------------------------------------------------------------------------
// Typed errors.
// ---------------------------------------------------------------------------

/** Base for every expected backend failure: HTTP status + detail string. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Inspect 422: the judge failed twice (`routers/inspect.py`). */
export class InspectJudgeError extends ApiError {
  constructor(detail: string) {
    super(422, detail);
    this.name = "InspectJudgeError";
  }
}

/** Inspect 422: the uploaded bytes are not a decodable image. */
export class UndecodableImageError extends ApiError {
  constructor(detail: string) {
    super(422, detail);
    this.name = "UndecodableImageError";
  }
}

/** PUT 422: body `id` disagrees with the path id (`routers/profiles.py`). */
export class ProfileIdMismatchError extends ApiError {
  constructor(detail: string) {
    super(422, detail);
    this.name = "ProfileIdMismatchError";
  }
}

/** Any other 422 (invalid PUT body, bad from-sop body, synth `n < 1`). */
export class RequestValidationError extends ApiError {
  constructor(detail: string) {
    super(422, detail);
    this.name = "RequestValidationError";
  }
}

/** 404: unknown profile, missing eval run, missing `/files/` path. */
export class NotFoundError extends ApiError {
  constructor(detail: string) {
    super(404, detail);
    this.name = "NotFoundError";
  }
}

// ---------------------------------------------------------------------------
// Runtime parsing helpers (`unknown` in, validated values out).
// ---------------------------------------------------------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fail(path: string): never {
  throw new ApiError(500, `unexpected API shape at ${path}`);
}

function reqString(obj: Record<string, unknown>, key: string, path: string): string {
  const value = obj[key];
  if (typeof value !== "string") fail(`${path}.${key}`);
  return value;
}

function reqNumber(obj: Record<string, unknown>, key: string, path: string): number {
  const value = obj[key];
  if (typeof value !== "number" || Number.isNaN(value)) fail(`${path}.${key}`);
  return value;
}

function reqBoolean(obj: Record<string, unknown>, key: string, path: string): boolean {
  const value = obj[key];
  if (typeof value !== "boolean") fail(`${path}.${key}`);
  return value;
}

function optString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function optNumber(value: unknown): number | null {
  return typeof value === "number" && !Number.isNaN(value) ? value : null;
}

function reqStringArray(
  obj: Record<string, unknown>,
  key: string,
  path: string,
): string[] {
  const value = obj[key];
  if (!Array.isArray(value) || value.some((v) => typeof v !== "string")) {
    fail(`${path}.${key}`);
  }
  return value.filter((v): v is string => typeof v === "string");
}

function reqArray(obj: Record<string, unknown>, key: string, path: string): unknown[] {
  const value = obj[key];
  if (!Array.isArray(value)) fail(`${path}.${key}`);
  return value.slice();
}

function parseVerdictWord(value: unknown, path: string): VerdictWord {
  if (value === "PASS" || value === "FAIL") return value;
  fail(path);
}

function parseMaskRle(value: unknown, path: string): MaskRle {
  if (!isRecord(value)) fail(path);
  const size = value["size"];
  const counts = value["counts"];
  if (!Array.isArray(size) || size.some((v) => typeof v !== "number")) {
    fail(`${path}.size`);
  }
  if (typeof counts !== "string") fail(`${path}.counts`);
  return {
    size: size.filter((v): v is number => typeof v === "number"),
    counts,
  };
}

function parseDetection(value: unknown, path: string): Detection {
  if (!isRecord(value)) fail(path);
  const bbox = value["bbox"];
  if (
    !Array.isArray(bbox) ||
    bbox.length !== 4 ||
    bbox.some((v) => typeof v !== "number")
  ) {
    fail(`${path}.bbox`);
  }
  const nums = bbox.filter((v): v is number => typeof v === "number");
  return {
    id: reqString(value, "id", path),
    label: reqString(value, "label", path),
    score: reqNumber(value, "score", path),
    bbox: [nums[0], nums[1], nums[2], nums[3]],
    maskRle: parseMaskRle(value["mask_rle"], `${path}.mask_rle`),
    areaPx: reqNumber(value, "area_px", path),
    lengthPx: reqNumber(value, "length_px", path),
    areaMm2: value["area_mm2"] == null ? null : reqNumber(value, "area_mm2", path),
    lengthMm:
      value["length_mm"] == null ? null : reqNumber(value, "length_mm", path),
  };
}

function parseDefectRuling(value: unknown, path: string): DefectRuling {
  if (!isRecord(value)) fail(path);
  return {
    detectionId: reqString(value, "detection_id", path),
    isRealDefect: reqBoolean(value, "is_real_defect", path),
    ruleViolated:
      value["rule_violated"] == null ? null : reqString(value, "rule_violated", path),
    reason: reqString(value, "reason", path),
  };
}

function parseVerdict(value: unknown, path: string): Verdict {
  if (!isRecord(value)) fail(path);
  return {
    verdict: parseVerdictWord(value["verdict"], `${path}.verdict`),
    confidence: reqNumber(value, "confidence", path),
    rulings: reqArray(value, "rulings", path).map((r, i) =>
      parseDefectRuling(r, `${path}.rulings[${i}]`),
    ),
    missedDefects: reqStringArray(value, "missed_defects", path),
    summary: reqString(value, "summary", path),
  };
}

function parseProductProfile(value: unknown): ProductProfile {
  const path = "ProductProfile";
  if (!isRecord(value)) fail(path);
  return {
    id: reqString(value, "id", path),
    name: reqString(value, "name", path),
    defectPrompts: reqStringArray(value, "defect_prompts", path),
    rules: reqString(value, "rules", path),
    mmPerPx: value["mm_per_px"] == null ? null : reqNumber(value, "mm_per_px", path),
    minScore:
      value["min_score"] === undefined
        ? 0.3
        : reqNumber(value, "min_score", path),
    referenceImage:
      value["reference_image"] == null
        ? null
        : reqString(value, "reference_image", path),
  };
}

function parseInspectionResult(value: unknown): InspectionResult {
  const path = "InspectionResult";
  if (!isRecord(value)) fail(path);
  const timings = value["timings_ms"];
  if (!isRecord(timings)) fail(`${path}.timings_ms`);
  return {
    id: reqString(value, "id", path),
    profileId: reqString(value, "profile_id", path),
    detections: reqArray(value, "detections", path).map((d, i) =>
      parseDetection(d, `${path}.detections[${i}]`),
    ),
    verdict: parseVerdict(value["verdict"], `${path}.verdict`),
    overlayUrl: reqString(value, "overlay_url", path),
    timingsMs: {
      segment: reqNumber(timings, "segment", `${path}.timings_ms`),
      judge: reqNumber(timings, "judge", `${path}.timings_ms`),
      total: reqNumber(timings, "total", `${path}.timings_ms`),
    },
  };
}

function parseEvalResultRow(value: unknown, index: number): EvalResultRow {
  const path = `results[${index}]`;
  if (!isRecord(value)) fail(path);
  const label = value["label"];
  if (label !== "good" && label !== "defective") fail(`${path}.label`);
  return {
    category: reqString(value, "category", path),
    image: reqString(value, "image", path),
    label,
    defectType: optString(value["defect_type"]) ?? "",
    verdict: parseVerdictWord(value["verdict"], `${path}.verdict`),
    confidence: reqNumber(value, "confidence", path),
    failScore: reqNumber(value, "fail_score", path),
    nDetections: reqNumber(value, "n_detections", path),
    iou: value["iou"] == null ? null : reqNumber(value, "iou", path),
    imageUrl: optString(value["image_url"]),
  };
}

function parseCategoryMetrics(value: unknown, path: string): CategoryMetrics {
  if (!isRecord(value)) fail(path);
  return {
    precision: reqNumber(value, "precision", path),
    recall: reqNumber(value, "recall", path),
    f1: reqNumber(value, "f1", path),
    accuracy:
      typeof value["accuracy"] === "number" ? value["accuracy"] : 0,
    auroc: reqNumber(value, "auroc", path),
    n: reqNumber(value, "n", path),
    tp: typeof value["tp"] === "number" ? value["tp"] : 0,
    tn: typeof value["tn"] === "number" ? value["tn"] : 0,
    fp: typeof value["fp"] === "number" ? value["fp"] : 0,
    fn: typeof value["fn"] === "number" ? value["fn"] : 0,
    iou: value["iou"] == null ? null : reqNumber(value, "iou", path),
  };
}

function parseEvalMetrics(value: unknown, path: string): EvalMetrics {
  if (!isRecord(value)) fail(path);
  const perCategory: Record<string, CategoryMetrics> = {};
  const raw = value["per_category"];
  if (!isRecord(raw)) fail(`${path}.per_category`);
  for (const [name, row] of Object.entries(raw)) {
    perCategory[name] = parseCategoryMetrics(row, `${path}.per_category.${name}`);
  }
  return {
    perCategory,
    overall: parseCategoryMetrics(value["overall"], `${path}.overall`),
  };
}

function parseEvalRunSummary(value: unknown): EvalRunSummary {
  const path = "EvalRunSummary";
  if (!isRecord(value)) fail(path);
  const categories = value["categories"];
  return {
    runId: reqString(value, "run_id", path),
    mode: optString(value["mode"]) ?? "",
    source: optString(value["source"]) ?? "mvtec",
    adapter: optString(value["adapter"]),
    seed: optNumber(value["seed"]),
    categories:
      Array.isArray(categories) && categories.every((c) => typeof c === "string")
        ? categories.filter((c): c is string => typeof c === "string")
        : [],
    nGood: optNumber(value["n_good"]),
    nDefective: optNumber(value["n_defective"]),
    rules: optString(value["rules"]),
    metrics:
      value["metrics"] == null
        ? null
        : parseEvalMetrics(value["metrics"], `${path}.metrics`),
  };
}

function parseEvalRunDetail(value: unknown): EvalRunDetail {
  const path = "EvalRunDetail";
  if (!isRecord(value)) fail(path);
  return {
    summary: parseEvalRunSummary(value["summary"]),
    results: reqArray(value, "results", path).map((r, i) =>
      parseEvalResultRow(r, i),
    ),
  };
}

function parseSynthGenerateResponse(value: unknown): SynthGenerateResponse {
  const path = "SynthGenerateResponse";
  if (!isRecord(value)) fail(path);
  return {
    profileId: reqString(value, "profile_id", path),
    defect: reqString(value, "defect", path),
    count: reqNumber(value, "count", path),
    pairs: reqArray(value, "pairs", path).map((p, i) => {
      if (!isRecord(p)) fail(`${path}.pairs[${i}]`);
      return {
        imageUrl: reqString(p, "image_url", `${path}.pairs[${i}]`),
        maskUrl:
          p["mask_url"] == null
            ? null
            : reqString(p, "mask_url", `${path}.pairs[${i}]`),
      };
    }),
  };
}

// ---------------------------------------------------------------------------
// Transport.
// ---------------------------------------------------------------------------

function extractDetail(body: unknown): string {
  if (isRecord(body)) {
    const detail = body["detail"];
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (isRecord(item)) {
            const msg = item["msg"];
            const loc = item["loc"];
            const where = Array.isArray(loc) ? loc.join(".") : "";
            return typeof msg === "string"
              ? `${where}: ${msg}`.replace(/^: /, "")
              : null;
          }
          return typeof item === "string" ? item : null;
        })
        .filter((s): s is string => s !== null);
      if (parts.length > 0) return parts.join("; ");
    }
  }
  return "request failed";
}

async function throwForStatus(
  response: Response,
  context: "inspect" | "profiles-put" | "generic",
): Promise<never> {
  let detail = `request failed with status ${response.status}`;
  try {
    detail = extractDetail(await response.json());
  } catch {
    // Keep the default detail when the error body is not JSON.
  }
  if (response.status === 404) throw new NotFoundError(detail);
  if (response.status === 422) {
    if (context === "inspect") {
      if (detail.startsWith("could not decode image")) {
        throw new UndecodableImageError(detail);
      }
      throw new InspectJudgeError(detail);
    }
    if (context === "profiles-put" && detail.includes("does not match path id")) {
      throw new ProfileIdMismatchError(detail);
    }
    throw new RequestValidationError(detail);
  }
  throw new ApiError(response.status, detail);
}

async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(path, { headers: JSON_HEADERS, signal });
  if (!response.ok) {
    await throwForStatus(response, "generic");
  }
  const data: unknown = await response.json();
  return data;
}

async function postJson(
  path: string,
  body: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<unknown> {
  const response = await fetch(path, {
    method: "POST",
    headers: { ...JSON_HEADERS, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    await throwForStatus(response, "generic");
  }
  const data: unknown = await response.json();
  return data;
}

// ---------------------------------------------------------------------------
// Endpoint functions (§8 shapes the four pages need).
// ---------------------------------------------------------------------------

export interface InspectParams {
  image: File | Blob;
  filename: string;
  profileId: string;
  rules?: string;
  signal?: AbortSignal;
}

/** POST /api/inspect: multipart image + profile_id + optional rules
 * override (the profile itself is untouched). Throws
 * {@link UndecodableImageError} on undecodable bytes, {@link InspectJudgeError}
 * on double judge failure, {@link NotFoundError} on unknown profile. */
export async function inspectImage(params: InspectParams): Promise<InspectionResult> {
  const form = new FormData();
  form.append("image", params.image, params.filename);
  form.append("profile_id", params.profileId);
  if (params.rules !== undefined && params.rules !== "") {
    form.append("rules", params.rules);
  }
  const response = await fetch("/api/inspect", {
    method: "POST",
    body: form,
    signal: params.signal,
  });
  if (!response.ok) {
    await throwForStatus(response, "inspect");
  }
  return parseInspectionResult(await response.json());
}

/** GET /api/profiles: every valid profile sorted by id. */
export async function listProfiles(signal?: AbortSignal): Promise<ProductProfile[]> {
  const data = await getJson("/api/profiles", signal);
  if (!Array.isArray(data)) fail("ProductProfile[]");
  return data.map((item) => parseProductProfile(item));
}

/** GET /api/profiles/:id. Throws {@link NotFoundError} on unknown id. */
export async function getProfile(
  profileId: string,
  signal?: AbortSignal,
): Promise<ProductProfile> {
  const data = await getJson(
    `/api/profiles/${encodeURIComponent(profileId)}`,
    signal,
  );
  return parseProductProfile(data);
}

/** PUT /api/profiles/:id: validate-and-save. Throws
 * {@link ProfileIdMismatchError} when `profile.id` disagrees with the
 * path, {@link RequestValidationError} on an invalid body (the file is
 * left untouched), {@link NotFoundError} on an invalid path id. */
export async function putProfile(
  profile: ProductProfile,
  signal?: AbortSignal,
): Promise<ProductProfile> {
  const response = await fetch(
    `/api/profiles/${encodeURIComponent(profile.id)}`,
    {
      method: "PUT",
      headers: { ...JSON_HEADERS, "Content-Type": "application/json" },
      body: JSON.stringify({
        id: profile.id,
        name: profile.name,
        defect_prompts: profile.defectPrompts,
        rules: profile.rules,
        mm_per_px: profile.mmPerPx,
        min_score: profile.minScore,
        reference_image: profile.referenceImage,
      }),
      signal,
    },
  );
  if (!response.ok) {
    await throwForStatus(response, "profiles-put");
  }
  return parseProductProfile(await response.json());
}

/** POST /api/profiles/from-sop: draft a profile from SOP text. Never
 * saves anything — the caller decides whether to persist the draft via
 * {@link putProfile}. Throws {@link RequestValidationError} on double
 * validation failure. */
export async function draftProfileFromSop(
  request: SopDraftRequest,
  signal?: AbortSignal,
): Promise<ProductProfile> {
  const data = await postJson(
    "/api/profiles/from-sop",
    { sop_text: request.sopText, category_name: request.categoryName },
    signal,
  );
  return parseProductProfile(data);
}

/** GET /api/eval/runs: every run summary; dirs without `summary.json`
 * are skipped server-side. */
export async function listEvalRuns(signal?: AbortSignal): Promise<EvalRunSummary[]> {
  const data = await getJson("/api/eval/runs", signal);
  if (!Array.isArray(data)) fail("EvalRunSummary[]");
  return data.map((item) => parseEvalRunSummary(item));
}

/** GET /api/eval/runs/:id → `{summary, results}`. Throws
 * {@link NotFoundError} on missing id (including traversal attempts). */
export async function getEvalRun(
  runId: string,
  signal?: AbortSignal,
): Promise<EvalRunDetail> {
  const data = await getJson(
    `/api/eval/runs/${encodeURIComponent(runId)}`,
    signal,
  );
  return parseEvalRunDetail(data);
}

/** POST /api/synth/generate: generate `n` synthetic pairs. Throws
 * {@link RequestValidationError} on `n < 1`, {@link NotFoundError} on
 * unknown profile.
 *
 * NOTE: there is deliberately no gallery-listing function. The backend
 * exposes no synth list endpoint and `/files/` serves files only (no
 * directory listing, `main.py:serve_data_file`), so the Synthetic page
 * cannot enumerate `data/synth/` pairs through this client — that needs
 * a backend change tracked as discovered work, not invented here. */
export async function generateSynthetic(
  request: SynthGenerateRequest,
  signal?: AbortSignal,
): Promise<SynthGenerateResponse> {
  const body: Record<string, string | number> = {
    profile_id: request.profileId,
    defect: request.defect,
    n: request.n,
    seed: request.seed ?? 0,
  };
  const data = await postJson("/api/synth/generate", body, signal);
  return parseSynthGenerateResponse(data);
}

/** Serialize a profile back to the backend's snake_case body shape
 * (for callers that build the PUT payload themselves). */
export function toProfileBody(profile: ProductProfile): Record<string, unknown> {
  return {
    id: profile.id,
    name: profile.name,
    defect_prompts: profile.defectPrompts,
    rules: profile.rules,
    mm_per_px: profile.mmPerPx,
    min_score: profile.minScore,
    reference_image: profile.referenceImage,
  };
}
