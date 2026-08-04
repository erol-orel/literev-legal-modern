import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

/**
 * Emit a Create-React-App-compatible `asset-manifest.json` so the existing
 * Django template tag (`literev.templatetags.frontend.frontend_static`) keeps
 * working unchanged. Django reads `files["main.js"]` / `files["main.css"]` and
 * expects absolute `/static/...` paths.
 */
function craAssetManifest(): Plugin {
  return {
    name: "cra-asset-manifest",
    apply: "build",
    generateBundle(_options, bundle) {
      const files: Record<string, string> = {};
      const entrypoints: string[] = [];

      // Files are emitted under `static/` and `collectstatic` flattens
      // `build/static/*` into Django's static root (served at `/static/`), so
      // the public path strips the leading `static/` before re-prefixing it.
      const toPublic = (fileName: string) =>
        `/static/${fileName.replace(/^static\//, "")}`;

      for (const [fileName, chunk] of Object.entries(bundle)) {
        if (chunk.type === "chunk" && chunk.isEntry) {
          files["main.js"] = toPublic(fileName);
          entrypoints.push(toPublic(fileName));
          for (const css of chunk.viteMetadata?.importedCss ?? []) {
            files["main.css"] = toPublic(css);
            entrypoints.push(toPublic(css));
          }
        }
      }

      this.emitFile({
        type: "asset",
        fileName: "asset-manifest.json",
        source: JSON.stringify({ files, entrypoints }, null, 2),
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), craAssetManifest()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    // Django serves everything under this directory; assets live in `static/`
    // and the manifest at the root, mirroring the previous CRA layout.
    outDir: "build",
    emptyOutDir: true,
    assetsDir: "static",
    rollupOptions: {
      output: {
        entryFileNames: "static/js/main.[hash].js",
        chunkFileNames: "static/js/[name].[hash].js",
        assetFileNames: (assetInfo) => {
          const name = assetInfo.name ?? "";
          if (name.endsWith(".css")) {
            return "static/css/main.[hash][extname]";
          }
          return "static/media/[name].[hash][extname]";
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      // During `vite dev`, proxy backend calls to a locally running Django.
      "/api": "http://localhost:8000",
      "/accounts": "http://localhost:8000",
      "/status": "http://localhost:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    coverage: {
      provider: "v8",
      reportsDirectory: "coverage",
      reporter: ["text", "text-summary", "json-summary", "lcov"],
    },
  },
});
