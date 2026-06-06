"""Tests for human-readable display name validation and slug generation."""

import unittest

from app.utils.display_validation import (
    DISPLAY_NAME_ALLOWED_MESSAGE,
    ensure_unique_slug,
    generate_slug,
    normalize_display_name,
    validate_display_name,
)


class DisplayNameValidationTests(unittest.TestCase):
    def test_accepts_spaces_and_punctuation(self):
        samples = [
            "Health & Welfare (Phase 2)",
            "District-Level Data 2024",
            "Telecom_Utility / North",
            "Report v1.2 (Draft)",
        ]
        for sample in samples:
            with self.subTest(name=sample):
                result = validate_display_name(sample, field_label="Name")
                self.assertEqual(result, normalize_display_name(sample))

    def test_rejects_machine_code_only_requirements(self):
        with self.assertRaises(Exception) as ctx:
            validate_display_name("Bad@Name", field_label="Source name")
        detail = getattr(ctx.exception, "detail", str(ctx.exception))
        self.assertIn("Source name", str(detail))

    def test_rejects_empty_name(self):
        with self.assertRaises(Exception) as ctx:
            validate_display_name("   ", field_label="Template name")
        detail = getattr(ctx.exception, "detail", str(ctx.exception))
        self.assertIn("required", str(detail).lower())

    def test_rejects_overly_long_name(self):
        with self.assertRaises(Exception) as ctx:
            validate_display_name("x" * 256, field_label="Name")
        detail = getattr(ctx.exception, "detail", str(ctx.exception))
        self.assertIn("255", str(detail))

    def test_normalize_collapses_whitespace(self):
        self.assertEqual(normalize_display_name("  Health   Dept  "), "Health Dept")


class SlugGenerationTests(unittest.TestCase):
    def test_generates_slug_from_display_name(self):
        self.assertEqual(
            generate_slug("Health & Welfare (Phase 2)"),
            "health-welfare-phase-2",
        )

    def test_generates_slug_with_slashes_and_underscores(self):
        self.assertEqual(
            generate_slug("Telecom_Utility / North"),
            "telecom-utility-north",
        )

    def test_ensure_unique_slug_appends_suffix(self):
        taken = {"health-welfare"}

        def is_taken(candidate: str) -> bool:
            return candidate in taken

        result = ensure_unique_slug("health-welfare", is_taken)
        self.assertEqual(result, "health-welfare-2")

    def test_allowed_message_is_user_friendly(self):
        self.assertIn("letters", DISPLAY_NAME_ALLOWED_MESSAGE.lower())
        self.assertIn("&", DISPLAY_NAME_ALLOWED_MESSAGE)


class NormalizationServiceTextTests(unittest.TestCase):
    def test_citizen_name_keeps_ampersand_and_parentheses(self):
        from app.services.normalization_service import normalize_name

        result = normalize_name("Health & Welfare (North)")
        self.assertIn("&", result)
        self.assertIn("(", result)
        self.assertIn(")", result)
        self.assertNotIn("@", result)


if __name__ == "__main__":
    unittest.main()
