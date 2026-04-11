from __future__ import annotations

import json
import tempfile

from pathlib import Path

from django.test import SimpleTestCase, override_settings

from literev.templatetags.frontend import (
    frontend_bundle_available,
    frontend_static,
)


class FrontendTemplateTagTests(SimpleTestCase):
    def test_bundle_availability_is_false_when_manifest_is_missing(
        self,
    ) -> None:
        """Missing manifests should report an unavailable frontend bundle."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "asset-manifest.json"
            with override_settings(FRONTEND_ASSET_MANIFEST_PATH=manifest_path):
                self.assertFalse(frontend_bundle_available())

    def test_frontend_static_uses_manifest_files_mapping(self) -> None:
        """Template tags should resolve built assets from the manifest files map."""
        manifest_data = {
            "files": {
                "main.css": "/static/css/main.1234.css",
                "main.js": "/static/js/main.5678.js",
            }
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "asset-manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))

            with override_settings(FRONTEND_ASSET_MANIFEST_PATH=manifest_path):
                self.assertTrue(frontend_bundle_available())
                self.assertEqual(
                    frontend_static("main.css"), "/static/css/main.1234.css"
                )
                self.assertEqual(
                    frontend_static("main.js"), "/static/js/main.5678.js"
                )

    def test_frontend_static_falls_back_to_entrypoints_when_needed(
        self,
    ) -> None:
        """Template tags should still support entrypoint-only manifests."""
        manifest_data = {
            "entrypoints": [
                "static/css/main.entry.css",
                "static/js/main.entry.js",
            ]
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "asset-manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))

            with override_settings(FRONTEND_ASSET_MANIFEST_PATH=manifest_path):
                self.assertEqual(
                    frontend_static("main.css"), "/static/css/main.entry.css"
                )
                self.assertEqual(
                    frontend_static("main.js"), "/static/js/main.entry.js"
                )
