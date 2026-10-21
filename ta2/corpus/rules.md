# Game of 24 reference rules

A puzzle consists of four integer cards. Use each card exactly once. Repeated
card values represent separate cards. Combine them using addition, subtraction,
multiplication, division, and parentheses to obtain exactly 24. Concatenation,
exponentiation, factorials, extra constants, and executable code are prohibited.

Fractional and negative intermediate values are permitted. Division by zero is
never permitted. Preserve rational values exactly rather than rounding decimals.
An intermediate value of 24 is not sufficient if unused cards remain.

Useful strategies include grouping pairs, forming a useful difference, and
retaining a fractional intermediate when integer-only choices fail. Compare
candidate expressions, then submit the best candidate to an independent exact
verifier. Evaluator confidence is not mathematical proof. If verification fails,
use its concrete feedback to revise the proposal within the supervisor's budget.

This reference intentionally contains no worked answers to evaluation puzzles.
