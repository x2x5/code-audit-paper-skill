# code-audit-paper-skill

> **[English](README.md)**

**论文代码审计：对比论文声明与实际代码实现。**

输入一个论文标题或 arXiv ID，自动去 arXiv 下载 LaTeX 源码，到 GitHub 找到对应仓库，然后从 4 个维度审计论文有没有吹牛、有没有隐瞒、实验能不能复现。

## 在 ZCode 中使用

1. **安装技能** — 克隆到技能目录：

   ```bash
   git clone git@github.com:x2x5/code-audit-paper-skill.git ~/.agents/skills/code-audit-paper
   ```

2. **触发审计** — 在 ZCode 中直接输入：

   > `/code-audit-paper <arXiv ID 或论文标题>`

   代理会自动加载技能，下载 LaTeX 源码、搜索代码仓库、执行四维度审计。

   或者直接说：

   > *"帮我审计一下 'Attention Is All You Need' 这篇论文"*

## 直接跑脚本

你也可以按顺序执行三个 Python 脚本：

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
│   ├── fetch_arxiv.py        # 按标题搜 arXiv → 下载 LaTeX 源码
│   ├── fetch_code.py         # 从 LaTeX 找 GitHub 链接 / 按标题搜 → 克隆仓库
│   └── audit.py              # 解析 LaTeX 提取 claims → 分析代码 → 出审计报告
├── templates/
│   └── report_template.md
├── README.md          # English
├── README.zh-CN.md    # 中文
└── LICENSE
```

## 输出结构

```
<论文名>/
├── latex/                      # arXiv LaTeX 源码
├── code/                       # GitHub 代码
├── audit/                      # 审计报告
│   ├── analysis_report.md      # 自动生成的 Markdown 报告
│   ├── analysis_data.json      # 结构化数据
│   ├── full_audit_report.md    # 完整手动审计报告（Section 0–3）
│   └── method_vs_code.md       # 逐方法对比表格
├── qa/                         # QA 问答网页（卡片式 HTML）
│   └── introduction.html       # 示例：引言三栏对照解读
├── paper.json                  # 论文元数据
└── repo.json                   # 仓库信息
```

## 四个审计维度

| 维度 | 检查内容 |
|------|----------|
| **0. 可复现性** | 数据集能否获取？预训练权重有没有？baseline 有没有实现？ |
| **1. 方法一致性** | 论文描述的方法和代码里的实现是不是一回事？ |
| **2. 实验细节** | 超参数、数据预处理、评估方式——论文说的和代码配置一致吗？ |
| **3. 代码覆盖率** | 论文做了哪些实验，哪些实验在代码里真的有对应实现？ |

## QA 问答模块

审计完成后，你可以继续追问论文相关的任何问题。每个问题都会生成一个独立的 HTML 页面，按自然段切分成卡片展示。

对于论文解读类问题，每张卡片分三栏：

| 左栏 | 中栏 | 右栏 |
|------|------|------|
| 🔤 英文原文 | 🀄 中文翻译 | 💡 用人话说一遍 |

"用人话说"的目标读者是**普通人工智能专业本科生**——遇到术语会加括号解释，用类比帮助理解，不歪曲原意。

新问题随时可以添加，每个问题对应 `qa/` 下的一个新 `.html` 文件。

## 设计原则

- **没有 LaTeX 源码？** 停止，不解析 PDF。
- **搜不到 GitHub？** 如实告诉用户，不强行找。
- **零外部依赖**，只要 Python 3.6+ 和 git。
- **所有报告用中文写**，易读易懂。
- **代理（agent）做判断**，脚本只是辅助工具。代理亲自读 LaTeX 和代码，给出准确判断。
