import { describe, expect, it } from "vitest";

import { sanitizeHtml } from "@/lib/sanitize";

describe("sanitizeHtml", () => {
  it("strips <script> tags", () => {
    const out = sanitizeHtml('<p>Arrêt</p><script>alert(1)</script>');
    expect(out).toContain("<p>Arrêt</p>");
    expect(out).not.toContain("<script>");
    expect(out).not.toContain("alert(1)");
  });

  it("removes inline event handlers", () => {
    const out = sanitizeHtml('<img src="x" onerror="alert(1)">');
    expect(out).not.toContain("onerror");
    expect(out).not.toContain("alert(1)");
  });

  it("drops javascript: URLs", () => {
    const out = sanitizeHtml('<a href="javascript:alert(1)">x</a>');
    expect(out).not.toContain("javascript:");
  });

  it("preserves legal-document formatting and <mark> highlights", () => {
    const html =
      "<h2>Considérant</h2><p>Le <mark>bail</mark> est <strong>résilié</strong>.</p><ul><li>art. 271 CO</li></ul>";
    const out = sanitizeHtml(html);
    expect(out).toContain("<h2>Considérant</h2>");
    expect(out).toContain("<mark>bail</mark>");
    expect(out).toContain("<strong>résilié</strong>");
    expect(out).toContain("<li>art. 271 CO</li>");
  });

  it("hardens kept anchors with target and rel", () => {
    const out = sanitizeHtml('<a href="https://example.test/doc">source</a>');
    expect(out).toContain('href="https://example.test/doc"');
    expect(out).toContain('target="_blank"');
    expect(out).toContain('rel="noopener noreferrer"');
  });
});
