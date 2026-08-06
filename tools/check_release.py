"""Has what this repo says it is actually shipped anywhere?

Five releases in a row failed on a GitHub Actions outage and PyPI sat four
versions behind for most of a day without anything noticing. The release
workflow was not the problem, it never ran. A pipeline that only reports
failures it was present for cannot catch that, so this asks the question from
the outside instead: what does the repo claim, and what do the registries
actually serve?

Exit status is the signal, so CI can act on it.

    0  everything downstream matches pyproject.toml
    1  the repo is ahead, something needs republishing
    2  could not reach a registry, so no judgement is possible

    uv run python tools/check_release.py
    uv run python tools/check_release.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPI = "https://pypi.org/pypi/vintage-mcp/json"
REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.RezaSoleymanifar/vintage"
TIMEOUT = 30


class Unreachable(RuntimeError):
    """A registry did not answer, which is not the same as being behind."""


def get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "vintage-release-check"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise Unreachable(f"{url}: {exc}") from exc


def declared() -> tuple[str, str]:
    """What the repo says it is, from both files the release guard compares."""
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        found = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M)
    if not found:
        raise SystemExit("pyproject.toml has no version")

    with open(os.path.join(ROOT, "server.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    return found.group(1), manifest["version"]


def as_tuple(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in version.split("."))


def on_pypi() -> str:
    return get(PYPI)["info"]["version"]


def on_registry() -> str | None:
    payload = get(REGISTRY)
    servers = payload.get("servers") or []
    for entry in servers:
        server = entry.get("server", entry)
        if "vintage" in (server.get("name") or ""):
            return server.get("version")
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    package, manifest = declared()
    if package != manifest:
        report = {"ok": False, "reason": "pyproject and server.json disagree",
                  "pyproject": package, "server_json": manifest}
        print(json.dumps(report) if args.json else
              f"pyproject says {package}, server.json says {manifest}, fix that first")
        raise SystemExit(1)

    try:
        pypi = on_pypi()
        registry = on_registry()
    except Unreachable as exc:
        print(json.dumps({"ok": None, "reason": str(exc)}) if args.json else
              f"could not reach a registry: {exc}")
        raise SystemExit(2) from None

    behind = []
    if as_tuple(pypi) < as_tuple(package):
        behind.append(f"PyPI serves {pypi}")
    if registry and as_tuple(registry) < as_tuple(package):
        behind.append(f"MCP registry serves {registry}")

    report = {
        "ok": not behind,
        "declared": package,
        "pypi": pypi,
        "mcp_registry": registry,
        "behind": behind,
        "tag": f"v{package}",
    }

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"repo declares   {package}")
        print(f"PyPI serves     {pypi}")
        print(f"MCP registry    {registry or 'not found'}")
        print()
        if behind:
            print("BEHIND: " + "; ".join(behind))
            print(f"Republish with: gh workflow run release.yml --ref v{package}")
        else:
            print("everything downstream is current")

    raise SystemExit(1 if behind else 0)


if __name__ == "__main__":
    main()
