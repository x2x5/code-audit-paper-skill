# paper-code-audit-skill

> **[中文版](README.zh-CN.md)**

**Audit academic papers: compare paper claims against actual code.**

Given a paper title, this tool fetches the LaTeX source from arXiv, finds the corresponding repository on GitHub, and analyzes whether the paper's claims and experiments match the actual implementation.

## Two Ways to Use

### A. As a Zed Agent Skill (recommended)

1. Clone the repo to the skills directory:
   ```bash
   git clone https://github.com/YOUR_USER/paper-code-audit-skill.git ~/.agents/skills/paper-code-audit-skill
   ```
2. Restart Zed, then ask the agent:
   > *"Analyze the paper 'Attention Is All You Need'"*

   The agent will automatically load the skill and walk through the steps.

### B. As Standalone Scripts

Run the three Python scripts directly in order:

```bash
# 1. Fetch LaTeX source from arXiv
python3 scripts/fetch_arxiv.py "<paper-title>" -o ./output

# 2. Find and clone code from GitHub
python3 scripts/fetch_code.py "<paper-title>" -o ./output -l ./output/<paper-name>/latex

# 3. Audit paper claims vs code
python3 scripts/audit.py ./output/<paper-name>/latex ./output/<paper-name>/code -o ./output/<paper-name>/audit
```

## Directory Structure

```
paper-code-audit-skill/
├── SKILL.md                  # Zed Agent skill definition
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
│   └── analysis_data.json      # Structured data for further processing
├── paper.json                  # Paper metadata
└── repo.json                   # Repository info
```

## Design Philosophy

- **No LaTeX source?** Stop. No PDF parsing. If you need it, provide a PDF and use MinerU to convert to Markdown.
- **No GitHub repo found?** Tell the user. If the paper has no code, just say so.
- **Zero external dependencies.** Python 3.6+ standard library only, plus git.
