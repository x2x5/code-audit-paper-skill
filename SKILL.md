---
name: code-audit-paper
description: Given a paper title, fetches LaTeX source from arXiv and code from GitHub, then audits whether the paper exaggerates, hides details, or makes unverifiable claims — using the actual code as evidence.
---

# code-audit-paper-skill

**用代码当证据，审计论文有没有吹牛、有没有隐瞒、实验能不能复现。**

---

## 两阶段设计

这个技能分成两个阶段，**用不同的模型做不同的事**：

| 阶段 | 做什么 | 用什么模型 | 为什么 |
|------|--------|-----------|--------|
| **阶段一：准备** | 环境检查、下载论文、克隆代码、跑自动脚本 | 便宜模型（如 DeepSeek Flash） | 纯体力活，不需要深度理解，便宜模型完全够用 |
| **阶段二：分析** | 读论文、读代码、四维度深度审计、生成 QA 页面 | 聪明模型（如 DeepSeek Pro） | 需要理解论文内容、对比代码细节、做专业判断 |

**阶段一跑完后，会输出一段"交接提示词"。你复制它，开一个新窗口，切换聪明模型，粘贴过去，阶段二就自动接上了。**

---

# 阶段一：准备阶段（便宜模型）

**你的任务：把所有需要的文件下载好，自动脚本跑完，然后停下来，输出交接提示词。**
**不要做任何深度分析——那是阶段二的事。**

---

## Step 0：环境检查

**任何操作之前，先检查当前环境里装了哪些工具、正确的命令名是什么。**
不同系统差异很大（`python` vs `python3`、`pip` vs `pip3`、有没有 `git`、有没有 `curl`），
不检查就直接跑命令会导致无谓的报错。

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

# 4. 网络工具：curl 还是 wget？（下载文件用，至少有一个就行）
curl --version 2>&1 | head -1 || echo "❌ curl 不可用"
wget --version 2>&1 | head -1 || echo "❌ wget 不可用"

# 5. 脚本依赖：audit 脚本需要哪些 Python 包？
<可用的python命令> -c "import json, os, re, sys, argparse, collections; print('✅ 核心依赖就绪')" 2>&1

# 6. 操作系统
uname -s 2>&1 || echo "Windows"
```

检查完后，记清楚：
- **Python 命令**是 `python` 还是 `python3`？（后续所有脚本用这个）
- **pip 命令**是 `pip` 还是 `pip3`？
- **Git 有没有**？（没有 → 审计中止）
- **下载工具**用 `curl` 还是 `wget`？
- **操作系统**是 macOS / Linux / Windows？

> ⚠️ **git 不可用**：告诉用户"需要安装 git 才能克隆代码仓库"，审计中止。
>
> ⚠️ **Python 不可用**：告诉用户"需要安装 Python 3.8+ 才能运行审计脚本"，审计中止。
>
> ⚠️ **缺少 Python 依赖包**：用正确的 pip 命令安装。

---

## Step 1：解析输入

解析用户的输入（arXiv ID / 论文标题 / 完整 URL），确定：
- **输出目录** `<base_dir>`（默认当前工作目录下的 `audit_output/`）
- **论文名** `<paper_name>`：
  - 优先检测论文标题中的全大写方法缩写（如 JMVR、ResNet、ViT、DALL-E），用它做目录名
  - 如果没有明显的缩写，取论文标题的**前 6 个单词**，小写用连字符连接（如 `toward-high-fidelity-visual-reconstruction`）

> 📌 **以下所有命令中的 `python3` 都表示你在 Step 0 中确定的正确 Python 命令。**
> 同理 `git`、`pip`、`curl` 也要用正确的命令名。

---

## Step 2：下载 PDF 和 LaTeX 源码

先下载 PDF（arXiv 上几乎总是有），再下载 LaTeX 源码。
如果论文只有 PDF 没有 LaTeX 源码，PDF 也会被保留下来。

```bash
python3 scripts/fetch_arxiv.py "<query>" --output-dir <base_dir>
```

输出目录结构：

```
<base_dir>/
  <paper_name>/                      # 方法缩写 or 标题前6词
    paper.pdf        # PDF（总是尝试下载）
    paper.json       # 元数据
    latex/           # LaTeX 源码（如果有）
    code/            # 代码仓库（后续步骤）
```

如果论文**没有 LaTeX 源码**（arXiv 只有 PDF），跳到 Step 5 输出交接提示词，
在提示词中注明"无 LaTeX 源码，无法深度审计"。

---

## Step 3：查找并克隆代码仓库

**这一步由你来做关键判断。**

先**读 LaTeX 源码**，在 `.tex` 和 `.bib` 文件中搜索 `github.com` 链接。
看链接的上下文（`\href`、`\url`、周围文字），判断哪个是论文**实际的代码仓库**
（排除依赖库、数据集仓库、个人主页等）。

确定 URL 后，用 `--repo-url` 参数运行 fetch_code.py：

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

脚本会扫描 LaTeX、搜索 GitHub 并展示结果。你从中选择合适的仓库，
然后重新加上 `--repo-url` 运行。

**克隆完成后：** 检查仓库内容，判断它是不是有实际代码的论文复现仓库
（而不是空壳项目、个人主页、或纯文档项目）。
如果不是 → 跳到 Step 5，在交接提示词中注明。

---

## Step 4：运行自动审计脚本

```bash
python3 scripts/audit.py <base_dir>/<paper_name>/latex <base_dir>/<paper_name>/code \
    --output-dir <base_dir>/<paper_name>/audit
```

这会生成 `audit/audit_report.html`——一个自包含的 HTML 网页（浏览器直接打开即可查看），
内容包括自动提取的论文概览、代码结构、交叉比对、声明详情、关键文件、审计总结。
JSON 数据也嵌入在 HTML 的 `<script>` 标签中。

---

## Step 5：停下来，输出交接提示词

**你（阶段一）的任务到此结束。不要做任何深度分析。**

现在你需要输出一段**交接提示词**，让用户复制后，在新窗口里贴给聪明模型（如 DeepSeek Pro）。
提示词必须自包含——新模型的会话没有任何上下文，全凭这段提示词接上。

### 交接提示词模板

把下面的 `<...>` 占位符全部替换为实际内容后输出：

```
你是一位论文审计专家。你的任务是深度审计一篇学术论文，检查论文的声明是否和代码一致、
实验是否可以复现、有没有夸大或隐瞒。

---

## 已完成的准备工作

以下材料已经下载好，你不需要重新下载：

- **论文标题**：<论文完整标题>
- **arXiv ID**：<arXiv ID>
- **论文目录**：<base_dir>/<paper_name>/
- **LaTeX 源码**：<base_dir>/<paper_name>/latex/   <如果无LaTeX源码，写"❌ 无 LaTeX 源码，仅有 PDF">
- **代码仓库**：<base_dir>/<paper_name>/code/       <如果无代码，写"❌ 无代码仓库">
- **自动审计报告**：<base_dir>/<paper_name>/audit/audit_report.html
- **论文 PDF**：<base_dir>/<paper_name>/paper.pdf
- **论文元数据**：<base_dir>/<paper_name>/paper.json

<如果 paper.json 有内容，把摘要粘贴过来>

## 自动扫描摘要

<简要列出 audit_report.html 中的关键数据：方法数、数据集数、声明数、代码语言和文件数、能力检测结果>

---

## 你需要做的事

请按以下顺序完成深度审计。每一步的结果请直接写入 `audit/audit_report.html`
对应 section 的预留位置中（该 HTML 文件底部有虚线占位区域）。

### 1. 先读完所有材料

- 打开 `audit/audit_report.html` 了解自动分析结果
- 通读 LaTeX 源码（重点：摘要、引言、方法、实验）
- 浏览代码仓库结构和关键文件

### 2. Section 0：可复现性检查

检查三项，每项给 ✅ / ⚠️ / ❌，把结果写入 audit_report.html：

**数据集**
- 论文实验里用了哪些数据集？列出来
- 代码里有没有提供下载脚本、数据集 URL、或者 README 里写了怎么下载？
- 如果某个数据集在代码里完全没提到 → ⚠️

**预训练权重**
- 论文里有没有说用了预训练权重？
- 代码里是自动下载权重？还是 README 里给了链接？
- 如果论文用了但代码里完全没有 → ❌

**Baseline 对比方法**
- 论文跟哪些 baseline 做了对比？列出来
- 代码里是真的实现了这些 baseline，还是只贴了个数字？

### 3. Section 1：方法实现一致性

把论文里的每个方法/模块描述和代码里的实际实现对照，写入 audit_report.html 的方法对比表格：

| 论文描述 | 花哨程度 | 代码实际实现 | 结论 |
|----------|----------|-------------|------|

花哨程度分三档：高（听起来很复杂）/ 中（有一点点包装）/ 低（实话实说）

检查项：整体架构、attention 机制、normalization、激活函数、多余组件、明显差异。

### 4. Section 2：实验细节一致性

对照检查并写入 audit_report.html：
- **超参数**：learning rate、batch size、epochs、optimizer、scheduler —— 论文表格 vs 代码配置
- **数据预处理**：归一化、数据增强、图像尺寸 —— 论文描述 vs 代码实现
- **训练细节**：硬件、随机种子、训练时长 —— 论文提没提、代码提没提供
- **评估方式**：指标计算方式、测试集划分、后处理 —— 是否一致

### 5. Section 3：每个实验的代码覆盖率

通读论文找出每一个实验，写入 audit_report.html 的实验对照表：

| 实验编号 | 来源章节 | 内容 | 对应 Table/Figure | 代码里有没有 | 对应文件 |

如果论文某个实验没有对应代码 → 标记 ❌，说明这个实验结果在代码里无法复现。

### 6. 更新审计总结

修改 audit_report.html 底部的总结 section，把自动分析结果替换为完整的四维度审计结论。

### 7. 生成引言三栏解读

创建 `qa/introduction.html`，将引言按自然段切分，每段一张卡片，每张卡片三栏：

| 左栏 | 中栏 | 右栏 |
|------|------|------|
| 🔤 英文原文 | 💡 用人话说一遍 | 🀄 中文翻译 |

"用人话说"的目标读者：非本领域的普通人工智能专业本科生。
遇到术语要加括号解释，用类比帮助理解，不歪曲原意。

网页要求：
- 完备的 HTML，自带样式（不要依赖外部 CDN）
- 浅色主题，样式参考 audit_report.html
- 标题简洁：`📄 引言`
- 不要 subtitle（不需要论文全名 + arXiv ID 副标题）
- 不要 footer-note
- 每个自然段一张卡片（card），卡片 body 三栏 grid

---

## 后续

如果你对这篇论文还有更多问题，请继续问我。我会在 `qa/` 目录下新建对应的问题页面。
```

> ⚠️ **阶段一到这里就结束了**。用户会复制上面的提示词，在新窗口用聪明模型继续。
> 你不要自己做 Section 0-3 的深度分析，不要生成引言解读页面——那些是阶段二的事。

---

# 阶段二：深度分析阶段（聪明模型）

**以下是阶段二收到交接提示词后的执行流程，写在 SKILL.md 里供参考。**

阶段二模型打开交接提示词后，按提示词中的 7 个任务顺序执行即可。
这里补充一些执行细节。

---

## 开始之前

阶段二不需要再做环境检查——所有文件已在阶段一下载好。
直接从提示词中的目录路径开始工作。

1. 打开 `audit/audit_report.html` 了解自动分析结果（浏览器查看或读 HTML 源码都行）
2. 通读 LaTeX 源码中的关键章节
3. 浏览代码仓库结构

---

## Section 0：可复现性检查

检查三项，每项给 ✅ / ⚠️ / ❌，**把结果写入 `audit/audit_report.html`**：

**数据集**
- 论文实验里用了哪些数据集？列出来
- 代码里有没有提供下载脚本、数据集 URL、或者 README 里写了怎么下载？
- 如果某个数据集在代码里完全没提到 → ⚠️

**预训练权重**
- 论文里有没有说用了预训练权重？
- 代码里是自动下载权重？还是 README 里给了链接？
- 如果论文用了但代码里完全没有 → ❌

**Baseline 对比方法**
- 论文跟哪些 baseline 做了对比？列出来
- 代码里是真的实现了这些 baseline，还是只贴了个数字？

---

## Section 1：方法实现一致性

论文的 Method / Architecture 部分是怎么描述的，代码里的模型定义是不是一回事。

做法：
- 读 LaTeX 里的 Method 章节
- 读代码里的模型定义文件（model.py / net.py 等）
- 对比以下方面：

| 检查项 | 说明 |
|--------|------|
| 整体架构 | backbone、模块组成是否一致 |
| 关键设计 | attention 机制、normalization、激活函数等是否对得上 |
| 明显差异 | 论文说 A，代码做 B |
| 多余组件 | 代码里有的但论文没提的 |

每个方法给出结论：✅ 一致 / ⚠️ 部分一致 / ❌ 不一致

**把方法对比表格写入 `audit/audit_report.html`：**

| 论文描述 | 花哨程度 | 代码实际实现 | 结论 |
|----------|----------|-------------|------|
| "We propose a novel multi-head attention mechanism with conditional computation" | 高 | 就是 8 头 attention，没有 conditional computation | ❌ 夸大了 |
| "We design a hierarchical feature pyramid network with bidirectional fusion" | 中 | 就是一个 FPN + 一个 top-down 路径 | ⚠️ 简化了 |

**花哨程度**分三档：高（听起来很复杂）/ 中（有一点点包装）/ 低（实话实说）

目的是让读者一眼看出论文的包装和代码的真实差距。

---

## Section 2：实验细节一致性

论文里写的实验设置和代码里的实际配置是否一致，**结果写入 `audit/audit_report.html`**。

对照检查：
- **超参数**：learning rate、batch size、epochs、optimizer、scheduler、weight decay、dropout —— 论文表格 vs 代码配置文件
- **数据预处理**：归一化、数据增强、图像尺寸 —— 论文描述 vs 代码实现
- **训练细节**：硬件、随机种子、训练时长 —— 论文提没提、代码提没提供
- **评估方式**：指标计算方式、测试集划分、后处理 —— 是否一致

---

## Section 3：每个实验的代码覆盖率

论文做了哪些实验，每个实验代码里有没有对应的实现，**结果写入 `audit/audit_report.html`**。

做法：
1. 通读论文，找出**每一个实验**
2. 每个实验记录：出自哪个章节、是什么内容、对应论文里的 Table/Figure 编号
3. 去代码里找对应的脚本、配置文件、或者 notebook
4. 给出结果

表格格式：

| 实验编号 | 来源章节 | 内容 | 对应 Table/Figure | 代码里有没有 | 对应文件 |
|----------|----------|------|-------------------|-------------|----------|
| 1 | Section 4.1 | ImageNet 分类 | Table 1 | ✅ | `scripts/train_imagenet.py` |
| 2 | Section 4.1 | 模型大小对比 | Table 2 | ⚠️ | 配置在但没自动化脚本 |
| 3 | Section 4.2 | 消融实验：深度 | Table 3 | ✅ | `scripts/ablation_depth.sh` |
| 4 | Section 4.3 | 收敛曲线 | Figure 3 | ❌ | 没有画图代码 |

---

## 更新审计总结

审计完成后，把 `audit/audit_report.html` 底部的虚线占位区域替换为实际的四维度审计结论。

---

## 生成引言三栏解读（默认执行）

审计完成后，**默认自动翻译论文的引言（Introduction）**，生成三栏对照网页：

创建 `qa/introduction.html`，将引言按自然段切分，每段一张卡片，每张卡片三栏：

| 左栏 | 中栏 | 右栏 |
|------|------|------|
| 🔤 英文原文 | 💡 用人话说一遍 | 🀄 中文翻译 |

**"用人话说"的目标读者：** 非本领域的普通人工智能专业本科生。
遇到术语要加括号解释，用类比帮助理解，不歪曲原意。

> 这样用户拿到审计报告的同时，也拿到了一份论文引言的通俗解读，可以直接在浏览器打开阅读。

如果用户后续还有更多问题，在 `qa/` 目录下继续新建 `xxx.html` 页面回答。

---

## QA 问答模块

在论文目录下已有 `qa/` 目录（或创建它），专门负责回答用户对这篇论文的提问。

### 目录结构

```
<base_dir>/
  <paper_name>/
    qa/
      introduction.html
      method.html
      ...
```

### 每个问题做成一个网页

每个问题对应一个独立的 `.html` 文件，用浏览器可打开阅读。

### 段落卡片设计

论文原文按自然段切分，每个段落做成一张**卡片（card）**，从上到下依次排列。
网页必须是完备的 HTML，自带样式（不要依赖外部 CDN），在浏览器中直接打开即可正常显示。

**标题规则：** 简洁直接，用 `📄 引言` / `🧪 实验` / `📄 摘要 · 方法 · 结论` 这种格式。
**不要 subtitle**（不需要论文全名 + arXiv ID 那行副标题）。
**不要 footer-note**（不需要底部的说明文字）。

### 三栏对照格式（用于论文解读类问题）

当用户要求翻译/解读论文某章节时，卡片内容分三栏：

| 左栏 | 中栏 | 右栏 |
|------|------|------|
| 🔤 英文原文 | 💡 用人话说一遍 | 🀄 中文翻译 |
| 论文该段落的原始英文 | 让非本领域读者（普通人工智能专业本科生）也能看懂的解释 | 准确的中文直译 |

**"用人话说"的原则：**
- 遇到专业术语时，在括号里加一句通俗解释（例如：GAN → 生成对抗网络，两个网络互相博弈生成图像）
- 用类比和比喻帮助理解
- 保留原文的技术准确性，不歪曲原意
- 对于论文中的核心创新点，可以用高亮块额外注解

### 网页模板

新建网页时使用以下完整模板。核心要点：
- 标题简洁（无 subtitle）
- 无 footer-note
- 所有样式内联（浅色主题）
- 卡片 body 三栏 grid

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

  <!-- 卡片示例 -->
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

### 当用户有新问题时

直接在 `qa/` 目录下新建 `xxx.html`，用同样的卡片风格回答。
问题也可以不是三栏格式，而是自由问答格式——此时卡片内可以是一问一答的结构：

```
卡片标题是问题
卡片内容用多段回答，支持高亮块、列表、代码块等
```
