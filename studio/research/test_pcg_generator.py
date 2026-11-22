#!/usr/bin/env python3
"""Unit tests for Lantern Atlas Constraint PCG Generator."""
import unittest
from studio.research.pcg_generator import (
    ConstraintPCGGenerator,
    compute_pulse_table,
    solve_grid_python,
    solve_via_cpp_oracle,
)


class TestPCGGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = ConstraintPCGGenerator(seed=42)

    def test_pulse_table_dimensions(self):
        pulse = compute_pulse_table(3)
        self.assertEqual(len(pulse), 9)
        # Center cell (index 4) toggles itself + 4 orthogonal neighbors = 5 bits set
        center_bits = bin(pulse[4]).count("1")
        self.assertEqual(center_bits, 5)

    def test_relay_pulse_coupling(self):
        # Relay between 0 and 8
        pulse = compute_pulse_table(3, left=0, right=8)
        self.assertTrue(pulse[0] & (1 << 8))
        self.assertTrue(pulse[8] & (1 << 0))

    def test_solve_grid_python_matches_cpp_oracle(self):
        # Test sample configuration
        width, shutter, left, right, state = 3, 0, 0, 8, 0
        py_par, py_no_link = solve_grid_python(width, shutter, left, right, state)
        cpp_par, cpp_no_link = solve_via_cpp_oracle(width, shutter, left, right, state)
        self.assertEqual(py_par, cpp_par)
        self.assertEqual(py_no_link, cpp_no_link)

    def test_generate_level_satisfies_par(self):
        level = self.generator.generate_level("TEST_01", width=3, target_par=2, require_relay=False)
        self.assertIsNotNone(level)
        self.assertEqual(level.par, 2)
        self.assertEqual(level.target_par, 2)

    def test_generate_level_relay_necessity(self):
        level = self.generator.generate_level("TEST_RELAY", width=3, target_par=3, require_relay=True)
        self.assertIsNotNone(level)
        self.assertEqual(level.par, 3)
        self.assertTrue(level.relay_required)
        self.assertTrue(level.par_without_relay == -1 or level.par_without_relay > level.par)


if __name__ == "__main__":
    unittest.main()
