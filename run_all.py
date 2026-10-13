"""Rebuild every output from data/raw. Use --fetch to re-download the raw data first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from lsr import fetch, report  # noqa: E402

if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch.main()
    s = report.main()
    print("selected:", s["selected"])
    print("dev:", s["dev"])
    print("holdout:", s["holdout"])
    print("posture:", s["posture_as_of"], s["posture_label"], s["posture_active"])
