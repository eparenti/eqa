"""Test categories for exercise QA.

Test categories are executed in this order:
1. TC-PREREQ - Prerequisites validation (P0 blocker if fails)
2. TC-STUDENTSIM - Student simulation (the main test)
3. TC-SOL - Solution file validation
4. TC-GRADE - Grading validation (Labs only)
5. TC-IDEM - Idempotency testing (always)
6. TC-CLEAN - Cleanup validation

Each test category:
- Takes ExerciseContext and SSHConnection
- Returns TestResult with bugs found
- Should not raise exceptions (catch and convert to bugs)
- Uses Bug severity levels (P0/P1/P2/P3)
"""

from .prereq import TC_PREREQ
from .studentsim import TC_STUDENTSIM
from .solution import TC_SOL
from .grading import TC_GRADE
from .idempotency import TC_IDEM
from .cleanup import TC_CLEAN

__all__ = [
    'TC_PREREQ',
    'TC_STUDENTSIM',
    'TC_SOL',
    'TC_GRADE',
    'TC_IDEM',
    'TC_CLEAN',
]
