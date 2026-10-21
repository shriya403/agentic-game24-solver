import unittest

from game24.validator import validate_expression


class ValidatorTests(unittest.TestCase):
    def test_valid_expression(self):
        self.assertTrue(validate_expression("(7-8/8)*4", (4, 7, 8, 8)).valid)

    def test_rejects_number_reuse(self):
        result = validate_expression("8*3+3-3", (3, 3, 8, 8))
        self.assertFalse(result.valid)
        self.assertIn("mismatch", result.message.lower())

    def test_rejects_python_code(self):
        result = validate_expression("__import__('os').system('echo unsafe')", (1, 2, 3, 4))
        self.assertFalse(result.valid)

    def test_rejects_wrong_value(self):
        result = validate_expression("3+3+8+8", (3, 3, 8, 8))
        self.assertFalse(result.valid)
        self.assertIn("not 24", result.message)


if __name__ == "__main__":
    unittest.main()

