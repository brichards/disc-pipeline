"""Writing the manifest, the plan and the playlist overrides."""

import json
import os
from pathlib import Path


def write(target, data):
    """Write atomically, so an interrupted save cannot truncate the file."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, target)
