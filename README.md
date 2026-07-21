# code-audit-paper

Audit academic papers: compare paper claims against actual code.  
论文代码审计：对比论文声明与实际代码实现。  

🌐 **GitHub Pages → https://x2x5.github.io/code-audit-paper**

---

## Quick Start

```bash
# Install
git clone git@github.com:x2x5/code-audit-paper.git ~/.agents/skills/code-audit-paper

# In ZCode, type
/code-audit-paper <arXiv ID or paper title>
```

## Scripts

```bash
python3 scripts/fetch_arxiv.py "<title>" -o ./output      # download LaTeX
python3 scripts/fetch_code.py "<title>" -o ./output ...   # find & clone code
python3 scripts/audit.py ...                              # audit
```

## Audit Dimensions

| # | Check |
|---|-------|
| 0 | **Reproducibility** — dataset, weights, baselines |
| 1 | **Method Consistency** — paper vs code |
| 2 | **Experiment Details** — hyperparams, preprocessing |
| 3 | **Code Coverage** — which experiments have code? |

## Design

- No LaTeX? Stop. No PDF parsing.
- No GitHub? Say so.
- Zero external deps (Python 3.6+ stdlib + git).
- Reports in Chinese. Agent judges, scripts assist.
