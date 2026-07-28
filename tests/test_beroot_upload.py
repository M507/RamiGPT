"""Tests for BeRoot remote upload helpers."""

from __future__ import annotations

import unittest

from ramigpt.web.tools.beroot import (
    _BEROOT_PKG_MARKER,
    _bytes_tail,
    _parse_beroot_pkg_path,
    _upload_extract_failed_error,
)


class BeRootUploadHelperTests(unittest.TestCase):
    def test_bytes_tail_empty_buffer(self) -> None:
        self.assertEqual(_bytes_tail(b""), b"")
        self.assertEqual(_bytes_tail(None), b"")
        self.assertEqual(_bytes_tail(""), b"")

    def test_bytes_tail_returns_suffix(self) -> None:
        data = b"0123456789"
        self.assertEqual(_bytes_tail(data, 4), b"6789")

    def test_parse_beroot_pkg_path(self) -> None:
        output = b"noise\n__BEROOT_PKG__:/tmp/ramigpt-beroot-1001/pkg.abcd/Linux\n"
        self.assertEqual(
            _parse_beroot_pkg_path(output),
            "/tmp/ramigpt-beroot-1001/pkg.abcd/Linux",
        )
        self.assertIsNone(_parse_beroot_pkg_path(b"no marker here"))

    def test_upload_extract_failed_error_on_empty_tail(self) -> None:
        err = _upload_extract_failed_error(stage="python3 extract", buf=b"", check=b"")
        self.assertIn("python3 extract", str(err))
        self.assertIn("Tail:", str(err))


if __name__ == "__main__":
    unittest.main()
