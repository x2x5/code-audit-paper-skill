# paper-code-audit-skill

> **[English](README.md)**

**论文代码审计：对比论文声明与实际代码实现。**

输入一个论文标题，自动去 arXiv 下载 LaTeX 源码，到 GitHub 找到对应仓库，然后分析论文里说的和代码里写的是不是一致。

## 两种使用方式

### A. 作为 Zed Agent Skill（推荐）

1. 把仓库克隆到 skills 目录下：
   ```bash
   git clone https://github.com/YOUR_USER/paper-code-audit-skill.git ~/.agents/skills/paper-code-audit-skill
   ```
2. 重启 Zed，然后对代理说：
   > *"帮我分析一下 'Attention Is All You Need' 这篇论文"*

   代理会自动加载 skill，按步骤执行。

### B. 直接跑脚本

按顺序执行三个 Python 脚本：

```bash
# 1. 从 arXiv 下载 LaTeX 源码
python3 scripts/fetch_arxiv.py "<论文标题>" -o ./output

# 2. 从 GitHub 获取代码
python3 scripts/fetch_code.py "<论文标题>" -o ./output -l ./output/<论文名>/latex

# 3. 对比审计
python3 scripts/audit.py ./output/<论文名>/latex ./output/<论文名>/code -o ./output/<论文名>/audit
```

## 目录结构

```
paper-code-audit-skill/
├── SKILL.md                  # Zed Agent skill 定义
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
<paper_name>/
├── latex/                      # arXiv LaTeX 源码
├── code/                       # GitHub 代码
├── audit/                      # 审计报告
│   ├── analysis_report.md      # 可读的 Markdown 报告
│   └── analysis_data.json      # 结构化数据
├── paper.json                  # 论文元数据
└── repo.json                   # 仓库信息
```

## 设计原则

- **没有 LaTeX 源码？** 停止，不解析 PDF。将来需要的话，用户提供 PDF + MinerU 转 Markdown 再分析。
- **搜不到 GitHub？** 告诉用户。论文没代码就说没有。
- **零外部依赖**，只要 Python 3.6+ 和 git。
