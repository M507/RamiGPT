"""Tests for static leaderboard HTML + tall PNG export."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ramigpt.benchmark.leaderboard_export import (
    README_LEADERBOARD_IMAGE_MD,
    ensure_readme_leaderboard_image,
    format_leaderboard_export_html,
    write_leaderboard_exports,
)
from ramigpt.benchmark.master_results import (
    README_BENCHMARK_END,
    README_BENCHMARK_HEADING,
    README_BENCHMARK_START,
    build_master_document,
)
from tests.test_benchmark_master_results import _sample_run_doc


class LeaderboardExportTests(unittest.TestCase):
    def test_html_export_contains_rankings_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run_a"
            run_dir.mkdir()
            doc = _sample_run_doc(run_id="export-a", status="passed", elapsed=12.0)
            doc["model_key_name"] = "openwebui-openai-gpt-4o-latest"
            doc["profile_label"] = "openwebui-openai-gpt-4o-latest · Online AI Service"
            (run_dir / "result.json").write_text(
                __import__("json").dumps(doc), encoding="utf-8"
            )
            master = build_master_document(root)
            html = format_leaderboard_export_html(master)
            self.assertIn("Model Leaderboard", html)
            self.assertIn("Top 6 table", html)
            self.assertIn("Resolved (got root)", html)
            self.assertIn("Success rate", html)
            self.assertIn("Methodology", html)
            self.assertIn("max_requests", html)
            self.assertIn("openwebui-openai-gpt-4o-latest", html)
            self.assertIn('class="lb-card lb-card-wide"', html)

    def test_png_export_is_tall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run_b"
            run_dir.mkdir()
            doc = _sample_run_doc(run_id="export-b", status="passed", elapsed=9.0)
            (run_dir / "result.json").write_text(
                __import__("json").dumps(doc), encoding="utf-8"
            )
            master = build_master_document(root)
            png_path = root / "out.png"
            paths = write_leaderboard_exports(
                master, results_dir=root, image_path=png_path
            )
            self.assertTrue(paths["html"].is_file())
            self.assertTrue(paths["png"].is_file())
            self.assertGreater(paths["png"].stat().st_size, 5_000)
            from PIL import Image

            with Image.open(paths["png"]) as im:
                self.assertGreater(im.height, im.width)
                self.assertGreaterEqual(im.width, 900)

    def test_readme_image_inserted_before_project_layout(self):
        readme = (
            "# RamiGPT\n\n"
            "Intro text.\n\n"
            "---\n\n"
            f"{README_BENCHMARK_HEADING}\n\n"
            f"{README_BENCHMARK_START}\nstats\n{README_BENCHMARK_END}\n\n"
            "## Web workspace\n\n"
            "stuff\n\n"
            "## Project layout\n\n"
            "layout here\n"
        )
        updated, changed = ensure_readme_leaderboard_image(readme)
        self.assertTrue(changed)
        self.assertIn(README_LEADERBOARD_IMAGE_MD, updated)
        layout_at = updated.index("## Project layout")
        image_at = updated.index(README_LEADERBOARD_IMAGE_MD)
        collab_at = updated.index(README_BENCHMARK_HEADING)
        self.assertLess(collab_at, image_at)
        self.assertLess(image_at, layout_at)
        # Idempotent
        again, changed2 = ensure_readme_leaderboard_image(updated)
        self.assertFalse(changed2)
        self.assertEqual(again.count("benchmark_leaderboard.png"), 1)


if __name__ == "__main__":
    unittest.main()
