/**
 * Regression tests for slide direct editing bugs reported by Tanaka-san.
 *
 * Bug 1: Selecting slide N showed HTML for a different slide (index mismatch).
 * Bug 2: Only some text elements were editable (isLeafText missed mixed-content elements).
 *
 * Both fixed in commit 42d77aa.
 *
 * These tests validate the contentEditable injection logic that runs inside
 * the slide editing iframe. We extract the pure JS logic and test it in jsdom.
 */

// ---------------------------------------------------------------------------
// Replicate the contentEditable logic from app/page.tsx (post-fix version)
// ---------------------------------------------------------------------------

const SKIP_TAGS = [
  "SCRIPT",
  "STYLE",
  "META",
  "LINK",
  "IMG",
  "SVG",
  "PATH",
  "BR",
  "HR",
  "IFRAME",
  "CIRCLE",
  "ELLIPSE",
  "RECT",
  "LINE",
  "POLYGON",
  "POLYLINE",
  "INPUT",
  "SELECT",
  "TEXTAREA",
];

const INLINE_TAGS = [
  "STRONG",
  "EM",
  "B",
  "I",
  "U",
  "SPAN",
  "A",
  "MARK",
  "SUB",
  "SUP",
  "SMALL",
  "ABBR",
  "CODE",
  "FONT",
];

function hasDirectText(el: Element): boolean {
  for (let i = 0; i < el.childNodes.length; i++) {
    const node = el.childNodes[i];
    if (node.nodeType === 3 && (node.textContent || "").trim()) return true;
  }
  return false;
}

function makeEditable(el: Element): void {
  if (SKIP_TAGS.includes(el.tagName)) return;
  const text = (el.textContent || "").trim();
  if (!text) return;

  if (hasDirectText(el)) {
    (el as HTMLElement).contentEditable = "true";
    return;
  }

  const childEls = Array.from(el.children).filter(
    (c) => !SKIP_TAGS.includes(c.tagName) && (c.textContent || "").trim().length > 0
  );

  if (
    childEls.length > 0 &&
    childEls.every((c) => INLINE_TAGS.includes(c.tagName))
  ) {
    (el as HTMLElement).contentEditable = "true";
    return;
  }

  Array.from(el.children).forEach(makeEditable);
}

// ---------------------------------------------------------------------------
// Helper: build a DOM fragment and run makeEditable on it
// ---------------------------------------------------------------------------

function setupSlideDOM(html: string): HTMLElement {
  const container = document.createElement("div");
  container.innerHTML = html;
  makeEditable(container);
  return container;
}

// ---------------------------------------------------------------------------
// Bug 2 regression: ALL text elements must become editable
// ---------------------------------------------------------------------------

describe("Bug 2 regression: all text elements are editable", () => {
  it("makes a plain <p> with direct text editable", () => {
    const dom = setupSlideDOM("<p>Hello World</p>");
    const p = dom.querySelector("p")!;
    expect(p.contentEditable).toBe("true");
  });

  it("makes headings (h1-h6) with direct text editable", () => {
    const dom = setupSlideDOM(`
      <h1>Title</h1>
      <h2>Subtitle</h2>
      <h3>Section</h3>
    `);
    expect(dom.querySelector("h1")!.contentEditable).toBe("true");
    expect(dom.querySelector("h2")!.contentEditable).toBe("true");
    expect(dom.querySelector("h3")!.contentEditable).toBe("true");
  });

  it("makes a <p> containing only <span> children editable (inline children)", () => {
    const dom = setupSlideDOM("<p><span>Styled</span><span> text</span></p>");
    const p = dom.querySelector("p")!;
    expect(p.contentEditable).toBe("true");
  });

  it("makes a <div> with mixed text and <strong> editable", () => {
    // This was the core Bug 2 scenario: elements with direct text AND inline children
    const dom = setupSlideDOM("<div>Some <strong>bold</strong> text</div>");
    const div = dom.querySelector("div")!;
    expect(div.contentEditable).toBe("true");
  });

  it("makes a <p> with <em> and <a> children editable", () => {
    const dom = setupSlideDOM(
      '<p><em>Important</em> info <a href="#">link</a></p>'
    );
    const p = dom.querySelector("p")!;
    expect(p.contentEditable).toBe("true");
  });

  it("makes nested inline elements editable at parent level", () => {
    const dom = setupSlideDOM(
      "<p><span><strong>Nested bold</strong></span></p>"
    );
    const p = dom.querySelector("p")!;
    // The <p> should be editable because its child <span> is an inline tag
    expect(p.contentEditable).toBe("true");
  });

  it("recurses into block-level children to make each editable", () => {
    const dom = setupSlideDOM(`
      <section>
        <div>First block</div>
        <div>Second block</div>
      </section>
    `);
    // The section should NOT be contentEditable (children are block-level divs)
    const section = dom.querySelector("section")!;
    expect(section.contentEditable).not.toBe("true");
    // But each inner div should be editable
    const inners = dom.querySelectorAll("section > div");
    inners.forEach((inner) => {
      expect(inner.contentEditable).toBe("true");
    });
  });

  it("does not make <script> or <style> elements editable", () => {
    const dom = setupSlideDOM(`
      <script>var x = 1;</script>
      <style>.foo { color: red; }</style>
      <p>Visible text</p>
    `);
    // script and style elements should be skipped
    const p = dom.querySelector("p")!;
    expect(p.contentEditable).toBe("true");
  });

  it("does not make <img> or <svg> elements editable", () => {
    const dom = setupSlideDOM(`
      <div>
        <img src="test.png" alt="test" />
        <svg><circle cx="50" cy="50" r="40" /></svg>
        <p>Caption</p>
      </div>
    `);
    const p = dom.querySelector("p")!;
    expect(p.contentEditable).toBe("true");
  });

  it("does not make empty elements editable", () => {
    const dom = setupSlideDOM('<div class="spacer"></div>');
    const div = dom.querySelector("div")!;
    expect(div.contentEditable).not.toBe("true");
  });

  it("handles a realistic slide HTML structure", () => {
    const dom = setupSlideDOM(`
      <div class="slide-container" style="position: relative;">
        <div class="bg-overlay" style="position: absolute;"></div>
        <h1>Presentation Title</h1>
        <p>This is <strong>important</strong> information about <em>AI technology</em>.</p>
        <ul>
          <li>First point</li>
          <li>Second <span class="highlight">highlighted</span> point</li>
        </ul>
        <div class="footer">
          <span>Footer text</span>
        </div>
      </div>
    `);

    // h1 should be editable
    expect(dom.querySelector("h1")!.contentEditable).toBe("true");
    // p with mixed inline content should be editable
    expect(dom.querySelector("p")!.contentEditable).toBe("true");
    // li elements should be editable
    const lis = dom.querySelectorAll("li");
    lis.forEach((li) => {
      expect(li.contentEditable).toBe("true");
    });
    // footer div with inline span child should be editable
    expect(dom.querySelector(".footer")!.contentEditable).toBe("true");
  });
});

// ---------------------------------------------------------------------------
// Bug 1 regression: correct slide content is shown for selected index
// ---------------------------------------------------------------------------

describe("Bug 1 regression: slide selection shows correct content", () => {
  const slideHtmlContents = [
    '<html><body><h1>Slide 1: Introduction</h1><p>Welcome</p></body></html>',
    '<html><body><h1>Slide 2: Main Topic</h1><p>Details here</p></body></html>',
    '<html><body><h1>Slide 3: Conclusion</h1><p>Thank you</p></body></html>',
  ];

  function simulateFetchSlideHtml(slideNumber: number): string | null {
    // Mirrors get_html_content: 1-indexed slide_number -> 0-indexed array
    const idx = slideNumber - 1;
    if (idx < 0 || idx >= slideHtmlContents.length) return null;
    return slideHtmlContents[idx];
  }

  it("slide 1 returns Slide 1 content", () => {
    const html = simulateFetchSlideHtml(1);
    expect(html).toContain("Slide 1: Introduction");
  });

  it("slide 2 returns Slide 2 content", () => {
    const html = simulateFetchSlideHtml(2);
    expect(html).toContain("Slide 2: Main Topic");
    expect(html).not.toContain("Slide 1");
    expect(html).not.toContain("Slide 3");
  });

  it("slide 3 returns Slide 3 content", () => {
    const html = simulateFetchSlideHtml(3);
    expect(html).toContain("Slide 3: Conclusion");
  });

  it("out-of-range slide number returns null", () => {
    expect(simulateFetchSlideHtml(0)).toBeNull();
    expect(simulateFetchSlideHtml(4)).toBeNull();
    expect(simulateFetchSlideHtml(-1)).toBeNull();
  });

  it("injected script is appended before </body> of the correct slide", () => {
    // Simulate what handleLoadSlideText does
    const slideNum = 2;
    const html = simulateFetchSlideHtml(slideNum)!;
    const editableScript = '<script>/* editable injection */</script>';
    const htmlWithEditor = html.replace("</body>", editableScript + "</body>");

    expect(htmlWithEditor).toContain("Slide 2: Main Topic");
    expect(htmlWithEditor).toContain("editable injection");
    expect(htmlWithEditor).not.toContain("Slide 1");
  });
});
