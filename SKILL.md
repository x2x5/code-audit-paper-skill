---
name: arxiv-paper-code-analyzer
description: Given a paper title, searches arXiv for the LaTeX source, finds the corresponding code on GitHub, and analyzes whether the paper claims and experiments match the actual implementation.
---

# paper-vs-code-skill

Download LaTeX from arXiv, find the code on GitHub, then audit the paper across 4 dimensions.

## Workflow

### 0. Prepare

Parse the user's input (arXiv ID / paper title / URL), ask for an output directory, then run the three scripts in order:

```bash
python3 scripts/fetch_arxiv.py "<query>" --output-dir <base_dir>
python3 scripts/fetch_code.py "<query>" --output-dir <base_dir> --latex-dir <base_dir>/<paper_name>/latex
python3 scripts/audit.py <base_dir>/<paper_name>/latex <base_dir>/<paper_name>/code --output-dir <base_dir>/<paper_name>/audit
```

The `audit.py` script generates a preliminary report with automated analysis (claims extracted, code structure, keyword matching). Read it to get started. Then go through the 4 sections below manually — the automated report is just a starting point, you need to inspect the actual LaTeX and code to give accurate answers.

---

### Section 0: Reproducibility Check

Check these three things and report ✅ / ⚠️ / ❌ for each:

#### Datasets
- Read the paper's experiment sections → list every dataset used
- Look in the code for download scripts, dataset URLs, or README instructions
- If a dataset is missing from code → ⚠️ flag it

#### Pretrained Weights
- Does the paper say they used pretrained weights?
- Are the weights auto-downloaded in the code? Is there a link in README?

#### Baselines
- Which baselines does the paper compare against?
- Does the code include implementations of those baselines, or just compare numbers?

---

### Section 1: Method Implementation

Compare what the paper says about the architecture vs what the code actually builds.

Read the Method / Architecture section in the LaTeX, then look at the model definition code:

- Does the code implement the same **architecture** described in the paper? (backbone, modules, components)
- Are the **key design choices** reflected? (attention mechanism, normalization, activation functions, etc.)
- Are there any **significant deviations**? (paper describes one thing, code does another)
- Are there **extra components** in code that the paper doesn't mention?

For each method/section identified, give a conclusion: ✅ matches / ⚠️ partial / ❌ differs.

---

### Section 2: Experiment Reproducibility

Compare the experimental setup described in the paper vs the actual configuration in the code.

Check these:

- **Hyperparameters**: learning rate, batch size, epochs, optimizer, scheduler, weight decay, dropout — look in paper tables vs code config files
- **Data preprocessing**: normalization, augmentation, image size — described in paper vs implemented
- **Training details**: hardware, random seed, training time — mentioned vs provided
- **Evaluation protocol**: metrics calculation, test splits, post-processing — consistent?

---

### Section 3: Experiment Coverage

Map every experiment in the paper to code.

- Read the paper → count tables and experiment figures
- Look at the code → find the corresponding scripts for each experiment
- For each table/figure, determine if the code supports reproducing it

Report as:
| # | Table / Figure | Topic | Code Found? | Script / Config |
|---|---|---|---|---|
| Table 1 | Main results on ImageNet | Classification accuracy | ✅ | `scripts/eval.py` |
| Table 2 | Ablation on depth | Layer count study | ⚠️ | Configs exist but no automation |
| Figure 3 | Convergence curve | Training loss over time | ❌ | No plotting code |

---

### Present the Results

After going through all 4 sections, give the user a clear summary:

```
## Summary

### Section 0: Reproducibility
- Datasets: 3/3 provided ✅
- Weights: auto-downloaded ✅
- Baselines: 2/5 implemented ⚠️

### Section 1: Method Implementation
- Architecture matches ✅
- Attention mechanism differs from paper ❌
  → Paper describes multi-head attention with 8 heads, code uses 12 heads

### Section 2: Experiment Reproducibility
- Hyperparameters match paper ✅
- Data augmentation differs ⚠️
  → Paper uses RandomResizedCrop, code uses CenterCrop

### Section 3: Experiment Coverage
- 5/7 tables have corresponding code ⚠️
- 2/4 figures have corresponding code ⚠️
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Paper not on arXiv | Tell user, ask for URL |
| No LaTeX source (only PDF) | Report it, stop |
| No GitHub repo found | Ask user for URL |
| Missing LaTeX or code | Can't audit, explain why |
