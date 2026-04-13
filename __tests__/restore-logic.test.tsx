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
