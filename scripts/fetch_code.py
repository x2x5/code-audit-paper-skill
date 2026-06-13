#!/usr/bin/env python3
"""
fetch_code.py — Find and clone a paper's code repository from GitHub.

Usage (agent provides URL):
    python3 fetch_code.py "<query>" --output-dir <base_dir> \\
        --latex-dir <base_dir>/<paper_name>/latex --repo-url <URL>

Usage (search mode, when no URL found in LaTeX):
    python3 fetch_code.py "<query>" --output-dir <base_dir> \\
        --latex-dir <base_dir>/<paper_name>/latex

The script's job is to clone. The agent is responsible for:
- Deciding which GitHub URL is the paper's actual code repository
- Providing it via --repo-url
- Choosing the paper_name (method name or sanitized title)
- Judging whether the cloned repo is a real code implementation
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

GITHUB_API_URL = "https://api.github.com"


# ---------------------------------------------------------------------------
#  GitHub API helpers
# ---------------------------------------------------------------------------


def search_github(query: str, max_results: int = 10) -> list[dict]:
    """Search GitHub repositories by keyword. Returns list of repo dicts."""
    url = (
        f"{GITHUB_API_URL}/search/repositories"
        f"?q={urllib.parse.quote(query)}"
        f"&sort=stars&order=desc&per_page={max_results}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PaperCodeAudit/1.0",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("items", [])
    except urllib.error.HTTPError as e:
        print(f"  GitHub API error: {e.code} — {e.reason}")
        if e.code == 403:
            print("  (Rate-limited. Set GITHUB_TOKEN env var or wait.)")
        return []


# ---------------------------------------------------------------------------
#  Scan LaTeX for GitHub URLs (informational only)
# ---------------------------------------------------------------------------


def find_github_urls_in_latex(latex_dir: str) -> list[dict]:
    """Walk the LaTeX directory and return every github.com URL with context.

    Returns a list of dicts: {url, file, line, context}.
    The agent uses the context to decide which URL is the paper's code repo.
    """
    results: list[dict] = []
    url_pattern = re.compile(r"(https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)")

    for root, _dirs, files in os.walk(latex_dir):
        for f in files:
            if not (f.endswith(".tex") or f.endswith(".bib")):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
                for lineno, line in enumerate(lines, 1):
                    for match in url_pattern.finditer(line):
                        url = match.group(1)
                        # Strip trailing punctuation that may have been captured
                        clean_url = re.sub(r"[)\]}.,;:\s]+$", "", url)
                        context = line.strip()[:200]
                        rel_path = os.path.relpath(path, latex_dir)
                        # Deduplicate
                        if clean_url not in [r["url"] for r in results]:
                            results.append(
                                {
                                    "url": clean_url,
                                    "file": rel_path,
                                    "line": lineno,
                                    "context": context,
                                }
                            )
            except Exception as exc:
                print(f"  Warning: could not read {path}: {exc}")

    return results


# ---------------------------------------------------------------------------
#  Clone
# ---------------------------------------------------------------------------


def clone_repo(repo_url: str, target_dir: str) -> bool:
    """Shallow-clone *repo_url* into *target_dir*."""
    print(f"  Cloning {repo_url} …")
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)

    # Remove existing directory to avoid 'already exists' error
    if os.path.isdir(target_dir):
        print(f"  Removing existing directory: {target_dir}")
        import shutil

        shutil.rmtree(target_dir)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, target_dir],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode == 0:
        print(f"  \u2713 Cloned \u2192 {target_dir}")
        return True
    else:
        print(f"  \u2717 Failed: {result.stderr.strip()}")
        return False


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find and clone paper code from GitHub"
    )
    parser.add_argument("query", help="Paper title or arXiv ID")
    parser.add_argument("--output-dir", "-o", default=".", help="Base output directory")
    parser.add_argument(
        "--latex-dir", "-l", default=None, help="Path to LaTeX source directory"
    )
    parser.add_argument(
        "--repo-url",
        "-r",
        default=None,
        help="GitHub repository URL to clone (agent-specified)",
    )
    args = parser.parse_args()

    base_dir = os.path.abspath(args.output_dir)
    latex_dir = os.path.abspath(args.latex_dir) if args.latex_dir else None

    # ------ Determine paper name from --latex-dir path ------
    # --latex-dir is <base_dir>/<paper_name>/latex
    paper_name: str | None = None
    if latex_dir:
        parent = os.path.dirname(latex_dir)  # <base_dir>/<paper_name>
        if os.path.isdir(parent):
            paper_name = os.path.basename(parent)

    if not paper_name:
        # Fallback: use a sanitized version of the query
        paper_name = re.sub(r"[^a-z0-9-]+", "-", args.query.lower().strip())
        paper_name = paper_name[:60].strip("-")

    # Target code directory: <base_dir>/<paper_name>/code
    code_dir = os.path.join(base_dir, paper_name, "code")
    repo_info_path = os.path.join(base_dir, paper_name, "repo.json")

    print(f"Paper name: {paper_name}")
    print(f"Code target: {code_dir}")
    print()

    # ------ Phase 0: --repo-url provided by agent ------
    if args.repo_url:
        print(f"Using provided repository URL: {args.repo_url}")
        if clone_repo(args.repo_url, code_dir):
            print(f"\nCode saved \u2192 {code_dir}")
            # Save repo info
            repo_info = {"url": args.repo_url, "local_path": code_dir}
            with open(repo_info_path, "w") as f:
                json.dump(repo_info, f, indent=2)
            print(f"Repo info \u2192 {repo_info_path}")
        else:
            print("\nFailed to clone repository.")
            sys.exit(1)
        return

    # ------ Phase 1: scan LaTeX for URLs (informational only) ------
    if latex_dir and os.path.isdir(latex_dir):
        print("Checking LaTeX source for GitHub URLs \u2026")
        found_urls = find_github_urls_in_latex(latex_dir)
        if found_urls:
            print(f"\n  Found {len(found_urls)} GitHub URL(s) in LaTeX source:")
            print()
            for r in found_urls:
                print(f"    URL: {r['url']}")
                print(f"    File: {r['file']}:{r['line']}")
                print(f"    Context: {r['context']}")
                print()
            print("  \u2500" * 60)
            print("  Agent: examine the context above and decide")
            print("  which URL is the paper's code repository.")
            print("  Then re-run with: --repo-url <URL>")
            print("  \u2500" * 60)
            print()
        else:
            print("  No GitHub URLs found in LaTeX source.\n")
    else:
        print("  No LaTeX directory provided or found.\n")

    # ------ Phase 2: search GitHub by title ------
    print("Searching GitHub for repositories \u2026")
    queries = [args.query, args.query[:60]]

    # Try to extract a short key-phrase from the title
    short = re.match(r"^(.+?)[:.]", args.query)
    if short:
        queries.append(short.group(1).strip())

    all_results: list[dict] = []
    for q in queries:
        print(f'  Searching: "{q}"')
        all_results.extend(search_github(q))

    # Deduplicate by full_name
    seen: set[str] = set()
    unique: list[dict] = []
    for r in all_results:
        if r["full_name"] not in seen:
            seen.add(r["full_name"])
            unique.append(r)

    if unique:
        print(f"\n  Found {len(unique)} repository/ies on GitHub:")
        for i, r in enumerate(unique[:10]):
            desc = (r.get("description") or "")[:90]
            print(f"    [{i + 1}] {r['full_name']}")
            if desc:
                print(f"        {desc}")
            print(f"        \u2b50 {r['stargazers_count']}  {r['html_url']}")
        print()
        print("  \u2500" * 60)
        print("  Agent: select the correct repository and")
        print("  re-run with: --repo-url <URL>")
        print("  \u2500" * 60)
    else:
        print("\n  No repositories found on GitHub.")
        print("  You can still manually clone a repo into:")
        print(f"    {code_dir}")
        print("  Then re-run the audit.")

    print()
    print("No repository was cloned. Use --repo-url to specify one.")
    sys.exit(1)


if __name__ == "__main__":
    main()
