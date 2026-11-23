#!/usr/bin/env python3
"""Print a verification.json (stdin) as the per-document table: `make lake-report`."""

import json
import sys

from pipeline.verification.report import render_text

print(render_text(json.load(sys.stdin)))
