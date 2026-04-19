/**
 * Sprint 3: Frontend restore logic tests.
 *
 * Tests:
 * 1. Backend restore failure sets error message
 * 2. Data validation for outline/polished_outline
 * 3. slidePreviews empty does not roll back step (uses regen flag instead)
 * 4. Normal data restore maintains step=6
 */

// ---------------------------------------------------------------------------
// Helper: Simulates the restore logic for data validation
// ---------------------------------------------------------------------------

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

interface RestoreData {
  step: number;
  workflow_mode: "full-ai" | "hybrid";
  outline: any;
  polished_outline: any;
  settings: { slidePreviews?: string[] };
}

function computeRestoredState(data: RestoreData) {
  let adjustedStep = data.step as Step;
  const s = data.settings ?? {};
  const restoredPreviews: string[] = s.slidePreviews ?? [];
  let validPreviews = restoredPreviews;

  const slideCompleteStep = data.workflow_mode === "full-ai" ? 6 : 9;

  // Data validation: outline check
  if (adjustedStep >= 4 && (!data.outline || typeof data.outline !== "object")) {
    adjustedStep = 3 as Step;
  }

  // Data validation: polished_outline check (full-ai only)
  if (
    adjustedStep >= 5 &&
    data.workflow_mode === "full-ai" &&
    (!data.polished_outline || typeof data.polished_outline !== "object")
  ) {
    adjustedStep = 4 as Step;
  }

  // Slide preview missing: flag instead of rollback
  let needsSlideRegeneration = false;
  if (data.step >= slideCompleteStep && restoredPreviews.length === 0) {
    needsSlideRegeneration = true;
  }

  return {
    adjustedStep,
    validPreviews,
    needsSlideRegeneration,
  };
}

function computeErrorMessage(backendRestoreFailed: boolean): string | null {
  return backendRestoreFailed
    ? "バックエンドの復元に失敗しました。スライドの再生成や動画生成を行うには、ページを再読み込みしてください。"
    : null;
}

// ---------------------------------------------------------------------------
// 1. Backend restore failure shows error message
// ---------------------------------------------------------------------------

describe("backend restore failure error message", () => {
  it("returns error message when backend restore fails", () => {
    const msg = computeErrorMessage(true);
    expect(msg).toBeTruthy();
    expect(msg).toContain("バックエンド");
    expect(msg).toContain("再読み込み");
  });

  it("returns null when backend restore succeeds", () => {
    const msg = computeErrorMessage(false);
    expect(msg).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 2. Data validation: outline missing rolls back to step 3
// ---------------------------------------------------------------------------

describe("restore data validation - outline", () => {
  it("rolls back to step 3 when outline is null at step >= 4", () => {
    const result = computeRestoredState({
      step: 5,
      workflow_mode: "full-ai",
      outline: null,
      polished_outline: { slides: [] },
      settings: {},
    });
    expect(result.adjustedStep).toBe(3);
  });

  it("rolls back to step 3 when outline is undefined at step >= 4", () => {
    const result = computeRestoredState({
      step: 6,
      workflow_mode: "full-ai",
      outline: undefined,
      polished_outline: { slides: [] },
      settings: {},
    });
    expect(result.adjustedStep).toBe(3);
  });

  it("rolls back to step 3 when outline is a string (invalid type)", () => {
    const result = computeRestoredState({
      step: 4,
      workflow_mode: "full-ai",
      outline: "invalid string",
      polished_outline: null,
      settings: {},
    });
    expect(result.adjustedStep).toBe(3);
  });

  it("does not roll back when outline is a valid object at step >= 4", () => {
    const result = computeRestoredState({
      step: 4,
      workflow_mode: "full-ai",
      outline: { slides: [{ title: "Test" }] },
      polished_outline: null,
      settings: {},
    });
    expect(result.adjustedStep).toBe(4);
  });
});

// ---------------------------------------------------------------------------
// 3. Data validation: polished_outline missing (full-ai) rolls back to step 4
// ---------------------------------------------------------------------------

describe("restore data validation - polished_outline", () => {
  it("rolls back to step 4 when polished_outline is null at step >= 5 (full-ai)", () => {
    const result = computeRestoredState({
      step: 6,
      workflow_mode: "full-ai",
      outline: { slides: [] },
      polished_outline: null,
      settings: { slidePreviews: ["http://example.com/1.png"] },
    });
    expect(result.adjustedStep).toBe(4);
  });

  it("rolls back to step 4 when polished_outline is a number (invalid type)", () => {
    const result = computeRestoredState({
      step: 5,
      workflow_mode: "full-ai",
      outline: { slides: [] },
      polished_outline: 42,
      settings: {},
    });
    expect(result.adjustedStep).toBe(4);
  });

  it("does not roll back polished_outline check for hybrid mode", () => {
    const result = computeRestoredState({
      step: 5,
      workflow_mode: "hybrid",
      outline: { slides: [] },
      polished_outline: null,
      settings: {},
    });
    expect(result.adjustedStep).toBe(5);
  });

  it("does not roll back when polished_outline is valid at step >= 5 (full-ai)", () => {
    const result = computeRestoredState({
      step: 6,
      workflow_mode: "full-ai",
      outline: { slides: [] },
      polished_outline: { slides: [{ title: "Polished" }] },
      settings: { slidePreviews: ["http://example.com/1.png"] },
    });
    expect(result.adjustedStep).toBe(6);
  });
});

// ---------------------------------------------------------------------------
// 4. slidePreviews empty: no rollback, uses regeneration flag
// ---------------------------------------------------------------------------

describe("slidePreviews empty does not roll back step", () => {
  it("sets needsSlideRegeneration=true when previews empty at step >= slideCompleteStep (full-ai)", () => {
    const result = computeRestoredState({
      step: 6,
      workflow_mode: "full-ai",
      outline: { slides: [] },
      polished_outline: { slides: [] },
      settings: { slidePreviews: [] },
    });
    // Step should stay at 6, NOT roll back to 5
    expect(result.adjustedStep).toBe(6);
    expect(result.needsSlideRegeneration).toBe(true);
  });

  it("sets needsSlideRegeneration=true when previews empty at step >= 9 (hybrid)", () => {
    const result = computeRestoredState({
      step: 9,
      workflow_mode: "hybrid",
      outline: { slides: [] },
      polished_outline: null,
      settings: { slidePreviews: [] },
    });
    expect(result.adjustedStep).toBe(9);
    expect(result.needsSlideRegeneration).toBe(true);
  });

  it("does not set needsSlideRegeneration when previews exist", () => {
    const result = computeRestoredState({
      step: 6,
      workflow_mode: "full-ai",
      outline: { slides: [] },
      polished_outline: { slides: [] },
      settings: { slidePreviews: ["http://example.com/slide1.png"] },
    });
    expect(result.adjustedStep).toBe(6);
    expect(result.needsSlideRegeneration).toBe(false);
  });

  it("does not set needsSlideRegeneration for steps before slide completion", () => {
    const result = computeRestoredState({
      step: 4,
      workflow_mode: "full-ai",
      outline: { slides: [] },
      polished_outline: null,
      settings: { slidePreviews: [] },
    });
    expect(result.adjustedStep).toBe(4);
    expect(result.needsSlideRegeneration).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 5. Normal data: step=6 is maintained
// ---------------------------------------------------------------------------

describe("normal data restore maintains correct step", () => {
  it("maintains step=6 with valid full-ai data and slide previews", () => {
    const result = computeRestoredState({
      step: 6,
      workflow_mode: "full-ai",
      outline: { slides: [{ title: "Slide 1" }] },
      polished_outline: { slides: [{ title: "Polished 1" }] },
      settings: { slidePreviews: ["http://example.com/1.png", "http://example.com/2.png"] },
    });
    expect(result.adjustedStep).toBe(6);
    expect(result.needsSlideRegeneration).toBe(false);
    expect(result.validPreviews).toEqual(["http://example.com/1.png", "http://example.com/2.png"]);
  });

  it("maintains step=9 with valid hybrid data and slide previews", () => {
    const result = computeRestoredState({
      step: 9,
      workflow_mode: "hybrid",
      outline: { slides: [{ title: "Slide 1" }] },
      polished_outline: null,
      settings: { slidePreviews: ["http://example.com/1.png"] },
    });
    expect(result.adjustedStep).toBe(9);
    expect(result.needsSlideRegeneration).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 6. Video recovery decision logic.
//
// Mirrors the branch in app/page.tsx that decides whether to trust the DB's
// stored video_url, rewind the step, or show the "動画が保存されていませんでした"
// banner. We test the logic independent of React so regressions are caught
// even without rendering the full restore flow.
//
// Contract (see app/page.tsx restore useEffect):
//   - video_recovered && video_url  → use the recovered URL, no rewind
//   - video_expired                 → clear URL, rewind step 10 → 8/6, set missing
//   - step==10 && !video_storage_path (defensive race-window catch)
//                                   → clear URL, rewind step 10 → 8/6, set missing
//   - step==10 else                 → clear URL, rewind step 10 → 8/6 (defensive)
// ---------------------------------------------------------------------------

interface VideoRestoreInput {
  adjustedStep: number;
  workflowMode: "full-ai" | "hybrid" | null;
  data: { video_url?: string | null; video_storage_path?: string | null };
  restoreData: {
    video_recovered?: boolean;
    video_url?: string | null;
    video_expired?: boolean;
  };
}

function computeVideoRestore(input: VideoRestoreInput) {
  let restoredVideoUrl: string | null = input.data.video_url ?? null;
  let restoredVideoMissing = false;
  let adjustedStep = input.adjustedStep;
  const { restoreData, data, workflowMode } = input;

  if (restoreData.video_recovered && restoreData.video_url) {
    restoredVideoUrl = `API${restoreData.video_url}?t=0`;
  } else if (
    restoreData.video_expired ||
    (adjustedStep === 10 && !data.video_storage_path)
  ) {
    restoredVideoUrl = null;
    restoredVideoMissing = true;
    if (adjustedStep === 10) {
      adjustedStep = workflowMode === "full-ai" ? 6 : 8;
    }
  } else if (adjustedStep === 10) {
    restoredVideoUrl = null;
    restoredVideoMissing = true;
    adjustedStep = workflowMode === "full-ai" ? 6 : 8;
  }
  return { restoredVideoUrl, restoredVideoMissing, adjustedStep };
}

describe("video restore decision logic", () => {
  it("uses recovered url when backend confirms recovery", () => {
    const r = computeVideoRestore({
      adjustedStep: 10,
      workflowMode: "full-ai",
      data: { video_url: "/video/old", video_storage_path: "u/p/video.mp4" },
      restoreData: { video_recovered: true, video_url: "/video/new" },
    });
    expect(r.restoredVideoUrl).toBe("API/video/new?t=0");
    expect(r.restoredVideoMissing).toBe(false);
    expect(r.adjustedStep).toBe(10);
  });

  it("marks missing and rewinds to 6 (full-ai) when backend flags expired", () => {
    const r = computeVideoRestore({
      adjustedStep: 10,
      workflowMode: "full-ai",
      data: { video_url: "/video/old", video_storage_path: "u/p/video.mp4" },
      restoreData: { video_recovered: false, video_expired: true },
    });
    expect(r.restoredVideoUrl).toBeNull();
    expect(r.restoredVideoMissing).toBe(true);
    expect(r.adjustedStep).toBe(6);
  });

  it("marks missing and rewinds to 8 (hybrid) when backend flags expired", () => {
    const r = computeVideoRestore({
      adjustedStep: 10,
      workflowMode: "hybrid",
      data: { video_url: "/video/old", video_storage_path: "u/p/video.mp4" },
      restoreData: { video_recovered: false, video_expired: true },
    });
    expect(r.adjustedStep).toBe(8);
    expect(r.restoredVideoMissing).toBe(true);
  });

  it("rewinds even if backend hasn't flagged expired, when storage_path is missing at step 10", () => {
    // This is the cache-write race: DB has video_url but no storage_path.
    const r = computeVideoRestore({
      adjustedStep: 10,
      workflowMode: "full-ai",
      data: { video_url: "/video/old", video_storage_path: null },
      restoreData: { video_recovered: false, video_expired: false },
    });
    expect(r.restoredVideoUrl).toBeNull();
    expect(r.restoredVideoMissing).toBe(true);
    expect(r.adjustedStep).toBe(6);
  });

  it("stays at step 8 on hybrid and does not flag missing when not at step 10", () => {
    const r = computeVideoRestore({
      adjustedStep: 8,
      workflowMode: "hybrid",
      data: { video_url: null, video_storage_path: null },
      restoreData: { video_recovered: false, video_expired: false },
    });
    expect(r.adjustedStep).toBe(8);
    expect(r.restoredVideoMissing).toBe(false);
    expect(r.restoredVideoUrl).toBeNull();
  });

  it("never trusts stored video_url at step 10 when backend gives no positive signal", () => {
    // Defensive branch: even if backend returned neither recovered nor expired,
    // a step-10 project with no storage_path must not render the stored URL —
    // it points at a stale job_id.
    const r = computeVideoRestore({
      adjustedStep: 10,
      workflowMode: "full-ai",
      data: { video_url: "/video/stale", video_storage_path: null },
      restoreData: {},
    });
    expect(r.restoredVideoUrl).toBeNull();
    expect(r.restoredVideoMissing).toBe(true);
  });
});
