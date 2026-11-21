"""Remove one file's entry from a corpus manifest (_index.json, a JSON list): scripts/manifest_remove.py <manifest> <file>."""
import json
import sys

path, name = sys.argv[1:3]
entries = json.load(open(path))
kept = [e for e in entries if e.get("file") != name]
json.dump(kept, open(path, "w"), indent=2)
print(f"removed {len(entries) - len(kept)} entry for {name}; {len(kept)} remain")
