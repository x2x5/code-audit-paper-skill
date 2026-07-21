---
name: code-audit-paper
description: Given a paper title, fetches LaTeX source from arXiv and code from GitHub, then audits whether the paper exaggerates, hides details, or makes unverifiable claims — using the actual code as evidence.
---

# code-audit-paper-skill

**用代码当证据，审计论文有没有吹牛、有没有隐瞒、实验能不能复现。**

---

## 设计思路

技能分两个阶段。用户自己决定用什么模型跑——便宜模型做体力活也行，聪明模型追求更准也行。

| 阶段 | 做什么 | 产出 |
|------|--------|------|
| **阶段一：准备** | 环境检查 → 下载论文 → 确定目录名 → 克隆代码 | 论文 PDF + LaTeX 源码 + 代码仓库就绪 |
| **阶段二：审计** | 自动扫描 → 四维度审计 → 生成 QA 页面 → 保存交接提示词 | `audit_report.html` + QA 页面 + `handoff_prompt.md` |

阶段二末尾还有一个**可选的深度重审**——如果用户觉得首轮审计不够深，拿着 `handoff_prompt.md` 再跑一轮，产出一份更详细的 `audit_report_deep.html`（不修改原报告）。

---

# 阶段一：准备阶段

**你的任务：把论文和代码全部下载好，给论文目录起一个干净的名字。**

---

## Step 0：环境检查

**任何操作之前，先检查环境里装了哪些工具、正确的命令名是什么。**

```bash
python --version 2>&1 || echo "❌ python 不可用"
python3 --version 2>&1 || echo "❌ python3 不可用"
pip --version 2>&1 || echo "❌ pip 不可用"
pip3 --version 2>&1 || echo "❌ pip3 不可用"
git --version 2>&1 || echo "❌ git 不可用"
curl --version 2>&1 | head -1 || echo "❌ curl 不可用"
wget --version 2>&1 | head -1 || echo "❌ wget 不可用"
<可用的python命令> -c "import json, os, re, sys, argparse, collections; print('✅ 核心依赖就绪')" 2>&1
uname -s 2>&1 || echo "Windows"
```

记清楚正确的命令名。git 或 Python 不可用 → 审计中止。

> 📌 **以下所有命令中的 `python3` 都表示你在这一步确定的正确 Python 命令。**

---

## Step 1：下载 PDF 和 LaTeX 源码

解析用户输入（arXiv ID / 论文标题 / 完整 URL），然后用 arXiv API 下载。
**先不要急着定目录名——等下载完 LaTeX 源码再决定。**

```bash
python3 scripts/fetch_arxiv.py "<query>" --output-dir <base_dir>
```

下载完成后，你会得到一个以 arXiv ID 命名的临时目录。进去读 LaTeX 源码。

---

## Step 2：确定论文目录名

**目录名应该在下载好 LaTeX 源码之后再定，因为方法缩写要从源码里找。**

在 `latex/` 目录下的 `.tex` 文件中搜索方法缩写：

- 优先找论文提出的**方法名 / 模型名的全大写缩写**（如 ResNet、ViT、DALL-E、JMVR、LoRA、Diffusion）。通常在 `\title` 或摘要附近出现
- 如果没有明显的缩写，取论文标题的**前 6 个单词**，小写连字符连接（如 `toward-high-fidelity-visual-reconstruction`）
- 把临时目录重命名为这个干净的名字

```
<base_dir>/
  <paper_name>/          # ← 方法缩写 或 标题前6词
    paper.pdf
    paper.json
    latex/               # LaTeX 源码
    code/                # 代码仓库（下一步克隆）
```

如果论文**没有 LaTeX 源码**（arXiv 只有 PDF），用论文标题前 6 个单词命名，后续审计如实标注"无 LaTeX 源码"。

---

## Step 3：查找并克隆代码仓库

**这一步由你来做关键判断。**

读 LaTeX 源码，在 `.tex` 和 `.bib` 中搜索 `github.com` 链接。
看 `\href`、`\url`、周围文字，判断哪个是论文**实际的代码仓库**
（排除依赖库、数据集仓库、个人主页）。

确定 URL 后：

```bash
python3 scripts/fetch_code.py "<query>" --output-dir <base_dir> \
    --latex-dir <base_dir>/<paper_name>/latex \
    --repo-url <确定的仓库 URL>
```

LaTeX 里没有链接时，先跑搜索模式让脚本列候选，你选一个再加 `--repo-url` 运行。

克隆完检查仓库是否有实际代码。没有代码 → 后续审计如实标注。

---

# 阶段二：审计阶段

**你的任务：对论文进行四维度审计，生成报告网页和 QA 页面，保存交接提示词。**

---

## Step 4：运行自动审计脚本

```bash
python3 scripts/audit.py <base_dir>/<paper_name>/latex <base_dir>/<paper_name>/code \
    --output-dir <base_dir>/<paper_name>/audit
```

生成 `audit/audit_report.html`——含论文概览、代码结构、交叉比对、声明详情、关键文件、审计总结（带虚线占位区域）。

---

## Step 5：四维度审计

读 LaTeX 源码和代码，完成四个维度的审计，**把发现写入 `audit/audit_report.html`**。

### Section 0：可复现性检查

检查三项，每项 ✅ / ⚠️ / ❌：

**数据集** — 论文用了哪些？代码里有下载脚本/URL/README 说明？代码完全没提到的 → ⚠️

**预训练权重** — 论文说用了预训练权重吗？代码自动下载 / README 给了链接？论文用了但代码没有 → ❌

**Baseline 对比方法** — 论文跟哪些 baseline 对比？代码是真的实现了还是只贴了数字？

### Section 1：方法实现一致性

论文 Method 章节 vs 代码模型定义，对照写入方法对比表格：

| 论文描述 | 花哨程度 | 代码实际实现 | 结论 |
|----------|----------|-------------|------|

花哨程度：高（听起来很复杂）/ 中（有一点包装）/ 低（实话实说）

检查：整体架构、attention 机制、normalization、激活函数、多余组件、明显差异。
每个方法给 ✅ 一致 / ⚠️ 部分一致 / ❌ 不一致。

### Section 2：实验细节一致性

- **超参数**：learning rate、batch size、epochs、optimizer、scheduler —— 论文表格 vs 代码配置
- **数据预处理**：归一化、数据增强、图像尺寸 —— 论文描述 vs 代码实现
- **训练细节**：硬件、随机种子、训练时长 —— 论文提没提、代码提没提供
- **评估方式**：指标计算、测试集划分、后处理 —— 是否一致

### Section 3：每个实验的代码覆盖率

通读论文找出每个实验，逐个标记：

| 实验编号 | 来源章节 | 内容 | 对应 Table/Figure | 代码里有没有 | 对应文件 |

代码里找不到的 → ❌，说明该结果无法复现。

---

## Step 6：生成引言三栏解读（QA 页面）

创建 `qa/introduction.html`，引言按自然段切分，每段一张卡片，三栏：

| 左栏 | 中栏 | 右栏 |
|------|------|------|
| 🔤 英文原文 | 💡 用人话说一遍 | 🀄 中文翻译 |

**"用人话说"的目标读者：** 非本领域的普通人工智能专业本科生。术语加括号解释，用类比帮助理解。

网页要求：完备 HTML、自带样式、浅色主题、标题简洁 `📄 引言`、无 subtitle、无 footer-note。

如果用户有后续问题，在 `qa/` 下继续新建页面，同样卡片风格。

---

## Step 7：保存交接提示词

创建 `<base_dir>/<paper_name>/handoff_prompt.md`，填入以下模板：

```markdown
# 深度重审提示词 — <论文标题>

## 首轮审计概况

- **论文标题**：<论文完整标题>
- **arXiv ID**：<arXiv ID>
- **论文目录**：<base_dir>/<paper_name>/

### 已有材料

- **LaTeX 源码**：<base_dir>/<paper_name>/latex/   <如果无，写"❌ 无">
- **代码仓库**：<base_dir>/<paper_name>/code/       <如果无，写"❌ 无">
- **首轮审计报告**：<base_dir>/<paper_name>/audit/audit_report.html
- **论文 PDF**：<base_dir>/<paper_name>/paper.pdf

### 首轮审计摘要

<简要总结：方法匹配/数据集覆盖/发现的主要问题>

---

## 深度重审任务

基于首轮报告，对以下 4 个方面做更深度的分析：

### 1. 方法深挖

- 首轮标记为 ⚠️ 的方法，重新逐行对比论文和代码，给出更确定的结论
- 检查是否有论文提到了但首轮漏掉的方法细节
- 代码里有没有论文完全没提的额外组件？

### 2. 实验逐项核实

- 逐一检查训练脚本里的每个超参数，和论文实验设置表格对比
- 数据预处理的具体实现和论文描述是否完全一致？
- 随机种子的设置是否可复现？

### 3. 全覆盖扫描

- 重新通读论文，列出每一个实验（包括附录和补充材料中的）
- 逐个去代码里找对应实现
- 对于 ❌ 的实验，判断是否可以通过组合现有代码来实现

### 4. 逐条声明验证

- 把首轮报告提取的每一条声明再读一遍
- 判断哪些声明是客观可验证的，哪些是主观/模糊的
- 对模糊声明给出评价（合理简化还是刻意模糊？）

---

## 输出要求

1. **不要修改 `audit_report.html`**。新建 `audit/audit_report_deep.html` 作为深度重审报告
2. 深度报告要比首轮更详细，包含具体的代码片段引用和行号
3. 对于和首轮结论不同的地方，标注原因
4. 如果用户有新的 QA 问题，在 `qa/` 下新建对应页面
```

> 📌 保存完 `handoff_prompt.md` 后，阶段二基本完成。告诉用户：
> - 审计报告在 `audit/audit_report.html`，可以直接浏览器打开看
> - 如果想做更深度的重审，`handoff_prompt.md` 里有完整提示词，复制到新窗口即可

---

# 可选：深度重审

**用户只有在觉得首轮审计不够深的时候才会跑这个。**
用户自己选择用什么模型——聪明模型通常效果更好，但不是必须的。

收到 `handoff_prompt.md` 后，按其中的 4 项任务执行：

1. **方法深挖** — 重审每个 ⚠️，找遗漏细节，发现隐藏组件
2. **实验逐项核实** — 检查每个超参数、每个预处理步骤
3. **全覆盖扫描** — 列出每个实验（含附录），逐个找代码
4. **逐条声明验证** — 判断每条声明是可验证的还是模糊的

输出：新建 `audit/audit_report_deep.html`（不修改首轮报告），内容比首轮更详细，
包含具体的代码片段引用和行号。首轮和深度结论不同的地方标注原因。

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
