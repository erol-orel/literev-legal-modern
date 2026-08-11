import DOMPurify from "dompurify";

/**
 * Sanitize server-rendered legal-document HTML before injecting it through
 * `dangerouslySetInnerHTML`.
 *
 * Although these fragments are rendered by same-origin Django, the corpus
 * itself includes decisions scraped from external sources (entscheidsuche),
 * so the HTML is not inherently trustworthy. This is defense-in-depth: we
 * strip `<script>`, event-handler attributes and `javascript:` URLs while
 * preserving the formatting a court document needs — headings, lists, tables,
 * `<mark>` highlights and links. The HTML profile keeps us to HTML (no SVG /
 * MathML vectors), and links are hardened with `rel="noopener noreferrer"`.
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target"],
    FORBID_TAGS: ["style", "form", "input", "button", "textarea", "select"],
    FORBID_ATTR: ["srcset", "action", "formaction"],
  });
}

// Harden any anchors the sanitizer keeps: open in a new tab without leaking the
// opener reference. Registered once at module load.
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A" && node.hasAttribute("href")) {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
});
