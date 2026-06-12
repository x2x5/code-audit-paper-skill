---
name: arxiv-paper-code-analyzer
description: Given a paper title, searches arXiv for the LaTeX source, finds the corresponding code on GitHub, and analyzes whether the paper claims and experiments match the actual implementation.
---

# paper-vs-code-skill

从 arXiv 下载 LaTeX 源码，从 GitHub 找到代码仓库，然后从 4 个维度审计论文。

## 准备工作

解析用户的输入（arXiv ID / 论文标题 / 完整 URL），询问输出目录，然后按顺序跑三个脚本：

```bash
python3 scripts/fetch_arxiv.py "<query>" --output-dir <base_dir>
python3 scripts/fetch_code.py "<query>" --output-dir <base_dir> --latex-dir <base_dir>/<paper_name>/latex
python3 scripts/audit.py <base_dir>/<paper_name>/latex <base_dir>/<paper_name>/code --output-dir <base_dir>/<paper_name>/audit
```

`fetch_code.py` 搜索 GitHub 的逻辑：
1. 先扫 LaTeX 源码里的 `github.com` 链接，有就直接克隆
2. 没有就按论文标题搜 GitHub，让用户选
3. **仓库克隆下来后，检查里面有没有实际代码文件（.py、.cpp、.java 等）。如果只有一个 README 或者几乎空的，直接说这个仓库是空的，不要再去搜其他的。空的就是空的。**

`audit.py` 会生成一份初步报告（自动提取的 claims、代码结构分析、关键词匹配）。用这份报告做起点，然后按下面 4 个 Section 逐条检查 —— 自动报告只是辅助，你需要亲自看 LaTeX 源码和代码来给出准确判断。

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

### 最终汇报

给用户一个清晰的总结：

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

## 边界情况

| 情况 | 处理方式 |
|------|----------|
| 论文不在 arXiv 上 | 告诉用户，问他有没有 URL |
| 有 arXiv 但只有 PDF，没有 LaTeX 源码 | 报告无法处理，停止 |
| GitHub 搜不到仓库 | 问用户有没有 URL |
| LaTeX 或代码缺一个 | 无法审计，解释原因 |
