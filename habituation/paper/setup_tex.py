#!/usr/bin/env python3
"""Optional local installation of a pinned official portable Tectonic binary.

Only Linux x86_64; no sudo or system package changes. First compile downloads
TeX resources into .cache/. Use an existing Tectonic via TECTONIC_BIN otherwise.
"""
import hashlib
import io
from pathlib import Path
import platform
import tarfile
import urllib.request

VERSION = "0.17.0"
URL = ("https://github.com/tectonic-typesetting/tectonic/releases/download/"
       "tectonic%400.17.0/tectonic-0.17.0-x86_64-unknown-linux-musl.tar.gz")
SHA256 = "8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7"


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("This bootstrap is Linux x86_64 only; install Tectonic for your platform and set TECTONIC_BIN.")
    target = Path(__file__).resolve().parent / ".tools/tectonic"
    if target.exists():
        print("Existing local compiler retained:", target)
        return
    data = urllib.request.urlopen(URL, timeout=120).read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("Official archive digest mismatch; no executable written.")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        # Read only the fixed executable entry; do not extract arbitrary archive paths.
        member = archive.getmember("tectonic")
        if not member.isfile():
            raise SystemExit("Unexpected archive entry type.")
        executable = archive.extractfile(member).read()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as f:
        f.write(executable)
    target.chmod(0o755)
    print("Verified official Tectonic", VERSION, "installed locally:", target)


if __name__ == "__main__":
    main()
