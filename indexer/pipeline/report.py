"""`python -m pipeline.report [run_id]`: print a stored verification report as a table."""

import sys

from .verification.run_verify import main

sys.exit(main())
