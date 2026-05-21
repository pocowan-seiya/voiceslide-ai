import fs from "fs";
import path from "path";

const PAGE_SOURCE = fs.readFileSync(
  path.join(__dirname, "..", "app", "page.tsx"),
  "utf-8"
);

describe("QA transcript fixture mode", () => {
  it("passes qaTranscriptFixture URL param to the transcribe API as qa_transcript_fixture", () => {
    expect(PAGE_SOURCE).toContain('searchParams.get("qaTranscriptFixture")');
    expect(PAGE_SOURCE).toContain('params.set("qa_transcript_fixture", qaTranscriptFixture)');
  });
});
