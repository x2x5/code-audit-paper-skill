---
name: code-audit-paper
description: Given a paper title, fetches LaTeX source from arXiv and code from GitHub, then audits whether the paper exaggerates, hides details, or makes unverifiable claims — using the actual code as evidence.
---

# code-audit-paper-skill

**用代码当证据，审计论文有没有吹牛、有没有隐瞒、实验能不能复现。**

从 arXiv 下载 PDF 和 LaTeX 源码，从 GitHub 找到代码仓库，然后从 4 个维度审计论文。

---

## 第 0 步：环境检查（每次审计前必须先做）

**任何操作之前，先检查当前环境里装了哪些工具、正确的命令名是什么。**
不同系统差异很大（`python` vs `python3`、`pip` vs `pip3`、有没有 `git`、有没有 `curl`），
不检查就直接跑命令会导致无谓的报错。

### 必须检查的项目

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
#    先确认可用的 Python 命令，再检查依赖
<可用的python命令> -c "import json, os, re, sys, argparse, collections; print('✅ 核心依赖就绪')" 2>&1

# 6. 操作系统
uname -s 2>&1 || echo "Windows"
```

### 记下结果，后续步骤全部使用正确命令

检查完后，你应该清楚：
- **Python 命令**是 `python` 还是 `python3`？（后续所有脚本命令用这个）
- **pip 命令**是 `pip` 还是 `pip3`？（安装缺失依赖用这个）
- **Git 有没有**？（没有的话无法克隆代码仓库 → 审计中止）
- **下载工具**用 `curl` 还是 `wget`？
- **操作系统**是 macOS / Linux / Windows？（路径和 shell 语法有区别）

> ⚠️ **如果 git 不可用**：直接告诉用户"需要安装 git 才能克隆代码仓库"，审计中止。
>
> ⚠️ **如果 Python 不可用**：直接告诉用户"需要安装 Python 3.8+ 才能运行审计脚本"，审计中止。
>
> ⚠️ **如果缺少 Python 依赖包**：用正确的 pip 命令安装，例如 `<pip> install requests`。

---

## 准备工作

环境检查通过后，解析用户的输入（arXiv ID / 论文标题 / 完整 URL），确定输出目录和论文名，然后按顺序执行：

> 📌 **以下所有命令中的 `python3` 都表示你在第 0 步中确定的正确 Python 命令**
> （可能是 `python` 或 `python3`，根据你的环境替换）。`git`、`pip`、`curl` 同理。

### 1. 下载 PDF 和 LaTeX 源码

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

### 2. 查找并克隆代码仓库

**这一步由你（agent）来做关键判断。**

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

**关于论文名 `<paper_name>`（自动提取，不需要你手动指定）：**
- 优先检测论文标题中的全大写方法缩写（如 JMVR、ResNet、ViT、DALL-E），用它做目录名
- 如果没有明显的缩写，取论文标题的**前 6 个单词**，小写用连字符连接（如 `toward-high-fidelity-visual-reconstruction`）
- 这样目录名简短可读，不再是 `paper-260319667v1` 这种无意义的数字串

**克隆完成后：** 检查仓库内容，判断它是不是有实际代码的论文复现仓库
（而不是空壳项目、个人主页、或纯文档项目）。

### 3. 执行审计

```bash
python3 scripts/audit.py <base_dir>/<paper_name>/latex <base_dir>/<paper_name>/code \
    --output-dir <base_dir>/<paper_name>/audit
```

`audit.py` 会生成一个自包含的 **HTML 网页** `audit/audit_report.html`（浏览器直接打开即可查看），内容包括：
- 论文概览（方法数、声明数、数据集、表格/图数量等）
- 代码结构分析（语言、文件统计、能力检测）
- 论文与代码交叉比对（方法匹配、数据集、指标、实验覆盖、代码质量）
- 提取的论文声明详情
- 关键源文件清单
- 自动审计总结

所有数据也以 JSON 格式嵌入在 HTML 的 `<script>` 标签中，方便程序化读取。

用这份 HTML 报告做起点，然后按下面 4 个 Section 逐条检查 ——
自动报告只是辅助，你需要亲自看 LaTeX 源码和代码来给出准确判断，
**并把这些判断直接写入 `audit_report.html` 中**（在对应 section 的预留位置填写）。

---

### Section 0：可复现性检查

检查三项，每项给 ✅ / ⚠️ / ❌：

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

### Section 1：方法实现一致性

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

#### 输出一份方法对比文档

把论文里的每个方法/模块描述和代码里的实际实现对照着写出来，
写入 `audit/audit_report.html` 中（在「方法一致性」section 的预留位置）。

格式：

| 论文描述 | 花哨程度 | 代码实际实现 | 结论 |
|----------|----------|-------------|------|
| "We propose a novel multi-head attention mechanism with conditional computation" | 高 | 就是 8 头 attention，没有 conditional computation | ❌ 夸大了 |
| "We design a hierarchical feature pyramid network with bidirectional fusion" | 中 | 就是一个 FPN + 一个 top-down 路径 | ⚠️ 简化了 |
| "We introduce a learnable gating mechanism to adaptively fuse modalities" | 中 | 一个 weighted sum，权重可学习 | ✅ 一致 |
| "We adopt a two-stage training strategy with curriculum learning" | 低 | 就是先用小 lr 训再用大 lr 训 | ✅ 一致 |

**花哨程度**分三档：高（听起来很复杂）/ 中（有一点点包装）/ 低（实话实说）

目的是让读者一眼看出论文的包装和代码的真实差距。

---

### Section 2：实验细节一致性

论文里写的实验设置和代码里的实际配置是否一致。

对照检查：

- **超参数**：learning rate、batch size、epochs、optimizer、scheduler、weight decay、dropout —— 论文表格 vs 代码配置文件
- **数据预处理**：归一化、数据增强、图像尺寸 —— 论文描述 vs 代码实现
- **训练细节**：硬件、随机种子、训练时长 —— 论文提没提、代码提没提供
- **评估方式**：指标计算方式、测试集划分、后处理 —— 是否一致

---

### Section 3：每个实验的代码覆盖率

论文做了哪些实验，每个实验代码里有没有对应的实现。

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
| 5 | Section 4.4 | 可视化分析 | Figure 4 | ❌ | 无可视化代码 |

如果论文某个实验没有对应代码 → 标记 ❌，说明这个实验结果在代码里无法复现。

---

### 4. 生成引言三栏解读（默认执行）

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

### 最终汇报

审计完成后，`audit/audit_report.html` 就是一个可以直接在浏览器中打开的完整报告网页。
你需要确保以下内容都已填写完整：

```
## 审计报告检查清单

### Section 0：可复现性（填入 audit_report.html 对应位置）
- 数据集：列出所有数据集及代码中是否有下载方式
- 预训练权重：论文是否用了、代码是否提供
- Baseline：列出所有 baseline，标记哪些有代码实现

### Section 1：方法实现（方法对比表格填入 audit_report.html）
- 整体架构一致性
- 各模块/组件一致性
- 论文夸大 vs 代码实际的差异

### Section 2：实验细节（填入 audit_report.html）
- 超参数一致性
- 数据预处理一致性
- 训练/评估细节一致性

### Section 3：实验覆盖率（实验对照表填入 audit_report.html）
- 论文每个实验 → 代码对应文件
- 标记缺失的实验
```

---

## QA 问答模块

在论文目录下创建 `qa/` 目录，专门负责回答用户对这篇论文的提问。

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
- 所有样式内联
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
    background: #f5f7fa;
    color: #1a1a2e;
    line-height: 1.7;
    padding: 40px 20px;
  }
  .container { max-width: 1200px; margin: 0 auto; }
  h1 {
    font-size: 1.6rem;
    text-align: center;
    margin-bottom: 36px;
    color: #1a1a2e;
  }
  .card {
    background: #fff;
    border-radius: 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    margin-bottom: 28px;
    overflow: hidden;
  }
  .card-header {
    background: #f0f2f5;
    padding: 10px 20px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #555;
    border-bottom: 1px solid #e8e8e8;
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
    border-right: 1px solid #e8e8e8;
  }
  .col-plain {
    background: #f8f9fe;
    border-right: 1px solid #e8e8e8;
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
  .col-en .col-label { color: #2b6cb0; border-color: #bee3f8; }
  .col-plain .col-label { color: #38a169; border-color: #c6f6d5; }
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
      <span style="font-size:0.8rem;color:#999;">#1</span>
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
