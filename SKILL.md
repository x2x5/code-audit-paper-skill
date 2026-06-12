---
name: arxiv-paper-code-analyzer
description: Given a paper title, searches arXiv for the LaTeX source, finds the corresponding code on GitHub, and analyzes whether the paper claims and experiments match the actual implementation.
---

# paper-vs-code-skill

Analyze a paper: fetch LaTeX from arXiv, find code on GitHub, and audit whether the paper's claims match the implementation.

## Workflow

### 1. Parse Input

Determine what the user provided:
- **arXiv ID** (e.g., `1706.03762`) — pass directly
- **Paper title** (e.g., `Attention Is All You Need`) — use as search query
- **Full URL** (e.g., `https://arxiv.org/abs/1706.03762`) — extract the ID

Ask the user for an output base directory, or use the current working directory.

### 2. Fetch LaTeX Source from arXiv

```bash
python3 scripts/fetch_arxiv.py "<query>" --output-dir <base_dir>
```

- The script searches arXiv by title, lets the user pick (if multiple), downloads and extracts the LaTeX source to `<paper_name>/latex/`.
- If the paper only has a PDF (no LaTeX source), the script exits with an error. Tell the user: *"This paper has no LaTeX source on arXiv, cannot analyze."* Do not attempt PDF parsing.

### 3. Find and Clone Code from GitHub

```bash
python3 scripts/fetch_code.py "<query>" --output-dir <base_dir> --latex-dir <base_dir>/<paper_name>/latex
```

The script:
1. Scans the LaTeX source for `github.com` URLs — clones directly if found
2. If no URLs found, searches GitHub by title — shows results for user selection
3. If nothing found, exits — tell the user and ask if they have a URL

On success, the repo is cloned to `<paper_name>/code/`. If no repo exists, just say so.

### 4. Run the Audit

```bash
python3 scripts/audit.py <base_dir>/<paper_name>/latex <base_dir>/<paper_name>/code --output-dir <base_dir>/<paper_name>/audit
```

This parses claims from LaTeX, analyzes code structure, cross-references them, and writes:
- `audit/analysis_report.md` — human-readable report
- `audit/analysis_data.json` — structured data

### 5. Present the Results

Read `analysis_report.md` and summarize for the user:
- Method/dataset/metric coverage
- Which experiments have code support
- Any claims not found in code
- Code quality notes (README, tests, configs, etc.)

## Output Structure

```
<paper_name>/
├── latex/          # LaTeX source from arXiv
├── code/           # Code from GitHub
├── audit/          # Audit report
│   ├── analysis_report.md
│   └── analysis_data.json
├── paper.json      # Paper metadata
└── repo.json       # Repository info
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Paper not on arXiv | Tell user, suggest they provide a URL |
| No LaTeX source (only PDF) | Report it, do not parse PDF |
| No GitHub repo found | Ask user for URL; if none, say so |
| Missing LaTeX or code | Audit cannot run, explain why |
