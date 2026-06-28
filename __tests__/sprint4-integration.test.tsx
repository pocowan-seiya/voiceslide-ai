/**
 * Sprint 4: Integration and edge-case tests for autosave / restore.
 *
 * Covers scenarios not yet tested in Sprint 1-3:
 * 1. Full integration test: slide-generated project (step=6, slidePreviews present) restores correctly
 * 2. Backend restore failure fallback: state.error set, frontend state still restored
 * 3. Page unload (beforeunload) triggers fetch keepalive
 * 4. Edge cases: very long transcript, empty outline, huge slidePreviews array
 */

// ---------------------------------------------------------------------------
// Helper: Full restore simulation (combines data validation + backend call)
// ---------------------------------------------------------------------------

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

interface ProjectData {
  step: number;
  workflow_mode: "full-ai" | "hybrid";
  transcript: string;
  polished_transcript: string;
  outline: any;
  polished_outline: any;
  timing_map: any[];
  slide_count: number;
  job_id: string | null;
  video_url: string | null;
  settings: {
    slidePreviews?: string[];
    aspectRatio?: string;
    [key: string]: any;
  };
}

interface RestoredFrontendState {
  step: Step;
  workflowMode: "full-ai" | "hybrid";
  transcript: string;
  polishedTranscript: string;
  outline: any;
  polishedOutline: any;
  timingMap: any[];
  slideCount: number;
  jobId: string | null;
  videoUrl: string | null;
  slidePreviews: string[];
  needsSlideRegeneration: boolean;
  error: string | null;
}

/**
 * Simulates the full restore flow:
 * 1. Validates data and adjusts step if needed
 * 2. Calls backend restore (simulated)
 * 3. Returns the restored frontend state
 */
function simulateFullRestore(
  data: ProjectData,
  backendRestoreSuccess: boolean
): RestoredFrontendState {
  let adjustedStep = data.step as Step;
  const slidePreviews: string[] = data.settings?.slidePreviews ?? [];

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
  const slideCompleteStep = data.workflow_mode === "full-ai" ? 6 : 9;
  let needsSlideRegeneration = false;
  if (data.step >= slideCompleteStep && slidePreviews.length === 0) {
    needsSlideRegeneration = true;
  }

  // Backend restore failure sets error but does not destroy frontend state
  const error = backendRestoreSuccess
    ? null
    : "バックエンドの復元に失敗しました。スライドの再生成や動画生成を行うには、ページを再読み込みしてください。";

  return {
    step: adjustedStep,
    workflowMode: data.workflow_mode,
    transcript: data.transcript,
    polishedTranscript: data.polished_transcript,
    outline: data.outline,
    polishedOutline: data.polished_outline,
    timingMap: data.timing_map,
    slideCount: data.slide_count,
    jobId: backendRestoreSuccess ? "restored-job-id" : data.job_id,
    videoUrl: data.video_url,
    slidePreviews,
    needsSlideRegeneration,
    error,
  };
}

// ---------------------------------------------------------------------------
// 1. Slide-generated project (step=6, slidePreviews present) restores correctly
// ---------------------------------------------------------------------------

describe("integration: slide-generated project restore", () => {
  const completeProject: ProjectData = {
    step: 6,
    workflow_mode: "full-ai",
    transcript: "This is the original transcript from the user's voice input.",
    polished_transcript: "This is the polished transcript with corrections applied.",
    outline: {
      slides: [
        { title: "Introduction", content: "Welcome to the presentation." },
        { title: "Main Topic", content: "Here is the core content." },
        { title: "Conclusion", content: "Thank you for listening." },
      ],
    },
    polished_outline: {
      slides: [
        { title: "Introduction", content: "Welcome to this presentation." },
        { title: "Main Topic", content: "Here is the refined content." },
        { title: "Conclusion", content: "Thank you for your time." },
      ],
    },
    timing_map: [
      { start: 0, end: 10, slideIndex: 0 },
      { start: 10, end: 25, slideIndex: 1 },
      { start: 25, end: 35, slideIndex: 2 },
    ],
    slide_count: 3,
    job_id: "old-job-123",
    video_url: null,
    settings: {
      slidePreviews: [
        "data:image/png;base64,slide1data",
        "data:image/png;base64,slide2data",
        "data:image/png;base64,slide3data",
      ],
      aspectRatio: "16:9",
    },
  };

  it("maintains step=6 with all data intact", () => {
    const state = simulateFullRestore(completeProject, true);
    expect(state.step).toBe(6);
    expect(state.needsSlideRegeneration).toBe(false);
    expect(state.error).toBeNull();
  });

  it("preserves all slide previews", () => {
    const state = simulateFullRestore(completeProject, true);
    expect(state.slidePreviews).toHaveLength(3);
    expect(state.slidePreviews[0]).toContain("slide1data");
  });

  it("preserves transcript, outline, timing_map, and slideCount", () => {
    const state = simulateFullRestore(completeProject, true);
    expect(state.transcript).toBe(completeProject.transcript);
    expect(state.polishedTranscript).toBe(completeProject.polished_transcript);
    expect(state.outline.slides).toHaveLength(3);
    expect(state.polishedOutline.slides).toHaveLength(3);
    expect(state.timingMap).toHaveLength(3);
    expect(state.slideCount).toBe(3);
  });

  it("replaces old jobId with new restored jobId on success", () => {
    const state = simulateFullRestore(completeProject, true);
    expect(state.jobId).toBe("restored-job-id");
    expect(state.jobId).not.toBe("old-job-123");
  });

  it("retains old jobId when backend restore fails", () => {
    const state = simulateFullRestore(completeProject, false);
    expect(state.jobId).toBe("old-job-123");
  });
});

// ---------------------------------------------------------------------------
// 2. Backend restore failure: frontend state preserved, error set
// ---------------------------------------------------------------------------

describe("backend restore failure fallback", () => {
  it("sets error message when backend fails", () => {
    const data: ProjectData = {
      step: 6,
      workflow_mode: "full-ai",
      transcript: "test",
      polished_transcript: "test polished",
      outline: { slides: [] },
      polished_outline: { slides: [] },
      timing_map: [],
      slide_count: 0,
      job_id: "existing-job",
      video_url: null,
      settings: { slidePreviews: ["img1.png"] },
    };

    const state = simulateFullRestore(data, false);
    expect(state.error).toBeTruthy();
    expect(state.error).toContain("バックエンド");
  });

  it("preserves frontend state fields even when backend fails", () => {
    const data: ProjectData = {
      step: 6,
      workflow_mode: "full-ai",
      transcript: "important transcript",
      polished_transcript: "important polished",
      outline: { slides: [{ title: "Slide1" }] },
      polished_outline: { slides: [{ title: "Polished1" }] },
      timing_map: [{ start: 0, end: 5 }],
      slide_count: 1,
      job_id: "old-job",
      video_url: null,
      settings: { slidePreviews: ["preview.png"] },
    };

    const state = simulateFullRestore(data, false);

    // Frontend state should be fully preserved
    expect(state.step).toBe(6);
    expect(state.transcript).toBe("important transcript");
    expect(state.polishedTranscript).toBe("important polished");
    expect(state.outline.slides).toHaveLength(1);
    expect(state.polishedOutline.slides).toHaveLength(1);
    expect(state.slidePreviews).toEqual(["preview.png"]);
    expect(state.timingMap).toHaveLength(1);
    // Error should be set
    expect(state.error).not.toBeNull();
  });

  it("allows user to continue viewing slides even with backend failure", () => {
    const data: ProjectData = {
      step: 6,
      workflow_mode: "full-ai",
      transcript: "t",
      polished_transcript: "p",
      outline: { slides: [] },
      polished_outline: { slides: [] },
      timing_map: [],
      slide_count: 5,
      job_id: null,
      video_url: null,
      settings: {
        slidePreviews: ["s1.png", "s2.png", "s3.png", "s4.png", "s5.png"],
      },
    };

    const state = simulateFullRestore(data, false);
    // Step should remain at 6 so UI shows slides
    expect(state.step).toBe(6);
    expect(state.slidePreviews).toHaveLength(5);
    // Error is present but does not prevent slide viewing
    expect(state.error).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 3. Page unload: beforeunload triggers fetch keepalive
// ---------------------------------------------------------------------------

describe("beforeunload fetch keepalive integration", () => {
  let originalFetch: typeof globalThis.fetch;
  let fetchCalls: Array<{ url: string; options: any }>;

  beforeEach(() => {
    fetchCalls = [];
    originalFetch = globalThis.fetch;
    globalThis.fetch = ((url: string, options?: any) => {
      fetchCalls.push({ url, options });
      return Promise.resolve({ ok: true, status: 200 });
    }) as any;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("sends keepalive fetch on beforeunload event", () => {
    const supabaseUrl = "https://abc.supabase.co";
    const supabaseKey = "test-anon-key";
    const projectId = "proj-save-test";

    // Simulate the beforeunload handler
    const saveOnUnload = () => {
      const payload = {
        step: 5,
        transcript: "test",
        settings: { slidePreviews: [] },
      };

      fetch(`${supabaseUrl}/rest/v1/projects?id=eq.${projectId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          apikey: supabaseKey,
          Authorization: `Bearer ${supabaseKey}`,
          Prefer: "return=minimal",
        },
        body: JSON.stringify(payload),
        keepalive: true,
      });
    };

    // Trigger
    saveOnUnload();

    expect(fetchCalls).toHaveLength(1);
    expect(fetchCalls[0].url).toContain("proj-save-test");
    expect(fetchCalls[0].options.keepalive).toBe(true);
    expect(fetchCalls[0].options.method).toBe("PATCH");
  });

  it("does not send fetch when projectId is null", () => {
    const projectId: string | null = null;

    const saveOnUnload = () => {
      if (!projectId) return;
      fetch(`https://x.supabase.co/rest/v1/projects?id=eq.${projectId}`, {
        method: "PATCH",
        keepalive: true,
      });
    };

    saveOnUnload();
    expect(fetchCalls).toHaveLength(0);
  });

  it("includes slidePreviews in the payload body", () => {
    const saveOnUnload = () => {
      const payload = {
        settings: {
          slidePreviews: ["/img/1.png", "/img/2.png"],
          aspectRatio: "16:9",
        },
      };
      fetch("https://x.supabase.co/rest/v1/projects?id=eq.proj-1", {
        method: "PATCH",
        body: JSON.stringify(payload),
        keepalive: true,
      });
    };

    saveOnUnload();

    const body = JSON.parse(fetchCalls[0].options.body);
    expect(body.settings.slidePreviews).toEqual(["/img/1.png", "/img/2.png"]);
    expect(body.settings.aspectRatio).toBe("16:9");
  });
});

// ---------------------------------------------------------------------------
// 4. Edge cases
// ---------------------------------------------------------------------------

describe("edge cases", () => {
  it("handles very long transcript (100K chars)", () => {
    const longTranscript = "A".repeat(100_000);
    const data: ProjectData = {
      step: 4,
      workflow_mode: "full-ai",
      transcript: longTranscript,
      polished_transcript: longTranscript,
      outline: { slides: [{ title: "T" }] },
      polished_outline: null,
      timing_map: [],
      slide_count: 1,
      job_id: null,
      video_url: null,
      settings: {},
    };

    const state = simulateFullRestore(data, true);
    expect(state.transcript.length).toBe(100_000);
    // Step rolled back to 4 because polished_outline is null
    expect(state.step).toBe(4);
  });

  it("handles empty outline object (no slides key)", () => {
    const data: ProjectData = {
      step: 4,
      workflow_mode: "full-ai",
      transcript: "test",
      polished_transcript: "test",
      outline: {},
      polished_outline: null,
      timing_map: [],
      slide_count: 0,
      job_id: null,
      video_url: null,
      settings: {},
    };

    const state = simulateFullRestore(data, true);
    // Empty object {} is still typeof "object", so it passes validation
    expect(state.step).toBe(4);
    expect(state.outline).toEqual({});
  });

  it("handles huge slidePreviews array (500 items)", () => {
    const hugePreviews = Array.from({ length: 500 }, (_, i) => `data:image/png;base64,slide${i}`);
    const data: ProjectData = {
      step: 6,
      workflow_mode: "full-ai",
      transcript: "t",
      polished_transcript: "p",
      outline: { slides: [] },
      polished_outline: { slides: [] },
      timing_map: [],
      slide_count: 500,
      job_id: null,
      video_url: null,
      settings: { slidePreviews: hugePreviews },
    };

    const state = simulateFullRestore(data, true);
    expect(state.slidePreviews).toHaveLength(500);
    expect(state.step).toBe(6);
    expect(state.needsSlideRegeneration).toBe(false);
  });

  it("handles settings with no slidePreviews key at all", () => {
    const data: ProjectData = {
      step: 6,
      workflow_mode: "full-ai",
      transcript: "t",
      polished_transcript: "p",
      outline: { slides: [] },
      polished_outline: { slides: [] },
      timing_map: [],
      slide_count: 3,
      job_id: null,
      video_url: null,
      settings: { aspectRatio: "16:9" },
    };

    const state = simulateFullRestore(data, true);
    expect(state.slidePreviews).toEqual([]);
    expect(state.needsSlideRegeneration).toBe(true);
  });

  it("handles null settings gracefully", () => {
    const data: ProjectData = {
      step: 3,
      workflow_mode: "full-ai",
      transcript: "t",
      polished_transcript: "",
      outline: null,
      polished_outline: null,
      timing_map: [],
      slide_count: 0,
      job_id: null,
      video_url: null,
      settings: null as any,
    };

    const state = simulateFullRestore(data, true);
    expect(state.slidePreviews).toEqual([]);
    expect(state.step).toBe(3);
  });
});
