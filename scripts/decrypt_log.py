"""Print decrypted traffic readings (local use only).

    python scripts/decrypt_log.py data/traffic/2026-10.jsonl.age [--key age-key.txt]

The private key is read from --key, or from the AGE_IDENTITY env var.
"""
import argparse
import base64
import os
import sys

from pyrage import decrypt, x25519


def load_identity(key_path):
    text = os.environ.get("AGE_IDENTITY") or open(key_path, encoding="utf-8").read()
    secret = next(l.strip() for l in text.splitlines() if l.startswith("AGE-SECRET-KEY-"))
    return x25519.Identity.from_str(secret)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--key", default="age-key.txt")
    args = parser.parse_args()

    identity = load_identity(args.key)
    for path in args.files:
        with open(path, encoding="ascii") as f:
            for line in f:
                if line.strip():
                    print(decrypt(base64.b64decode(line), [identity]).decode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
