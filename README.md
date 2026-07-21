# code-audit-paper-skill

**Audit academic papers: compare paper claims against actual code.**

**论文代码审计：对比论文声明与实际代码实现。**

---

Given a paper title, this skill fetches the LaTeX source from arXiv, finds the corresponding repository on GitHub, and analyzes whether the paper's claims and experiments match the actual implementation.

输入论文标题或 arXiv ID，自动去 arXiv 下载 LaTeX 源码，到 GitHub 找对应仓库，然后从 4 个维度审计论文有没有吹牛、有没有隐瞒、实验能不能复现。

## How to Use in ZCode / 在 ZCode 中使用

**Install** — clone into your skills directory:
**安装** — 克隆到技能目录：

```bash
git clone git@github.com:x2x5/code-audit-paper-skill.git ~/.agents/skills/code-audit-paper
```

**Invoke** — in ZCode, type `/code-audit-paper <arXiv ID or paper title>`, or just say *"Audit the paper 'Attention Is All You Need'"*.
**触发** — 在 ZCode 中输入 `/code-audit-paper <arXiv ID 或论文标题>`，或直接说 *"帮我审计一下 'Attention Is All You Need'"*。

## Run Standalone Scripts / 直接跑脚本

```bash
# 1. Fetch LaTeX source from arXiv / 从 arXiv 下载 LaTeX 源码
python3 scripts/fetch_arxiv.py "<paper-title>" -o ./output

# 2. Find and clone code from GitHub / 从 GitHub 获取代码
python3 scripts/fetch_code.py "<paper-title>" -o ./output -l ./output/<paper-name>/latex

# 3. Audit paper claims vs code / 对比审计
python3 scripts/audit.py ./output/<paper-name>/latex ./output/<paper-name>/code \
    -o ./output/<paper-name>/audit
```

## Directory Structure / 目录结构

```
code-audit-paper-skill/
├── SKILL.md                  # ZCode skill definition / skill 定义
├── scripts/
│   ├── fetch_arxiv.py        # Search arXiv → download LaTeX / 搜 arXiv → 下载 LaTeX
│   ├── fetch_code.py         # Find GitHub URL / search by title → clone / 找 GitHub 链接或搜标题 → 克隆
│   └── audit.py              # Parse claims → analyze code → generate report / 提取声明 → 分析代码 → 出报告
├── templates/
├── README.md
└── LICENSE
```

## Output Structure / 输出结构

```
<paper_name>/           # Method abbreviation or first 6 words of title / 方法缩写或标题前6词
├── latex/              # LaTeX source from arXiv
├── code/               # Code from GitHub (if available)
├── audit/              # Audit report / 审计报告
│   ├── analysis_report.md
│   ├── analysis_data.json
│   ├── full_audit_report.md     # Manual audit (Sections 0–3) / 完整手动审计
│   └── method_vs_code.md        # Method-by-method comparison / 逐方法对比
├── qa/                 # Q&A pages — card-style HTML / 问答网页
│   └── introduction.html        # Three-column interpretation / 三栏解读
├── paper.json
└── repo.json
```

## Audit Dimensions / 四个审计维度

**0. Reproducibility / 可复现性** — Dataset accessibility, pretrained weights, baseline implementations / 数据集能获取吗？预训练权重有吗？baseline 有实现吗？

**1. Method Consistency / 方法一致性** — Does the code match the paper's architecture description? / 论文说的和代码写的是不是一回事？

**2. Experiment Details / 实验细节** — Hyperparameters, preprocessing, evaluation — paper vs code / 超参数、预处理、评估方式——论文 vs 代码一致吗？

**3. Code Coverage / 代码覆盖率** — Which experiments actually have corresponding code? / 哪些实验真的有对应代码？

## Q&A Module / QA 问答模块

After the audit, you can ask follow-up questions. Each question becomes a self-contained HTML page with paragraph-by-paragraph cards. For interpretation questions, each card has three columns:

审计完成后可以继续追问。每个问题生成独立 HTML 页面，按自然段切卡片。解读类问题每张卡片三栏：

| Left / 左栏 | Middle / 中栏 | Right / 右栏 |
|------|--------|-------|
| 🔤 English original / 英文原文 | 💡 Plain-language explanation / 用人话说 | 🀄 Chinese translation / 中文翻译 |

The plain-language column targets AI undergraduates outside this niche field — jargon gets parenthetical explanations, analogies help understanding.

"用人话说"的目标读者是普通 AI 本科生——术语加括号解释，用类比帮助理解。

## Design Philosophy / 设计原则

- **No LaTeX source?** Stop. No PDF parsing. / **没有 LaTeX？** 停止，不解析 PDF。
- **No GitHub repo?** Tell the user honestly. / **搜不到 GitHub？** 如实告诉用户。
- **Zero external dependencies.** Python 3.6+ stdlib only, plus git. / **零外部依赖**，只要 Python 3.6+ 和 git。
- **Reports in Chinese.** Easy to read. / **报告用中文写**，易读易懂。
- **Agent does the judgment.** Scripts assist; the agent reads the LaTeX and code. / **代理做判断**，脚本只是辅助。
