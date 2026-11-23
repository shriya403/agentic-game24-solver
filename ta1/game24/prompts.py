LINEAR_PROMPT = """You are solving the Game of 24.

Numbers: {numbers}

Rules:
- Use every supplied number exactly once.
- Allowed operations are +, -, *, / and parentheses.
- The final result must equal exactly 24.
- Do not introduce any other numbers.
- Make one concise sequential attempt; do not generate alternative branches.

Let's think step by step. Show only a concise arithmetic trace, not hidden reasoning.

Return exactly:
RESULT: SUCCESS or FAILURE
STEPS:
1. ...
2. ...
3. ...
EXPRESSION: final expression or NONE
VALUE: final value or NONE
"""


EVALUATOR_PROMPT = """You are the branch-evaluator agent for the Game of 24.
Original numbers: {numbers}
Current candidate states:
{candidates}

Rank the candidates by likelihood of reaching exactly 24 while using all remaining values once.
Fractional intermediate values are allowed. Be concise.
Return one line per candidate exactly as: CANDIDATE <n>: <score 0-100> | <PROMISING/UNCERTAIN/DEAD-END> | <short reason>
"""

