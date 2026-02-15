"""Test categories for exercise QA."""

from .prereq import TC_PREREQ
from .solution import TC_SOL
from .grading import TC_GRADE
from .solve import TC_SOLVE
from .verify import TC_VERIFY
from .workflow import TC_WORKFLOW
from .execution import TC_EXEC
from .cleanup import TC_CLEAN
from .idempotency import TC_IDEM, TC_IDEM_EXTENDED
from .aap import TC_AAP, TC_AAP_JOBS
from .e2e import TC_E2E
from .security import TC_SECURITY
from .contract import TC_CONTRACT
from .instructions import TC_INSTRUCT
from .lint import TC_LINT
from .deps import TC_DEPS
from .perf import TC_PERF
from .vars import TC_VARS
from .rollback import TC_ROLLBACK
from .network import TC_NETWORK
from .ee import TC_EE

__all__ = [
    'TC_PREREQ',
    'TC_SOL',
    'TC_GRADE',
    'TC_SOLVE',
    'TC_VERIFY',
    'TC_WORKFLOW',
    'TC_EXEC',
    'TC_CLEAN',
    'TC_IDEM',
    'TC_IDEM_EXTENDED',
    'TC_AAP',
    'TC_AAP_JOBS',
    'TC_E2E',
    'TC_SECURITY',
    'TC_CONTRACT',
    'TC_INSTRUCT',
    'TC_LINT',
    'TC_DEPS',
    'TC_PERF',
    'TC_VARS',
    'TC_ROLLBACK',
    'TC_NETWORK',
    'TC_EE',
]
