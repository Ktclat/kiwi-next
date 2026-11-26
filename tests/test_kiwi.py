import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import kiwi


class BootstrapTests(unittest.TestCase):
    def test_pinned_official_sources(self):
        sources = kiwi.read_lock()
        self.assertLess(int(sources[0]["version"].split(".")[0]), int(sources[1]["version"].split(".")[0]))

    def test_blob_verification_rejects_tampered_bytes(self):
        payload = b"MAJOR=123\nMINOR=0\nBUILD=456\nPATCH=7\n"
        sha, commit = kiwi.blob_sha(payload), "a" * 40
        spec = [{"role": "candidate", "repo": "chromium/chromium", "tag": "123.0.456.7",
                 "commit": commit, "version": "123.0.456.7", "blobs": {"chrome/VERSION": sha}}]
        def mock(content):
            return lambda url: ({"object": {"type": "commit", "sha": commit}} if "/git/ref/" in url else
                               {"type": "file", "encoding": "base64", "sha": sha,
                                "content": base64.b64encode(content).decode()})
        kiwi.verify_remote(spec, mock(payload))
        with self.assertRaisesRegex(ValueError, "Source differs"):
            kiwi.verify_remote(spec, mock(payload + b" "))
        with self.assertRaisesRegex(ValueError, "no longer"):
            kiwi.verify_remote(spec, lambda _: {"object": {"type": "commit", "sha": "b" * 40}})

    def test_dev_profiles_use_distinct_id_and_no_sandbox_overrides(self):
        for arch in kiwi.PROFILES:
            text = kiwi.gn_text(arch)
            self.assertIn(f'target_cpu = "{arch}"', text)
            self.assertIn('is_desktop_android = true', text)
            self.assertIn('chrome_public_manifest_package = "io.github.ktclat.kiwinext.dev"', text)
            self.assertNotIn('com.kiwibrowser.browser', text)
            for dangerous in ('disable_sandbox', 'ignore_certificate', 'remote_debugging', 'disable_safe_browsing'):
                self.assertNotIn(dangerous, text.lower())

    def test_prepare_is_pinned_and_does_not_replace_existing_args(self):
        candidate = kiwi.read_lock()[1]
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            (src / ".git").mkdir()
            (src / "chrome").mkdir()
            keys = ("MAJOR", "MINOR", "BUILD", "PATCH")
            (src / "chrome" / "VERSION").write_text("\n".join(
                f"{key}={val}" for key, val in zip(keys, candidate["version"].split("."))))
            cfg = src / "out" / kiwi.PROFILES["x64"] / "args.gn"
            with patch.object(kiwi, "check_capacity"), patch.object(kiwi.subprocess, "check_output",
                    side_effect=["b" * 40]):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    kiwi.prepare(src, "x64", candidate)
            with patch.object(kiwi, "check_capacity"), patch.object(kiwi.subprocess, "check_output",
                    side_effect=[candidate["commit"], "", candidate["commit"], ""]):
                kiwi.prepare(src, "x64", candidate)
                self.assertEqual(cfg.read_text(), kiwi.gn_text("x64"))
                cfg.write_text("# user configuration\n")
                with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                    kiwi.prepare(src, "x64", candidate)
                self.assertEqual(cfg.read_text(), "# user configuration\n")

    def test_fixture_cannot_request_general_host_access(self):
        root = kiwi.ROOT / "fixtures"
        manifest = json.loads((root / "mv3-localhost" / "manifest.json").read_text())
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["content_scripts"][0]["matches"], ["http://127.0.0.1/*"])
        self.assertNotIn("permissions", manifest)
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("background", manifest)
        self.assertIn("kiwi-fixture-result", (root / "fixture.html").read_text())

if __name__ == "__main__":
    unittest.main()
