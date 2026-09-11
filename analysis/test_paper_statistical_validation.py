import unittest

import numpy as np

from analysis.paper_statistical_validation import (
    friedman_summary,
    holm_adjust,
    parse_result_table,
)


class StatisticalValidationTests(unittest.TestCase):
    def test_friedman_summary_ranks_lower_objectives_first(self):
        values = np.array(
            [
                [1.0, 2.0, 3.0],
                [2.0, 3.0, 4.0],
                [3.0, 4.0, 5.0],
                [4.0, 5.0, 6.0],
            ]
        )

        summary = friedman_summary(values)

        self.assertAlmostEqual(summary.statistic, 8.0)
        self.assertEqual(summary.mean_ranks.tolist(), [1.0, 2.0, 3.0])

    def test_holm_adjustment_is_monotone_and_bounded(self):
        adjusted = holm_adjust([0.001, 0.005, 0.02])

        self.assertEqual(adjusted, [0.003, 0.01, 0.02])

    def test_parser_reads_active_hw_rows_and_strips_bold_markup(self):
        latex = r"""
        % & HW99 & 9 & 9 & 9 & 9 & 9 & 9 & 9 \\
        & HW1 & 1,200 & \textbf{2.5e3} & 3 & 4 & 5 & 6 & 7 \\
        & HW2 & 8 & 9 & 10 & 11 & 12 & 13 & \textbf{14} \\
        """

        instances, values = parse_result_table(latex)

        self.assertEqual(instances, [1, 2])
        self.assertEqual(values.tolist(), [[1200.0, 2500.0, 3.0, 4.0, 5.0, 6.0, 7.0], [8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0]])


if __name__ == "__main__":
    unittest.main()
