"""Regression coverage for the Chromium Android engineering signature gate."""

import unittest

from tools.check_apk_signer import EXPECTED_SIGNER, report_matches


V2_CHECK = "Verified using v2 scheme (APK Signature Scheme v2): true"
V2_CERT = f"V2 Signer: certificate SHA-256 digest: {EXPECTED_SIGNER}"
BUILD_TOOLS_37 = f"""Verifies
Verified using v1 scheme (JAR signing): false
{V2_CHECK}
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v3.2 scheme (APK Signature Scheme v3.2): false
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
V2 Signer: certificate DN: CN=Unknown, OU=Unknown, O=Unknown, L=Unknown, ST=Unknown, C=Unknown
{V2_CERT}
V2 Signer: public key SHA-256 digest: ee681e69c7453cde30ce6b1306b002bd1b7fe288c5878a550fc90ed23c2971f2
"""


class SignerReportTests(unittest.TestCase):
    def test_build_tools_37_transcript(self):
        self.assertTrue(report_matches(BUILD_TOOLS_37))

    def test_numbered_report_and_normalization(self):
        grouped = ":".join(EXPECTED_SIGNER[i:i + 2].upper() for i in range(0, 64, 2))
        self.assertTrue(report_matches(
            f"Verifies\r\nNumber of signers: 1\r\nSigner #1 certificate SHA-256 digest: {grouped}\r\n"
        ))

    def test_fails_closed_for_invalid_or_ambiguous_reports(self):
        for modified in (
            BUILD_TOOLS_37.replace(EXPECTED_SIGNER, "0" * 64),
            BUILD_TOOLS_37.replace(EXPECTED_SIGNER, EXPECTED_SIGNER + "a"),
            BUILD_TOOLS_37.replace(V2_CERT, V2_CERT.replace("certificate", "public key")),
            BUILD_TOOLS_37.replace(V2_CERT, V2_CERT.replace("V2 Signer:", "SourceStamp Signer:")),
            BUILD_TOOLS_37.replace(V2_CERT, V2_CERT.replace("V2 Signer:", "Signer #2")),
            BUILD_TOOLS_37.replace(V2_CHECK, V2_CHECK.replace("true", "false")),
            BUILD_TOOLS_37.replace("Number of signers: 1", "Number of signers: 2"),
            BUILD_TOOLS_37.replace("Number of signers: 1", ""),
            BUILD_TOOLS_37 + "Number of signers: 2\n",
            BUILD_TOOLS_37 + V2_CERT + "\n",
            BUILD_TOOLS_37 + V2_CERT.replace("V2 Signer:", "V3 Signer:") + "\n",
        ):
            with self.subTest(report=modified):
                self.assertFalse(report_matches(modified))
