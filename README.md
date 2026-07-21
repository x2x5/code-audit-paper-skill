# code-audit-paper-skill

> **[中文版](README.zh-CN.md)**

**Audit academic papers: compare paper claims against actual code.**

Given a paper title, this skill fetches the LaTeX source from arXiv, finds the corresponding repository on GitHub, and analyzes whether the paper's claims and experiments match the actual implementation.

## How to Use in ZCode

1. **Install the skill** — clone the repo into your skills directory:

   ```bash
   git clone git@github.com:x2x5/code-audit-paper-skill.git ~/.agents/skills/code-audit-paper
   ```

2. **Invoke it** — in ZCode, just type:

   > `/code-audit-paper <arXiv ID or paper title>`

   The agent automatically loads the skill, downloads the LaTeX source, searches for the code repo, and runs a comprehensive audit across four dimensions.

   Or simply describe what you want:

   > *"Audit the paper 'Attention Is All You Need'"*

## Run Standalone Scripts

You can also run the three Python scripts directly:

```bash
# 1. Fetch LaTeX source from arXiv
python3 scripts/fetch_arxiv.py "<paper-title>" -o ./output

# 2. Find and clone code from GitHub
python3 scripts/fetch_code.py "<paper-title>" -o ./output -l ./output/<paper-name>/latex

# 3. Audit paper claims vs code
python3 scripts/audit.py ./output/<paper-name>/latex ./output/<paper-name>/code \
    -o ./output/<paper-name>/audit
```

## Directory Structure

```
code-audit-paper-skill/
├── SKILL.md                  # ZCode skill definition
├── scripts/
│   ├── fetch_arxiv.py        # Search arXiv by title → download LaTeX source
│   ├── fetch_code.py         # Find GitHub URL in LaTeX / search by title → clone repo
│   └── audit.py              # Parse LaTeX claims → analyze code → generate audit report
├── templates/
│   └── report_template.md
├── README.md          # English
├── README.zh-CN.md    # 中文
└── LICENSE
```

## Output Structure

```
<paper_name>/
├── latex/                      # LaTeX source from arXiv
├── code/                       # Code from GitHub
├── audit/                      # Audit report
│   ├── analysis_report.md      # Readable Markdown report
│   ├── analysis_data.json      # Structured data for further processing
│   ├── full_audit_report.md    # Comprehensive manual audit (Sections 0–3)
│   └── method_vs_code.md       # Method-by-method comparison table
├── qa/                         # Q&A pages (card-style HTML)
│   └── introduction.html       # Example: three-column interpretation
├── paper.json                  # Paper metadata
└── repo.json                   # Repository info
```

## What Gets Audited

| Section | What it checks |
|---------|----------------|
| **0. Reproducibility** | Dataset availability, pretrained weights, baseline implementations |
| **1. Method Consistency** | Does the code match the paper's architecture description? |
| **2. Experiment Details** | Hyperparameters, preprocessing, evaluation — paper vs config |
| **3. Code Coverage** | Which experiments actually have corresponding code? |

## Q&A Module

After the audit, you can ask follow-up questions about the paper. Each question is answered as a self-contained HTML page with paragraph-by-paragraph cards. For interpretation questions, each card shows:

- **Left column:** English original
- **Middle column:** Plain-language explanation (for non-specialist AI undergraduates)
- **Right column:** Chinese translation

New questions can be added at any time as new `.html` files in the `qa/` directory.

## Design Philosophy

- **No LaTeX source?** Stop. No PDF parsing.
- **No GitHub repo found?** Tell the user honestly.
- **Zero external dependencies.** Python 3.6+ standard library only, plus git.
- **All reports in Chinese.** Easy to read for a Chinese-speaking audience.
- **Agent does the thinking.** The scripts are assistants; the agent reads the LaTeX and code to make judgment calls.
