#!/usr/bin/env python3
"""Copy result files from a Colab VM to the operator's machine over HTTPS.

Usage: SYNC_URL=https://<tunnel>/<token>/up python scripts/push_results.py DIR [DIR...]
Uploads every file under each DIR in 4 MB chunks and checks the SHA-256 the
receiver reports for each chunk. Transport only; it never changes the files.
"""
import hashlib
import os
import sys
import urllib.parse
import urllib.request

CHUNK = 4 * 1024 * 1024


def post(url, data):
    request = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode()


def push(base, path, root):
    name = os.path.relpath(path, root)
    with open(path, "rb") as handle:
        offset = 0
        while True:
            data = handle.read(CHUNK)
            if not data and offset:
                break
            query = urllib.parse.urlencode({"name": name, "offset": offset})
            reply = post(f"{base}?{query}", data)
            if reply.split()[-1] != hashlib.sha256(data).hexdigest():
                raise RuntimeError(f"Checksum mismatch for {name} at {offset}")
            offset += len(data)
            if len(data) < CHUNK:
                break
    return name, offset


def main():
    base = os.environ["SYNC_URL"]
    root = os.getcwd()
    for directory in sys.argv[1:]:
        for folder, _, files in os.walk(directory):
            for file in sorted(files):
                name, size = push(base, os.path.join(folder, file), root)
                print(f"pushed {name} ({size} bytes)", flush=True)


if __name__ == "__main__":
    main()
