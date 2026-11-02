import json
import sys
import urllib.error
import urllib.request

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

TARGET_PYTHON = Version("3.11")
PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"


def parse_line(line):
    """Return (name, version) for a 'name==version' line, or None for blanks/comments."""
    line = line.split("#", 1)[0].strip()
    if not line:
        return None
    name, sep, version = line.partition("==")
    if not sep:
        raise ValueError(f"Expected 'name==version', got: {line!r}")
    return name.strip(), version.strip()


def fetch_release(name, version):
    """Return the release's JSON from PyPI, or None if the package/version does not exist."""
    url = PYPI_URL.format(name=name, version=version)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def minimum_python(spec_set):
    """Return the lowest Python version allowed by the lower-bound clauses of a SpecifierSet."""
    lows = [
        Version(s.version.rstrip(".*"))
        for s in spec_set
        if s.operator in (">=", ">", "~=", "==", "===")
    ]
    return max(lows) if lows else None


def main(path):
    with open(path, encoding="utf-8") as f:
        deps = [d for d in (parse_line(line) for line in f) if d]

    not_found = 0
    incompatible = 0
    highest = None  # (min_version, name, version)

    for name, version in deps:
        release = fetch_release(name, version)
        if release is None:
            not_found += 1
            continue

        requires_python = (release["info"].get("requires_python") or "").strip()
        if not requires_python:
            continue  # no constraint counts as compatible

        try:
            spec = SpecifierSet(requires_python)
        except InvalidSpecifier:
            continue
        if not spec.contains(TARGET_PYTHON, prereleases=True):
            incompatible += 1

        min_py = minimum_python(spec)
        if min_py and (highest is None or min_py > highest[0]):
            highest = (min_py, name, version)

    print(f"Dependencies checked: {len(deps)}")
    print(f"Not found on PyPI: {not_found}")
    print(f"Incompatible with Python 3.11: {incompatible}")
    if highest:
        min_py, name, version = highest
        print(f"Highest requirement: {name}=={version} (>={min_py})")
    else:
        print("Highest requirement: none")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "requirements.txt")
