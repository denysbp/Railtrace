#!/usr/bin/env python3
"""Send live-stream.txt to your API, one POST per line.

Each line of live-stream.txt is one report. The script uses only the standard library.

Usage:
    python3 send_live.py --base http://localhost:8000 --file live-stream.txt
"""
import argparse
import collections
import urllib.error
import urllib.request


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--file", default="live-stream.txt")
    args = ap.parse_args()

    codes = collections.Counter()
    with open(args.file, encoding="utf-8") as f:
        for line in f:
            report = line.rstrip("\n")
            if not report:
                continue
            req = urllib.request.Request(
                f"{args.base}/v1/reports",
                data=report.encode("utf-8"),
                method="POST",
                headers={"Content-Type": "text/plain"},
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    codes[resp.status] += 1
            except urllib.error.HTTPError as e:
                codes[e.code] += 1
    print(dict(codes))


if __name__ == "__main__":
    main()
