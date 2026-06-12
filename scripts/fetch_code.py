#!/usr/bin/env python3
"""
search_github.py — Find a paper's code repository on GitHub and clone it.

Usage:
    python3 search_github.py "<paper-title>" --output-dir <base_dir> --latex-dir <base_dir>/<paper_name>/latex

The script first scans the LaTeX source for GitHub URLs. If none are found, it
searches GitHub by paper title. The user selects the repository, and it is
cloned to <base_dir>/<paper_name>/code/.
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
#  Scan LaTeX for GitHub URLs
# ---------------------------------------------------------------------------


def find_github_urls_in_latex(latex_dir: str) -> list[str]:
    """Walk the LaTeX directory and return every github.com URL found."""
    urls: list[str] = []
    pattern = re.compile(r"https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+")

    for root, _dirs, files in os.walk(latex_dir):
        for f in files:
            if not (f.endswith(".tex") or f.endswith(".bib")):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                for match in pattern.findall(content):
                    # Strip trailing punctuation that may have been captured
                    clean = re.sub(r"[)\]}.,;:\s]+$", "", match)
                    if clean not in urls:
                        urls.append(clean)
            except Exception as exc:
                print(f"  Warning: could not read {path}: {exc}")

    return urls


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


_SOURCE_EXTS = {
    ".py",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".rs",
    ".go",
    ".ts",
    ".js",
    ".r",
    ".m",
    ".jl",
    ".lua",
    ".sh",
}


def is_empty_repo(code_dir: str) -> bool:
    """Check if a cloned repo has any actual source code files."""
    for root, dirs, files in os.walk(code_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in _SOURCE_EXTS:
                return False  # found at least one real source file
    return True


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
    args = parser.parse_args()

    base_dir = os.path.abspath(args.output_dir)
    latex_dir = os.path.abspath(args.latex_dir) if args.latex_dir else None

    # Determine paper name from paper.json if available
    paper_meta_path = os.path.join(base_dir, "paper.json")
    paper_name: str | None = None
    if os.path.isfile(paper_meta_path):
        with open(paper_meta_path) as f:
            paper_meta = json.load(f)
        paper_name = paper_meta.get("title", "").strip()
    if not paper_name:
        paper_name = args.query

    # ---- Phase 1: check LaTeX for embedded URLs ----------------------------
    repo_url: str | None = None
    if latex_dir and os.path.isdir(latex_dir):
        print("Checking LaTeX source for GitHub URLs …")
        found_urls = find_github_urls_in_latex(latex_dir)
        if found_urls:
            print(f"  Found URL(s):")
            for u in found_urls:
                print(f"    • {u}")
            print()
            # Try each URL in order; stop at first successful clone
            for u in found_urls:
                code_dir = os.path.join(base_dir, "code")
                if clone_repo(u, code_dir):
                    repo_url = u
                    break

    # ---- Phase 2: search GitHub by title -----------------------------------
    if not repo_url:
        print("Searching GitHub for repositories …")
        queries = [paper_name, paper_name[:60]]

        # Try to extract a short key-phrase from the title
        short = re.match(r"^(.+?)[:.]", paper_name)
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
            print(f"\n  Found {len(unique)} repository/ies:")
            for i, r in enumerate(unique[:10]):
                desc = (r.get("description") or "")[:90]
                print(f"    [{i + 1}] {r['full_name']}")
                if desc:
                    print(f"        {desc}")
                print(f"        ⭐ {r['stargazers_count']}  {r['html_url']}")
            print()
            try:
                choice = int(
                    input(f"  Select repo (1–{min(len(unique), 10)}, 0 to skip): ")
                )
                if 1 <= choice <= min(len(unique), 10):
                    selected = unique[choice - 1]
                    repo_url = selected["html_url"]
            except (ValueError, EOFError):
                print("  Invalid input.")

    # ---- Phase 3: clone ----------------------------------------------------
    if repo_url:
        code_dir = os.path.join(base_dir, "code")
        if clone_repo(repo_url, code_dir):
            # Check if repo has actual code
            if is_empty_repo(code_dir):
                print(
                    f"\n  \u26a0 Repository is empty or contains no source code files."
                )
                print(
                    f"     Only has: {[f for f in os.listdir(code_dir) if os.path.isfile(os.path.join(code_dir, f))]}"
                )
                print(
                    f"\nThis repo exists but has no actual code. Audit cannot proceed."
                )
                sys.exit(1)
            print(f"\nCode saved \u2192 {code_dir}")
            # Save repo info
            repo_info = {"url": repo_url, "local_path": code_dir}
            with open(os.path.join(base_dir, "repo.json"), "w") as f:
                json.dump(repo_info, f, indent=2)
    else:
        print("\nNo suitable repository found or selected.")
        print(
            "You can manually clone a repo into the 'code' subdirectory and re-run compare.py."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
