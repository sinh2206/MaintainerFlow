import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from demo_calculator import calculate_total  # noqa: E402


class CalculatorTest(unittest.TestCase):
    def test_total(self) -> None:
        self.assertEqual(calculate_total(3, 5), 15)

    def test_rejects_negative_input(self) -> None:
        with self.assertRaises(ValueError):
            calculate_total(-1, 5)


if __name__ == "__main__":
    unittest.main()
