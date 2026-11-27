#!/usr/bin/env python3
"""Source verification and a deliberately non-release Chromium Android profile."""
import argparse
import base64
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CHROMIUM_GIT = "https://chromium.googlesource.com/chromium/src.git"
PACKAGE = "io.github.ktclat.kiwinext.dev"
GIB = 1024**3
MIN_BYTES = 100 * 10**9  # Chromium's documented minimum, not an expected final size.
PROFILES = {"arm64": "kiwinext-arm64", "x64": "kiwinext-x64"}
TRUSTED = (
    ("heritage", "kiwibrowser/src.next"),
    ("candidate", "chromium/chromium"),
)


def read_lock():
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    if lock["schema"] != 1 or tuple((s["role"], s["repo"]) for s in lock["sources"]) != TRUSTED:
        raise ValueError("Unexpected official source identities")
    for s in lock["sources"]:
        if not re.fullmatch(r"[a-f0-9]{40}", s["commit"]):
            raise ValueError("Full commit SHA is required")
        if not re.fullmatch(r"[0-9.]+", s["tag"]):
            raise ValueError("Unexpected release tag")
        for path, sha in s["blobs"].items():
            if any(p in ("", ".", "..") for p in path.split("/")) or not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise ValueError("Invalid pinned path or blob")
    return lock["sources"]


def version(data):
    parts = {}
    for line in data.decode("ascii").splitlines():
        key, value = line.split("=", 1)
        if key in parts or not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Malformed VERSION file")
        parts[key] = value
    if set(parts) != {"MAJOR", "MINOR", "BUILD", "PATCH"}:
        raise ValueError("Incomplete VERSION file")
    return ".".join(parts[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))


def blob_sha(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def github(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "kiwi-next-source-verifier"}
    token = os.environ.get("GH_TOKEN")
    request = Request("https://api.github.com/" + path, headers=headers)
    if token:
        request.add_unredirected_header("Authorization", "Bearer " + token)
    for attempt in range(2):
        try:
            with urlopen(request, timeout=20) as rsp:
                return json.load(rsp)
        except HTTPError as exc:
            exhausted = exc.headers.get("X-RateLimit-Remaining") == "0"
            retry_after = exc.headers.get("Retry-After", "")
            if attempt or (exc.code != 429 and not (exc.code == 403 and (exhausted or retry_after))):
                raise
            delay = max(1, int(retry_after)) if retry_after.isdecimal() else 60
            if exhausted:
                reset = exc.headers.get("X-RateLimit-Reset", "")
                if not reset.isdecimal():
                    raise
                delay = max(delay, int(reset) - int(time.time()) + 1)
            if delay > 120:
                raise
            print(f"GitHub rate limited {path}; waiting {delay}s before one retry", file=sys.stderr)
            time.sleep(delay)


def verify_remote(sources, fetch=github):
    for s in sources:
        repo, sha = s["repo"], s["commit"]
        ref = fetch(f"repos/{repo}/git/ref/tags/{quote(s['tag'], safe='')}")["object"]
        if ref["type"] != "commit" or ref["sha"] != sha:
            raise ValueError(f"{repo} tag no longer resolves to the pinned source")
        for path, expected in s["blobs"].items():
            response = fetch(f"repos/{repo}/contents/{quote(path)}?ref={sha}")
            if response["type"] != "file" or response["encoding"] != "base64":
                raise ValueError(f"Unexpected response for {repo}/{path}")
            payload = base64.b64decode("".join(response["content"].split()), validate=True)
            if response["sha"] != expected or blob_sha(payload) != expected:
                raise ValueError(f"Source differs from lock: {repo}/{path}")
            if path == "chrome/VERSION" and version(payload) != s["version"]:
                raise ValueError(f"VERSION differs from lock: {repo}")
        print(f"Verified {s['role']}: {repo} {s['tag']} / {sha} (source VERSION {s['version']})")


def verify_candidate_checkout(src, candidate):
    def git(*args, text=True):
        return subprocess.check_output(["git", "-C", str(src), *args], text=text, timeout=45)

    if git("remote", "get-url", "origin").strip() != CHROMIUM_GIT:
        raise ValueError("Candidate checkout must use the official Chromium Git origin")
    ref = "refs/tags/" + candidate["tag"]
    ref_lines = git("ls-remote", "--exit-code", CHROMIUM_GIT, ref).splitlines()
    if ref_lines != [candidate["commit"] + "\t" + ref]:
        raise ValueError("Official Chromium tag does not match the pinned commit")
    if git("rev-parse", "HEAD").strip() != candidate["commit"]:
        raise ValueError("Candidate checkout HEAD differs from the lock")
    for path, expected in candidate["blobs"].items():
        entry = src / path
        if entry.is_symlink() or not entry.is_file() or not entry.resolve().is_relative_to(src.resolve()):
            raise ValueError(f"Invalid candidate checkout file: {path}")
        payload = entry.read_bytes()
        if git("rev-parse", "HEAD:" + path).strip() != expected or blob_sha(payload) != expected:
            raise ValueError(f"Candidate checkout differs from the lock: {path}")
        if path == "chrome/VERSION" and version(payload) != candidate["version"]:
            raise ValueError("Candidate checkout VERSION differs from the lock")
    print(f"Verified official Chromium Git tag, HEAD and {len(candidate['blobs'])} checked-out blobs")


def check_capacity(path, minimum=MIN_BYTES):
    free = shutil.disk_usage(path).free
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise ValueError("Use an x86-64 Linux build host")
    if free < minimum:
        why = "Chromium documents at least 100 GB" if minimum == MIN_BYTES else f"the build reserves {minimum / GIB:.0f} GiB for output"
        raise ValueError(f"{path} has {free / GIB:.1f} GiB free; {why}")
    return free


def gn_text(arch):
    if arch not in PROFILES:
        raise ValueError("Unsupported Android target")
    return "\n".join((
        "# Kiwi Next engineering profile. Not a production or official Chrome build.",
        'target_os = "android"', f'target_cpu = "{arch}"',
        'is_debug = false', 'is_official_build = false', 'is_chrome_branded = false',
        'is_component_build = false', 'symbol_level = 0',
        '# Use Chromium Android desktop-extension code for the phone feasibility build.',
        'is_desktop_android = true',
        f'chrome_public_manifest_package = "{PACKAGE}"', "",
    ))


def prepare(src, arch, candidate):
    if not (src / ".git").exists() or not (src / "chrome" / "VERSION").is_file():
        raise ValueError("Pass the Chromium source root from an Android gclient checkout")
    check_capacity(src, 30 * GIB)
    head = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
    if head != candidate["commit"] or version((src / "chrome" / "VERSION").read_bytes()) != candidate["version"]:
        raise ValueError("Checkout does not match the pinned Chromium source")
    if subprocess.check_output(["git", "-C", str(src), "status", "--porcelain", "--untracked-files=no"],
                               text=True).strip():
        raise ValueError("Use a clean tracked source tree")
    target = src / "out" / PROFILES[arch]
    for p in (target.parent, target, target / "args.gn"):
        if p.is_symlink():
            raise ValueError(f"Refusing to follow a symlink at {p}")
    target.mkdir(parents=True, exist_ok=True)
    config = target / "args.gn"
    text = gn_text(arch)
    if config.exists() and config.read_text() != text:
        raise ValueError(f"Refusing to overwrite existing {config}")
    if not config.exists():
        with config.open("x", encoding="utf-8") as f:
            f.write(text)
    print(f"Prepared {config}; no build or install was run")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="method", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--role", choices=("heritage", "candidate"))
    checkout = sub.add_parser("verify-checkout")
    checkout.add_argument("source_root", type=Path)
    pf = sub.add_parser("preflight")
    pf.add_argument("directory", type=Path)
    pf.add_argument("--report-only", action="store_true")
    gn = sub.add_parser("prepare")
    gn.add_argument("source_root", type=Path)
    gn.add_argument("architecture", choices=PROFILES)
    args = p.parse_args()
    sources = read_lock()
    if args.method == "verify":
        verify_remote([s for s in sources if args.role is None or s["role"] == args.role])
    elif args.method == "verify-checkout":
        verify_candidate_checkout(args.source_root.resolve(), sources[1])
    elif args.method == "prepare":
        prepare(args.source_root.resolve(), args.architecture, sources[1])
    else:
        try:
            free = check_capacity(args.directory)
            print(f"{free / GIB:.1f} GiB free; disk and host architecture satisfy baseline")
        except ValueError as exc:
            if not args.report_only:
                raise
            print(f"Build not started: {exc}")
        print("Tool discovery: " + ", ".join(f"{k}={'found' if shutil.which(k) else 'missing'}"
                                            for k in ("git", "gclient", "gn", "autoninja", "adb")))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
