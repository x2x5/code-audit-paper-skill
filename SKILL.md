---
name: code-audit-paper
description: Given a paper title, fetches LaTeX source from arXiv and code from GitHub, then audits whether the paper exaggerates, hides details, or makes unverifiable claims — using the actual code as evidence.
---

# code-audit-paper-skill

**用代码当证据，审计论文有没有吹牛、有没有隐瞒、实验能不能复现。**

从 arXiv 下载 PDF 和 LaTeX 源码，从 GitHub 找到代码仓库，然后从 4 个维度审计论文。

## 准备工作

解析用户的输入（arXiv ID / 论文标题 / 完整 URL），确定输出目录和论文名，然后按顺序执行：

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

`audit.py` 会生成一份初步报告（自动提取的 claims、代码结构分析、关键词匹配）。
用这份报告做起点，然后按下面 4 个 Section 逐条检查 ——
自动报告只是辅助，你需要亲自看 LaTeX 源码和代码来给出准确判断。

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

把论文里的每个方法/模块描述和代码里的实际实现对照着写出来，存为 `audit/method_vs_code.md`。

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

```
## 审计总结

### Section 0：可复现性
- 数据集：ImageNet（有下载脚本 ✅）、COCO（README 给了链接 ✅）
- 预训练权重：自动下载 ✅
- Baseline：5 个 baseline 中 2 个有实现 ⚠️

### Section 1：方法实现
- 整体架构一致 ✅
- Attention 机制不一致 ❌
  → 论文描述的是 8 头 attention，代码实现是 12 头

### Section 2：实验细节
- 超参数与论文一致 ✅
- 数据增强不一致 ⚠️
  → 论文用的是 RandomResizedCrop，代码用的是 CenterCrop

### Section 3：实验覆盖率
- 5 个实验中 3 个有对应代码实现 ⚠️
- 2 个实验完全找不到代码 ❌
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

### 示例实现

参见 `qa/introduction.html` 的写法：

```html
<!-- 每一段是一个卡片 -->
<div class="card">
  <div class="card-body" style="display:grid; grid-template-columns: 1fr 1fr 1fr;">
    <div class="col col-en">
      <div class="col-label">🔤 原文</div>
      ...英文原文...
    </div>
    <div class="col col-plain">
      <div class="col-label">💡 用人话说</div>
      ...通俗解释...
    </div>
    <div class="col col-zh">
      <div class="col-label">🀄 中文翻译</div>
      ...中文翻译...
    </div>
  </div>
</div>
```

### 当用户有新问题时

直接在 `qa/` 目录下新建 `xxx.html`，用同样的卡片风格回答。
问题也可以不是三栏格式，而是自由问答格式——此时卡片内可以是一问一答的结构：

```
卡片标题是问题
卡片内容用多段回答，支持高亮块、列表、代码块等
```
