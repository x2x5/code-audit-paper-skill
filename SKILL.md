---
name: code-audit-paper
description: Given a paper title, fetches LaTeX source from arXiv and code from GitHub, then audits whether the paper exaggerates, hides details, or makes unverifiable claims — using the actual code as evidence.
---

# code-audit-paper-skill

**用代码当证据，审计论文有没有吹牛、有没有隐瞒、实验能不能复现。**

---

## 设计思路

这个技能先用便宜模型跑一版完整审计，产出一份能看的网页报告。
然后保存一份详细的交接提示词到 markdown 文件——如果用户觉得第一版审计不够深，可以拿着这份提示词，用聪明模型再做一版更深度的审计。

| 阶段 | 做什么 | 用什么模型 | 产出 |
|------|--------|-----------|------|
| **阶段一：首轮审计** | 下载论文和代码 → 自动扫描 → 四维度审计 → 生成 QA 页面 → 保存交接提示词 | 便宜模型（如 DeepSeek Flash） | 一份完整的审计报告网页 + `handoff_prompt.md` |
| **阶段二：深度重审（可选）** | 用户拿着 `handoff_prompt.md`，用聪明模型重新审计，挖得更深 | 聪明模型（如 DeepSeek Pro） | 更新后的审计报告，分析更透彻 |

**大多数情况下，阶段一的报告已经够用了。阶段二是给那些想要"第二意见"的用户准备的。**

---

# 阶段一：首轮审计（便宜模型）

**你的任务：从头到尾完成一轮完整审计，输出一份能看的报告网页，然后把交接提示词保存到 markdown 文件。**

---

## Step 0：环境检查

**任何操作之前，先检查当前环境里装了哪些工具、正确的命令名是什么。**

逐一运行以下命令，把结果记下来：

```bash
# 1. Python：到底是 python 还是 python3？
python --version 2>&1 || echo "❌ python 不可用"
python3 --version 2>&1 || echo "❌ python3 不可用"

# 2. pip：安装依赖用哪个？
pip --version 2>&1 || echo "❌ pip 不可用"
pip3 --version 2>&1 || echo "❌ pip3 不可用"

# 3. Git：克隆代码仓库需要
git --version 2>&1 || echo "❌ git 不可用"

# 4. 网络工具：curl 还是 wget？
curl --version 2>&1 | head -1 || echo "❌ curl 不可用"
wget --version 2>&1 | head -1 || echo "❌ wget 不可用"

# 5. 脚本依赖
<可用的python命令> -c "import json, os, re, sys, argparse, collections; print('✅ 核心依赖就绪')" 2>&1

# 6. 操作系统
uname -s 2>&1 || echo "Windows"
```

检查完后记清楚：**Python 命令名、pip 命令名、git 有没有、下载工具、操作系统。**

> ⚠️ **git 不可用** → 审计中止，告诉用户装 git。
>
> ⚠️ **Python 不可用** → 审计中止，告诉用户装 Python 3.8+。
>
> ⚠️ **缺少 Python 依赖包** → 用正确的 pip 命令安装。

---

## Step 1：解析输入

解析用户的输入（arXiv ID / 论文标题 / 完整 URL），确定：
- **输出目录** `<base_dir>`（默认当前工作目录下的 `audit_output/`）
- **论文名** `<paper_name>`：
  - 优先检测全大写方法缩写（如 JMVR、ResNet、ViT、DALL-E）
  - 没有明显缩写则取标题前 6 个单词，小写连字符连接

> 📌 **以下所有命令中的 `python3` 都表示你在 Step 0 中确定的正确 Python 命令。**

---

## Step 2：下载 PDF 和 LaTeX 源码

```bash
python3 scripts/fetch_arxiv.py "<query>" --output-dir <base_dir>
```

输出目录结构：

```
<base_dir>/
  <paper_name>/
    paper.pdf        # PDF（总是尝试下载）
    paper.json       # 元数据
    latex/           # LaTeX 源码（如果有）
    code/            # 代码仓库（后续步骤克隆）
```

如果论文**没有 LaTeX 源码**（arXiv 只有 PDF），在后续审计中如实标注，审计深度会受影响。

---

## Step 3：查找并克隆代码仓库

**这一步由你来做关键判断。**

先**读 LaTeX 源码**，在 `.tex` 和 `.bib` 文件中搜索 `github.com` 链接。
看链接上下文（`\href`、`\url`、周围文字），判断哪个是论文**实际的代码仓库**
（排除依赖库、数据集仓库、个人主页等）。

确定 URL 后：

```bash
python3 scripts/fetch_code.py "<query>" --output-dir <base_dir> \
    --latex-dir <base_dir>/<paper_name>/latex \
    --repo-url <确定的仓库 URL>
```

如果 LaTeX 里**没有 GitHub 链接**，先跑搜索模式：

```bash
python3 scripts/fetch_code.py "<query>" --output-dir <base_dir> \
    --latex-dir <base_dir>/<paper_name>/latex
```

脚本会搜索 GitHub 并展示结果，你从中选择合适的仓库，然后重新加上 `--repo-url` 运行。

**克隆完成后：** 检查仓库内容，确认有实际代码（不是空壳、不是纯文档）。
如果没有代码，后续审计中如实标注。

---

## Step 4：运行自动审计脚本

```bash
python3 scripts/audit.py <base_dir>/<paper_name>/latex <base_dir>/<paper_name>/code \
    --output-dir <base_dir>/<paper_name>/audit
```

生成 `audit/audit_report.html`——包含自动提取的论文概览、代码结构、交叉比对、声明详情、关键文件、审计总结（带虚线占位区域待填入）。

---

## Step 5：四维度审计

在自动分析的基础上，亲自读 LaTeX 源码和代码，完成四个维度的审计，
**把发现直接写入 `audit/audit_report.html`** 对应位置。

### Section 0：可复现性检查

检查三项，每项给 ✅ / ⚠️ / ❌：

**数据集**
- 论文用了哪些数据集？列出来
- 代码里有没有下载脚本、URL、或 README 说明？
- 代码里完全没提到的 → ⚠️

**预训练权重**
- 论文是否说用了预训练权重？
- 代码是否自动下载 / README 给了链接？
- 论文用了但代码完全没有 → ❌

**Baseline 对比方法**
- 论文跟哪些 baseline 对比？列出来
- 代码是真的实现了还是只贴了数字？

### Section 1：方法实现一致性

对照检查并写入方法对比表格：

| 论文描述 | 花哨程度 | 代码实际实现 | 结论 |
|----------|----------|-------------|------|

花哨程度：高（听起来很复杂）/ 中（有一点包装）/ 低（实话实说）

检查：整体架构、attention 机制、normalization、激活函数、多余组件、明显差异。
每个方法给 ✅ 一致 / ⚠️ 部分一致 / ❌ 不一致。

### Section 2：实验细节一致性

论文 vs 代码：
- **超参数**：learning rate、batch size、epochs、optimizer、scheduler —— 论文表格 vs 代码配置
- **数据预处理**：归一化、数据增强、图像尺寸
- **训练细节**：硬件、随机种子、训练时长
- **评估方式**：指标计算、测试集划分、后处理

### Section 3：每个实验的代码覆盖率

通读论文找出每个实验，逐个标记：

| 实验编号 | 来源章节 | 内容 | 对应 Table/Figure | 代码里有没有 | 对应文件 |

代码里找不到的 → ❌，说明该结果无法复现。

---

## Step 6：生成引言三栏解读（QA 页面）

创建 `qa/introduction.html`，将引言按自然段切分，每段一张卡片，三栏对照：

| 左栏 | 中栏 | 右栏 |
|------|------|------|
| 🔤 英文原文 | 💡 用人话说一遍 | 🀄 中文翻译 |

**"用人话说"的目标读者：** 非本领域的普通人工智能专业本科生。
术语加括号解释，用类比帮助理解，不歪曲原意。

网页要求：
- 完备 HTML，自带样式（不依赖外部 CDN）
- 浅色主题，样式参考 `audit_report.html`
- 标题简洁：`📄 引言`，无 subtitle，无 footer-note
- 每个自然段一张卡片，三栏 grid

如果用户有后续问题，在 `qa/` 下继续新建页面，同样卡片风格。

---

## Step 7：保存交接提示词到 markdown 文件

创建 `<base_dir>/<paper_name>/handoff_prompt.md`，把下面的模板填好写入：

```markdown
# 深度重审提示词 — <论文标题>

你是一位论文审计专家。你的任务是对以下论文进行**更深度的第二轮审计**，
找出第一轮可能遗漏的问题、简化了的分析、或者需要更专业判断的细节。

---

## 第一轮审计概况

- **论文标题**：<论文完整标题>
- **arXiv ID**：<arXiv ID>
- **论文目录**：<base_dir>/<paper_name>/

### 已有材料

- **LaTeX 源码**：<base_dir>/<paper_name>/latex/   <如果无，写"❌ 无">
- **代码仓库**：<base_dir>/<paper_name>/code/       <如果无，写"❌ 无">
- **第一轮审计报告**：<base_dir>/<paper_name>/audit/audit_report.html
- **论文 PDF**：<base_dir>/<paper_name>/paper.pdf

### 第一轮审计摘要

<简要总结第一轮审计的主要发现：方法匹配情况、数据集覆盖、发现的主要问题>

---

## 深度重审任务

请逐项检查第一轮报告，对以下方面进行更深度的分析：

### 1. 方法一致性 — 深挖

- 第一轮标记为 ⚠️ 的方法，请你重新逐行对比论文和代码，给出更确定的结论
- 检查是否有论文提到了但第一轮漏掉的方法细节
- 代码里有没有论文完全没提的额外组件？（有时候作者偷偷加了对结果有影响的模块）

### 2. 实验细节 — 逐项核实

- 逐一检查训练脚本里的每一个超参数，和论文的实验设置表格对比
- 数据预处理的具体实现（transform pipeline）和论文描述是否完全一致？
- 随机种子的设置是否可复现？

### 3. 实验覆盖率 — 一个不漏

- 重新通读论文，列出每一个实验（包括附录和补充材料中的）
- 逐个去代码里找对应实现
- 对于 ❌ 的实验，尝试判断是否可以通过组合现有代码来实现

### 4. 论文声明逐条验证

- 把 `audit_report.html` 中提取的每一条声明再读一遍
- 判断哪些声明是客观可验证的，哪些是主观/模糊的
- 对模糊声明给出评价（是合理简化还是刻意模糊？）

### 5. 代码质量评估

- 代码可读性、注释情况、是否有测试
- 是否容易复现？（依赖管理、Docker、安装说明等）
- 如果有训练脚本，是否可以直接跑？

---

## 输出要求

1. **直接编辑 `audit/audit_report.html`**，在第一轮审计的基础上修改/补充你的发现
2. 对于和第一轮结论不同的地方，标注 `🔍 深度重审：` 前缀
3. 更新审计总结部分，给出最终结论
4. 如果用户有新的 QA 问题，在 `qa/` 下新建对应页面
```

> 📌 保存完 `handoff_prompt.md` 后，**阶段一就完成了**。
> 告诉用户：审计报告在 `audit/audit_report.html`，可以直接浏览器打开看。
> 如果觉得审计不够深，`handoff_prompt.md` 里有交接提示词，可以复制到新窗口用聪明模型重审。

---

# 阶段二：深度重审（聪明模型，可选）

**以下是阶段二收到 `handoff_prompt.md` 后的执行流程。用户只有在觉得第一轮审计不够深的时候才会跑这个。**

阶段二的核心任务：**基于第一轮报告，做更深度的分析和验证。**

1. 打开 `audit/audit_report.html` 了解第一轮审计的所有结论
2. 按 `handoff_prompt.md` 中的 5 个深度重审任务逐一执行
3. **直接编辑 `audit/audit_report.html`**，修改/补充你的发现
4. 对于和第一轮结论不同的地方，加 `🔍 深度重审：` 前缀
5. 更新审计总结，给出最终结论

---

## 网页模板

新建 QA 页面时使用以下模板（浅色主题，三栏卡片布局）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>论文解读 — 章节名</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif;
    background: #f8fafc;
    color: #1e293b;
    line-height: 1.7;
    padding: 40px 20px;
  }
  .container { max-width: 1200px; margin: 0 auto; }
  h1 {
    font-size: 1.6rem;
    text-align: center;
    margin-bottom: 36px;
    color: #0f172a;
  }
  .card {
    background: #fff;
    border-radius: 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    margin-bottom: 28px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
  }
  .card-header {
    background: #f8fafc;
    padding: 10px 20px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #475569;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .card-body {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 0;
  }
  @media (max-width: 800px) {
    .card-body { grid-template-columns: 1fr; }
  }
  .col {
    padding: 18px 20px;
    font-size: 0.95rem;
  }
  .col-en {
    background: #fafbfc;
    border-right: 1px solid #e2e8f0;
  }
  .col-plain {
    background: #f5f3ff;
    border-right: 1px solid #e2e8f0;
  }
  .col-zh { background: #fff; }
  .col-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #888;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 2px solid #e0e0e0;
  }
  .col-en .col-label { color: #2563eb; border-color: #bfdbfe; }
  .col-plain .col-label { color: #7c3aed; border-color: #ddd6fe; }
  .col-zh .col-label { color: #c05621; border-color: #fbd38d; }
  .highlight-box {
    background: #fffbeb;
    border: 1px solid #f6e05e;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.85rem;
    color: #744210;
    margin-top: 12px;
  }
  .info-box {
    background: #eef2ff;
    border: 1px solid #a5b4fc;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.85rem;
    color: #3730a3;
    margin-top: 12px;
  }
</style>
</head>
<body>
<div class="container">

  <h1>📄 标题</h1>

  <div class="card">
    <div class="card-header">
      <span>📌 段落标题</span>
      <span style="font-size:0.8rem;color:#94a3b8;">#1</span>
    </div>
    <div class="card-body">
      <div class="col col-en">
        <div class="col-label">🔤 原文</div>
        English original text...
      </div>
      <div class="col col-plain">
        <div class="col-label">💡 用人话说</div>
        Plain-language explanation...
      </div>
      <div class="col col-zh">
        <div class="col-label">🀄 中文翻译</div>
        中文翻译...
      </div>
    </div>
  </div>

</div>
</body>
</html>
```
