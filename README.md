# code-audit-paper-skill

**Audit academic papers: compare paper claims against actual code.**

Given a paper title, this skill fetches the LaTeX source from arXiv, finds the corresponding repository on GitHub, and analyzes whether the paper's claims and experiments match the actual implementation.

---

## How to Use in ZCode

1. **Install** — clone into your skills directory:

   ```bash
   git clone git@github.com:x2x5/code-audit-paper-skill.git ~/.agents/skills/code-audit-paper
   ```

2. **Invoke** — in ZCode, type `/code-audit-paper <arXiv ID or paper title>`, or just say:

   > *"Audit the paper 'Attention Is All You Need'"*

## Run Standalone Scripts

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
│   ├── fetch_arxiv.py        # Search arXiv → download LaTeX source
│   ├── fetch_code.py         # Find GitHub URL / search by title → clone repo
│   └── audit.py              # Parse claims → analyze code → generate report
├── templates/
├── README.md
└── LICENSE
```

## Output Structure

```
<paper_name>/           # Named after method abbreviation or first 6 words of title
├── latex/              # LaTeX source from arXiv
├── code/               # Code from GitHub (if available)
├── audit/              # Audit report
│   ├── analysis_report.md
│   ├── analysis_data.json
│   ├── full_audit_report.md    # Manual audit (Sections 0–3)
│   └── method_vs_code.md       # Method-by-method comparison
├── qa/                 # Q&A pages — card-style HTML
│   └── introduction.html       # Three-column interpretation of the Introduction
├── paper.json
└── repo.json
```

## Audit Dimensions

| Section | What it checks |
|---------|----------------|
| **0. Reproducibility** | Dataset accessibility, pretrained weights, baseline implementations |
| **1. Method Consistency** | Does the code match the paper's architecture description? |
| **2. Experiment Details** | Hyperparameters, preprocessing, evaluation — paper vs code |
| **3. Code Coverage** | Which experiments actually have corresponding code? |

## Q&A Module

After the audit, you can ask follow-up questions. Each question becomes a self-contained HTML page with paragraph-by-paragraph cards. For interpretation questions, each card has three columns:

| Left | Middle | Right |
|------|--------|-------|
| 🔤 English original | 💡 Plain-language explanation | 🀄 Chinese translation |

The plain-language column targets **AI undergraduates** outside this niche field — jargon gets parenthetical explanations, analogies help understanding.

## Design Philosophy

- **No LaTeX source?** Stop. No PDF parsing.
- **No GitHub repo?** Tell the user honestly.
- **Zero external dependencies.** Python 3.6+ stdlib only, plus git.
- **Reports in Chinese.** Easy to read.
- **Agent does the judgment.** Scripts assist; the agent reads the LaTeX and code.

---

---

# code-audit-paper-skill

**论文代码审计：对比论文声明与实际代码实现。**

输入论文标题或 arXiv ID，自动去 arXiv 下载 LaTeX 源码，到 GitHub 找对应仓库，然后从 4 个维度审计论文有没有吹牛、有没有隐瞒、实验能不能复现。

---

## 在 ZCode 中使用

1. **安装** — 克隆到技能目录：

   ```bash
   git clone git@github.com:x2x5/code-audit-paper-skill.git ~/.agents/skills/code-audit-paper
   ```

2. **触发** — 在 ZCode 中输入 `/code-audit-paper <arXiv ID 或论文标题>`，或直接说：

   > *"帮我审计一下 'Attention Is All You Need'"*

## 直接跑脚本

```bash
# 1. 从 arXiv 下载 LaTeX 源码
python3 scripts/fetch_arxiv.py "<论文标题>" -o ./output

# 2. 从 GitHub 获取代码
python3 scripts/fetch_code.py "<论文标题>" -o ./output -l ./output/<论文名>/latex

# 3. 对比审计
python3 scripts/audit.py ./output/<论文名>/latex ./output/<论文名>/code \
    -o ./output/<论文名>/audit
```

## 目录结构

```
code-audit-paper-skill/
├── SKILL.md                  # ZCode skill 定义
├── scripts/
│   ├── fetch_arxiv.py        # 搜 arXiv → 下载 LaTeX
│   ├── fetch_code.py         # 找 GitHub 链接 / 搜标题 → 克隆
│   └── audit.py              # 提取声明 → 分析代码 → 出报告
├── templates/
├── README.md
└── LICENSE
```

## 输出结构

```
<论文名>/           # 方法缩写或标题前6词
├── latex/          # arXiv LaTeX 源码
├── code/           # GitHub 代码（如有）
├── audit/          # 审计报告
│   ├── analysis_report.md
│   ├── analysis_data.json
│   ├── full_audit_report.md     # 完整手动审计（Section 0–3）
│   └── method_vs_code.md        # 逐方法对比
├── qa/             # QA 问答网页（卡片式 HTML）
│   └── introduction.html        # 引言三栏对照解读
├── paper.json
└── repo.json
```

## 四个审计维度

| 维度 | 检查内容 |
|------|----------|
| **0. 可复现性** | 数据集能获取吗？预训练权重有吗？baseline 有实现吗？ |
| **1. 方法一致性** | 论文说的和代码写的是不是一回事？ |
| **2. 实验细节** | 超参数、预处理、评估方式——论文 vs 代码一致吗？ |
| **3. 代码覆盖率** | 哪些实验真的有对应代码？ |

## QA 问答模块

审计完成后可以继续追问。每个问题生成独立 HTML 页面，按自然段切卡片。解读类问题每张卡片三栏：

| 左栏 | 中栏 | 右栏 |
|------|------|------|
| 🔤 英文原文 | 💡 用人话说一遍 | 🀄 中文翻译 |

"用人话说"的目标读者是**普通 AI 本科生**——术语加括号解释，用类比帮助理解。

## 设计原则

- **没有 LaTeX？** 停止，不解析 PDF。
- **搜不到 GitHub？** 如实告诉用户。
- **零外部依赖**，只要 Python 3.6+ 和 git。
- **报告用中文写**，易读易懂。
- **代理（agent）做判断**，脚本只是辅助。
