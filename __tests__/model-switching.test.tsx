/**
 * VoiceSlide AI - Model switching regression tests (frontend).
 * Sprint 3: Ensures getAPIHeaders returns correct headers and
 * handlePolishOutline includes them in requests.
 *
 * Uses source code analysis (string matching) to verify without
 * needing to render the full page component.
 */

import * as fs from "fs";
import * as path from "path";

const PAGE_SOURCE = fs.readFileSync(
  path.join(__dirname, "..", "app", "page.tsx"),
  "utf-8"
);

describe("getAPIHeaders", () => {
  it("is defined in page.tsx", () => {
    expect(PAGE_SOURCE).toContain("function getAPIHeaders()");
  });

  it("returns x-openrouter-key header", () => {
    expect(PAGE_SOURCE).toContain('"x-openrouter-key"');
  });

  it("returns x-openrouter-model header", () => {
    expect(PAGE_SOURCE).toContain('"x-openrouter-model"');
  });

  it("returns x-openrouter-design-model header", () => {
    expect(PAGE_SOURCE).toContain('"x-openrouter-design-model"');
  });

  it("returns x-gemini-key header", () => {
    expect(PAGE_SOURCE).toContain('"x-gemini-key"');
  });

  it("returns x-gemini-model header", () => {
    expect(PAGE_SOURCE).toContain('"x-gemini-model"');
  });
});

describe("handlePolishOutline", () => {
  it("is defined in page.tsx", () => {
    expect(PAGE_SOURCE).toContain("handlePolishOutline");
  });

  it("includes getAPIHeaders() in its fetch call", () => {
    // Extract the handlePolishOutline function area
    const startIdx = PAGE_SOURCE.indexOf("const handlePolishOutline");
    expect(startIdx).toBeGreaterThan(-1);

    // Look at the next ~500 chars to find the fetch call with headers
    const functionArea = PAGE_SOURCE.substring(startIdx, startIdx + 800);

    // Should contain ...getAPIHeaders() in headers
    expect(functionArea).toContain("getAPIHeaders()");
  });

  it("sends Content-Type header alongside API headers", () => {
    const startIdx = PAGE_SOURCE.indexOf("const handlePolishOutline");
    const functionArea = PAGE_SOURCE.substring(startIdx, startIdx + 800);

    expect(functionArea).toContain("Content-Type");
    expect(functionArea).toContain("getAPIHeaders()");
  });
});
