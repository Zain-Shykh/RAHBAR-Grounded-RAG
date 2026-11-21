"""Group measure_resources.sh samples by workload (pod name minus hash) and print median and peak (R3-F5-1)."""
import re
import statistics
import sys
from collections import defaultdict

by: dict[str, list[tuple[int, int]]] = defaultdict(list)
for f in sys.argv[1:]:
    for line in open(f):
        p = line.split()
        if len(p) == 4 and p[2].isdigit() and p[3].isdigit():
            name = re.sub(r"(-[0-9a-f]{8,10})?-[a-z0-9]{5}$|-\d+$", "", p[1])
            by[name].append((int(p[2]), int(p[3])))
print(f"{'workload':28} {'n':>4} {'cpu_med_m':>9} {'cpu_peak_m':>10} {'mem_med_Mi':>10} {'mem_peak_Mi':>11}")
for k, v in sorted(by.items()):
    c, m = [x[0] for x in v], [x[1] for x in v]
    print(f"{k:28} {len(v):>4} {int(statistics.median(c)):>9} {max(c):>10} {int(statistics.median(m)):>10} {max(m):>11}")
