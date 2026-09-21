"""Family-name ear: Christman is not Crispin."""
import unittest

from family_ear import FILAMENT_FAMILY_PROMPT, correct_family_names


class FamilyEarTests(unittest.TestCase):
    def test_crispin_becomes_christman(self):
        self.assertEqual(
            correct_family_names("The Crispin Full Sensory Bridge"),
            "The Christman Full Sensory Bridge",
        )

    def test_lowercase_crispin(self):
        self.assertEqual(
            correct_family_names("crispin is how it's spelled"),
            "Christman is how it's spelled",
        )

    def test_christmas_is_left_alone(self):
        self.assertEqual(
            correct_family_names("Merry Christmas from the house"),
            "Merry Christmas from the house",
        )

    def test_chris_man(self):
        self.assertEqual(
            correct_family_names("Everett Chris man speaking"),
            "Everett Christman speaking",
        )

    def test_already_correct(self):
        self.assertEqual(
            correct_family_names("The Christman AI Project"),
            "The Christman AI Project",
        )

    def test_empty(self):
        self.assertEqual(correct_family_names(""), "")
        self.assertEqual(correct_family_names(None), None)

    def test_prompt_says_christman(self):
        self.assertIn("Christman", FILAMENT_FAMILY_PROMPT)
        self.assertNotIn("Crispin", FILAMENT_FAMILY_PROMPT)


if __name__ == "__main__":
    unittest.main()
