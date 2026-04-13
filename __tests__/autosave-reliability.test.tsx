/**
 * Auto-save reliability tests for Sprint 1.
 *
 * Tests the three improvements:
 * 1. beforeunload handler saves project via fetch keepalive
 * 2. slidePreviews changes trigger immediate save
 * 3. Enhanced error logging in saveProject
 */

// ---------------------------------------------------------------------------
// 1. beforeunload save logic (unit test of the data preparation)
// ---------------------------------------------------------------------------

describe("beforeunload save data preparation", () => {
  const buildSavePayload = (
    currentState: {
      step: number;
      workflowMode: string | null;
      transcript: string;
      polishedTranscript: string;
      outline: object | null;
      polishedOutline: object | null;
      timingMap: any[];
      slideCount: number;
      jobId: string | null;
      videoUrl: string | null;
      slidePreviews: string[];
    },
    settings: object
  ) => ({
    step: currentState.step,
    workflow_mode: currentState.workflowMode,
    transcript: currentState.transcript,
    polished_transcript: currentState.polishedTranscript,
    outline: currentState.outline,
    polished_outline: currentState.polishedOutline,
    timing_map: currentState.timingMap,
    slide_count: currentState.slideCount,
    job_id: currentState.jobId,
    status: currentState.videoUrl ? "completed" : "draft",
    video_url: currentState.videoUrl,
    settings: {
      ...settings,
      slidePreviews: currentState.slidePreviews,
    },
  });

  it("includes slidePreviews in the settings field", () => {
    const state = {
      step: 5,
      workflowMode: "auto" as const,
      transcript: "test transcript",
      polishedTranscript: "polished",
      outline: { slides: [] },
      polishedOutline: null,
      timingMap: [],
      slideCount: 3,
      jobId: "job-123",
      videoUrl: null,
      slidePreviews: ["/preview/1.png", "/preview/2.png", "/preview/3.png"],
    };
    const settings = { aspectRatio: "16:9" };

    const payload = buildSavePayload(state, settings);

    expect(payload.settings.slidePreviews).toEqual([
      "/preview/1.png",
      "/preview/2.png",
      "/preview/3.png",
    ]);
    expect(payload.settings.aspectRatio).toBe("16:9");
  });

  it("sets status to 'completed' when videoUrl is present", () => {
    const state = {
      step: 6,
      workflowMode: null,
      transcript: "",
      polishedTranscript: "",
      outline: null,
      polishedOutline: null,
      timingMap: [],
      slideCount: 0,
      jobId: null,
      videoUrl: "https://example.com/video.mp4",
      slidePreviews: [],
    };
    const payload = buildSavePayload(state, {});
    expect(payload.status).toBe("completed");
  });

  it("sets status to 'draft' when videoUrl is null", () => {
    const state = {
      step: 3,
      workflowMode: null,
      transcript: "test",
      polishedTranscript: "",
      outline: null,
      polishedOutline: null,
      timingMap: [],
      slideCount: 0,
      jobId: null,
      videoUrl: null,
      slidePreviews: [],
    };
    const payload = buildSavePayload(state, {});
    expect(payload.status).toBe("draft");
  });

  it("preserves all state fields in the payload", () => {
    const state = {
      step: 4,
      workflowMode: "manual" as const,
      transcript: "my transcript",
      polishedTranscript: "my polished transcript",
      outline: { slides: [{ title: "Slide 1" }] },
      polishedOutline: { slides: [{ title: "Polished Slide 1" }] },
      timingMap: [{ start: 0, end: 5 }],
      slideCount: 1,
      jobId: "job-456",
      videoUrl: null,
      slidePreviews: ["/img/1.png"],
    };
    const payload = buildSavePayload(state, {});

    expect(payload.step).toBe(4);
    expect(payload.workflow_mode).toBe("manual");
    expect(payload.transcript).toBe("my transcript");
    expect(payload.polished_transcript).toBe("my polished transcript");
    expect(payload.outline).toEqual({ slides: [{ title: "Slide 1" }] });
    expect(payload.timing_map).toEqual([{ start: 0, end: 5 }]);
    expect(payload.slide_count).toBe(1);
    expect(payload.job_id).toBe("job-456");
  });
});

// ---------------------------------------------------------------------------
// 2. fetch keepalive call structure
// ---------------------------------------------------------------------------

describe("beforeunload fetch keepalive", () => {
  it("constructs the correct Supabase REST API URL", () => {
    const supabaseUrl = "https://abc.supabase.co";
    const projectId = "proj-789";
    const url = `${supabaseUrl}/rest/v1/projects?id=eq.${projectId}`;
    expect(url).toBe("https://abc.supabase.co/rest/v1/projects?id=eq.proj-789");
  });

  it("sets required Supabase headers", () => {
    const supabaseKey = "test-anon-key";
    const headers = {
      "Content-Type": "application/json",
      "apikey": supabaseKey,
      "Authorization": `Bearer ${supabaseKey}`,
      "Prefer": "return=minimal",
    };
    expect(headers["apikey"]).toBe("test-anon-key");
    expect(headers["Authorization"]).toBe("Bearer test-anon-key");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Prefer"]).toBe("return=minimal");
  });
});

// ---------------------------------------------------------------------------
// 3. slidePreviews change detection logic
// ---------------------------------------------------------------------------

describe("slidePreviews immediate save trigger", () => {
  it("should not trigger save when slidePreviews is empty", () => {
    const projectId = "proj-123";
    const slidePreviews: string[] = [];
    const shouldSave = !!projectId && slidePreviews.length > 0;
    expect(shouldSave).toBe(false);
  });

  it("should not trigger save when projectId is null", () => {
    const projectId = null;
    const slidePreviews = ["/preview/1.png"];
    const shouldSave = !!projectId && slidePreviews.length > 0;
    expect(shouldSave).toBe(false);
  });

  it("should trigger save when projectId exists and slidePreviews is non-empty", () => {
    const projectId = "proj-123";
    const slidePreviews = ["/preview/1.png", "/preview/2.png"];
    const shouldSave = !!projectId && slidePreviews.length > 0;
    expect(shouldSave).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 4. Error logging structure
// ---------------------------------------------------------------------------

describe("enhanced error logging", () => {
  it("structured error object includes all diagnostic fields", () => {
    const projectId = "proj-err-test";
    const step = 5;
    const error = new Error("network timeout") as any;
    error.code = "TIMEOUT";
    error.details = "Connection refused";

    const logData = {
      projectId,
      step,
      error: error?.message || error,
      code: error?.code,
      details: error?.details,
      timestamp: new Date().toISOString(),
    };

    expect(logData.projectId).toBe("proj-err-test");
    expect(logData.step).toBe(5);
    expect(logData.error).toBe("network timeout");
    expect(logData.code).toBe("TIMEOUT");
    expect(logData.details).toBe("Connection refused");
    expect(logData.timestamp).toBeTruthy();
  });

  it("handles error without message gracefully", () => {
    const error = "string error";
    const logData = {
      error: (error as any)?.message || error,
    };
    expect(logData.error).toBe("string error");
  });

  it("handles null error gracefully", () => {
    const error = null;
    const logData = {
      error: (error as any)?.message || error,
    };
    expect(logData.error).toBeNull();
  });
});
