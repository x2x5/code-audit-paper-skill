#!/usr/bin/env python3
"""
search_arxiv.py — Search arXiv for a paper and download its LaTeX source.

Usage:
    python3 search_arxiv.py "<paper-title>" --output-dir <base_dir>

The script queries the arXiv API, lets the user pick from results (if multiple),
downloads the LaTeX source bundle, and extracts it to <base_dir>/<paper_name>/latex/.

If the paper only has a PDF on arXiv (no LaTeX source), the script reports that
clearly and exits — no PDF parsing is attempted.
"""

import argparse
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_EPRINT_URL = "https://arxiv.org/e-print"


# ---------------------------------------------------------------------------
#  arXiv API helpers
# ---------------------------------------------------------------------------


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arXiv by title. Returns a list of result dicts."""
    params = {
        "search_query": f'ti:"{query}"',
        "max_results": str(max_results),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"User-Agent": "PaperCodeAudit/1.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    xml_data = resp.read().decode("utf-8")

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(xml_data)
    entries = root.findall("atom:entry", ns)

    results = []
    for entry in entries:
        title_el = entry.find("atom:title", ns)
        title = (
            title_el.text.strip().replace("\n", " ")
            if title_el is not None
            else "Unknown"
        )

        id_el = entry.find("atom:id", ns)
        arxiv_id = ""
        if id_el is not None:
            m = re.search(r"/(\d+\.\d+)(v\d+)?", id_el.text)
            if m:
                arxiv_id = m.group(1) + (m.group(2) or "")

        summary_el = entry.find("atom:summary", ns)
        summary = (
            summary_el.text.strip().replace("\n", " ") if summary_el is not None else ""
        )

        authors = []
        for author in entry.findall("atom:author", ns):
            name_el = author.find("atom:name", ns)
            if name_el is not None:
                authors.append(name_el.text)

        results.append(
            {
                "id": arxiv_id,
                "title": title,
                "summary": summary[:500],
                "authors": authors,
            }
        )

    return results


# ---------------------------------------------------------------------------
#  Download / extraction
# ---------------------------------------------------------------------------


def _looks_like_pdf(data: bytes) -> bool:
    """Check whether *data* starts with the PDF magic bytes."""
    return data[:4] == b"%PDF"


def download_source(arxiv_id: str, output_dir: str) -> None:
    """Download the LaTeX source from arXiv and extract it.

    Raises RuntimeError if the download is a PDF (i.e. the author did not
    upload LaTeX source).  Caller should catch this and report gracefully.
    """
    os.makedirs(output_dir, exist_ok=True)

    base_id = re.sub(r"v\d+$", "", arxiv_id)  # strip version for download URL
    url = f"{ARXIV_EPRINT_URL}/{base_id}"

    print(f"  Downloading source from {url} …")
    req = urllib.request.Request(url, headers={"User-Agent": "PaperCodeAudit/1.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    raw_data = resp.read()

    # --- Detect PDF early ---------------------------------------------------
    if _looks_like_pdf(raw_data):
        # Clean up the empty directory we just created
        os.rmdir(output_dir)
        raise RuntimeError(
            f"arXiv paper {arxiv_id} has no LaTeX source — only a PDF is available. "
            "Cannot extract claims without LaTeX source."
        )

    # --- Try to extract as tarball -------------------------------------------
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
        tmp.write(raw_data)
        tmp_path = tmp.name

    extracted = False
    try:
        # arXiv typically returns .tar.gz
        try:
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(path=output_dir)
            print(f"  Extracted gzipped tarball → {output_dir}")
            extracted = True
        except tarfile.ReadError:
            # Fall back to uncompressed tar
            try:
                with tarfile.open(tmp_path, "r:") as tar:
                    tar.extractall(path=output_dir)
                print(f"  Extracted uncompressed tarball → {output_dir}")
                extracted = True
            except tarfile.ReadError:
                # Last resort: single .tex file uploaded directly
                # (arXiv occasionally returns a lone .tex instead of a tarball)
                print(f"  Not a tarball — checking if it is a valid .tex file …")
                # Read first few hundred bytes as text to guess if it's TeX
                text_start = raw_data[:1024].decode("utf-8", errors="replace")
                if re.search(
                    r"\\(documentclass|section|begin\{document\})", text_start
                ):
                    tex_path = os.path.join(output_dir, f"{base_id}.tex")
                    with open(tex_path, "wb") as f:
                        f.write(raw_data)
                    print(f"  Saved single .tex file → {tex_path}")
                    extracted = True
                else:
                    # Don't know what this is — clean up and bail
                    os.rmdir(output_dir)
                    raise RuntimeError(
                        f"Download from arXiv for {arxiv_id} is not a LaTeX tarball "
                        "or .tex file, and not a PDF. Cannot process."
                    )
    finally:
        os.unlink(tmp_path)

    # --- Report TeX files found ---------------------------------------------
    tex_count = 0
    for root, _dirs, files in os.walk(output_dir):
        for f in files:
            if f.endswith(".tex"):
                tex_count += 1
                print(f"    TeX: {os.path.relpath(os.path.join(root, f), output_dir)}")
    print(f"  ({tex_count} TeX file(s) total)")


# ---------------------------------------------------------------------------
#  Misc
# ---------------------------------------------------------------------------


def sanitize_paper_name(title: str) -> str:
    """Turn a paper title into a safe, short directory name."""
    name = title.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"[\s-]+", "-", name)
    name = name[:80].strip("-")
    return name


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search arXiv and download LaTeX source"
    )
    parser.add_argument("query", help="Paper title or arXiv ID (e.g. 1706.03762)")
    parser.add_argument(
        "--output-dir", "-o", default=".", help="Base output directory (default: cwd)"
    )
    parser.add_argument(
        "--max-results",
        "-m",
        type=int,
        default=5,
        help="Max search results (default: 5)",
    )
    args = parser.parse_args()

    query = args.query.strip()

    # --- Step 1: locate the paper -------------------------------------------
    arxiv_id_match = re.match(r"^(\d+\.\d+)(v\d+)?$", query)
    if arxiv_id_match:
        print(f"Input recognised as arXiv ID: {query}")
        results = [
            {"id": query, "title": f"Paper {query}", "authors": [], "summary": ""}
        ]
    else:
        print(f'Searching arXiv for: "{query}"')
        results = search_arxiv(query, args.max_results)

    if not results:
        print("No papers found.")
        sys.exit(1)

    if len(results) > 1:
        print(f"\nFound {len(results)} papers:")
        for i, r in enumerate(results):
            authors = ", ".join(r["authors"][:3])
            print(f"  [{i + 1}] {r['title']}")
            print(f"       ID: {r['id']}  |  {authors}")
        print()
        try:
            choice = int(input(f"Select paper (1–{len(results)}): ")) - 1
            if choice < 0 or choice >= len(results):
                print("Invalid choice.")
                sys.exit(1)
        except (ValueError, EOFError):
            print("Invalid input.")
            sys.exit(1)
    else:
        choice = 0

    paper = results[choice]
    paper_name = sanitize_paper_name(paper["title"])
    latex_dir = os.path.join(args.output_dir, paper_name, "latex")

    print(f"\nPaper: {paper['title']}")
    print(f"  arXiv ID : {paper['id']}")
    print(f"  Directory: {latex_dir}")

    # --- Step 2: download & extract -----------------------------------------
    try:
        download_source(paper["id"], latex_dir)
    except RuntimeError as e:
        print(f"\n  ✗ {e}")
        print("\nThis paper cannot be analyzed because LaTeX source is not available.")
        print(
            "If the paper has a GitHub repository, you can still run search_github.py"
        )
        print("and compare.py on the code alone.")
        sys.exit(1)

    # --- Step 3: save metadata ----------------------------------------------
    meta_dir = os.path.dirname(latex_dir)  # <paper_name>/
    with open(os.path.join(meta_dir, "paper.json"), "w", encoding="utf-8") as f:
        json.dump(paper, f, indent=2, ensure_ascii=False)

    print(f"\nDone. LaTeX source → {latex_dir}")
    print(f"      Metadata   → {os.path.join(meta_dir, 'paper.json')}")


if __name__ == "__main__":
    main()
