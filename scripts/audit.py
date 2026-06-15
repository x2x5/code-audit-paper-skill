#!/usr/bin/env python3
"""
compare.py — Compare paper claims with code implementation.

Usage:
    python3 compare.py <latex_dir> <code_dir> --output-dir <compare_dir>

The script parses the LaTeX source to extract claims, methods, datasets, metrics,
and experiments, then analyzes the code repository for corresponding implementations.
Results are written as a Markdown report and JSON data file.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
#  LaTeX parsing helpers
# ---------------------------------------------------------------------------


def collect_latex_files(latex_dir: str) -> list[dict]:
    """Return a list of {path, content} for every .tex file found."""
    files = []
    for root, _dirs, _files in os.walk(latex_dir):
        for f in _files:
            if not f.endswith(".tex"):
                continue
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            files.append({"path": os.path.relpath(path, latex_dir), "content": content})
    return files


def extract_section_content(content: str, section_name: str) -> str:
    """Crudely grab the text right after \\section{section_name} until the next
    \\section or \\bibliography.  This is intentionally simple; real LaTeX
    parsing would need a full parser."""
    esc = re.escape(section_name)
    m = re.search(
        r"\\(?:section|subsection)\{"
        + esc
        + r"\}(.*?)(?:\\section|\\subsection|\\bibliography|\Z)",
        content,
        re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def extract_paper_claims(latex_files: list[dict]) -> dict:
    """Parse LaTeX files and return structured claims/methods/experiments info."""
    claims: list[dict] = []
    methods: dict[str, str] = {}
    experiments: list[dict] = []
    datasets: list[str] = []
    metrics: list[str] = []
    baselines: list[str] = []
    ablation_studies: list[str] = []
    tables_found: int = 0
    figures_found: int = 0

    for lf in latex_files:
        content = lf["content"]
        path = lf["path"]

        # Sections
        sections = re.findall(r"\\(?:section|subsection)\{([^}]+)\}", content)

        # --- Abstract claims ------------------------------------------------
        abs_m = re.search(
            r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, re.DOTALL
        )
        if abs_m:
            abstract = abs_m.group(1)
            for pat in [
                r"(?:we|our|this paper)\s.{0,60}?(?:achieve|improve|outperform|surpass|"
                r"demonstrate|show|introduce|propose|present|obtain|attain|state|exceed)"
                r".{0,200}[.?!]",
                r"(?:state-of-the-art|SOTA|best performance|superior|novel|first).{0,200}[.?!]",
            ]:
                for m in re.finditer(pat, abstract, re.IGNORECASE | re.DOTALL):
                    clean = " ".join(m.group().strip().split())
                    if clean and clean[:10] not in {c["text"][:10] for c in claims}:
                        claims.append(
                            {"text": clean, "source": path, "section": "abstract"}
                        )

        # --- Methods / Architecture -----------------------------------------
        for s in sections:
            if any(
                kw in s.lower()
                for kw in [
                    "method",
                    "approach",
                    "architecture",
                    "model",
                    "network",
                    "framework",
                    "design",
                    "overview",
                ]
            ):
                methods[s.strip()] = extract_section_content(content, s)[:800]

        # --- Experiments ----------------------------------------------------
        for s in sections:
            if "experiment" not in s.lower():
                continue
            exp_content = extract_section_content(content, s)
            experiments.append({"section": s.strip(), "content": exp_content[:2000]})

            # Datasets
            for d in re.findall(
                r"(?:on|using|dataset|data\s+set)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
                exp_content,
            ):
                d = d.strip()
                if d and len(d) > 2 and d not in datasets:
                    datasets.append(d)

            # Metrics
            for m in re.findall(
                r"([a-zA-Z]+[-/]?[a-zA-Z]*\s*(?:accuracy|precision|recall|F1|BLEU|ROUGE|"
                r"perplexity|error\s*rate|mAP|IoU|PSNR|SSIM|score|loss))",
                exp_content,
                re.IGNORECASE,
            ):
                clean = m.strip()
                if clean and clean not in metrics:
                    metrics.append(clean)

            # Baselines
            for b in re.findall(
                r"(?:compared\s+(?:with|to|against)|baselines?|"
                r"competitors?|prior\s+work|existing\s+methods?)[^.]*\.",
                exp_content,
                re.IGNORECASE,
            ):
                clean = b.strip()
                if clean and clean not in baselines:
                    baselines.append(clean)

            # Ablation
            if re.search(r"ablation", exp_content, re.IGNORECASE):
                for a in re.findall(
                    r"[^.]*ablation[^.]*\.", exp_content, re.IGNORECASE
                ):
                    clean = a.strip()
                    if clean and clean not in ablation_studies:
                        ablation_studies.append(clean)

        # --- Introduction claims --------------------------------------------
        for s in sections:
            if "introduction" not in s.lower():
                continue
            intro = extract_section_content(content, s)
            pat = (
                r"(?:we|our|this paper)\s.{0,60}?(?:achieve|improve|outperform|surpass|"
                r"demonstrate|show|introduce|propose|present|obtain|state).{0,200}[.?!]"
            )
            for m in re.finditer(pat, intro, re.IGNORECASE | re.DOTALL):
                clean = " ".join(m.group().strip().split())
                if clean and clean[:10] not in {c["text"][:10] for c in claims}:
                    claims.append(
                        {"text": clean, "source": path, "section": "introduction"}
                    )

        # --- Tables & figures -----------------------------------------------
        tables_found += len(re.findall(r"\\begin\{table\}", content))
        figures_found += len(re.findall(r"\\begin\{figure\}", content))

    return {
        "claims": claims,
        "methods": methods,
        "experiments": experiments,
        "datasets": list(set(datasets)),
        "metrics": list(set(metrics)),
        "baselines": baselines,
        "ablation_studies": ablation_studies,
        "tables": tables_found,
        "figures": figures_found,
    }


# ---------------------------------------------------------------------------
#  Code analysis helpers
# ---------------------------------------------------------------------------

LANG_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".go": "Go",
    ".rs": "Rust",
    ".r": "R",
    ".m": "MATLAB",
    ".jl": "Julia",
    ".ipynb": "Jupyter Notebook",
    ".sh": "Shell",
    ".lua": "Lua",
    ".tex": "LaTeX",
}


def detect_language(code_dir: str) -> str:
    """Detect primary language by counting source file extensions."""
    counts: dict[str, int] = defaultdict(int)
    for root, dirs, files in os.walk(code_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext:
                counts[ext] += 1
    if not counts:
        return "Unknown"
    top = max(counts, key=counts.get)
    return LANG_MAP.get(top, top.lstrip(".").upper())


def analyze_code_structure(code_dir: str) -> dict:
    """Walk the code directory and return structural metadata."""
    analysis: dict = {
        "language": detect_language(code_dir),
        "total_files": 0,
        "file_types": defaultdict(int),
        "has_tests": False,
        "has_scripts": False,
        "has_configs": False,
        "has_models": False,
        "has_datasets": False,
        "has_training": False,
        "has_evaluation": False,
        "has_pretrained": False,
        "has_readme": False,
        "has_license": False,
        "has_requirements": False,
        "has_docker": False,
        "has_demos": False,
        "key_files": [],
        "directory_structure": [],
    }

    for root, dirs, files in os.walk(code_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        rel = os.path.relpath(root, code_dir)
        if rel == ".":
            rel = "/"

        depth = rel.count(os.sep)
        if depth <= 2:
            analysis["directory_structure"].append(
                {"path": rel, "files": len(files), "dirs": len(dirs)}
            )

        for f in files:
            analysis["total_files"] += 1
            ext = os.path.splitext(f)[1].lower()
            analysis["file_types"][ext] += 1
            fpath = os.path.join(root, f)
            rel_path = os.path.relpath(fpath, code_dir)
            f_low = f.lower()

            if f_low.startswith("readme"):
                analysis["has_readme"] = True
            if "license" in f_low:
                analysis["has_license"] = True
            if f_low in (
                "requirements.txt",
                "environment.yml",
                "setup.py",
                "setup.cfg",
                "pyproject.toml",
            ):
                analysis["has_requirements"] = True
            if "dockerfile" in f_low or f_low.endswith("docker-compose.yml"):
                analysis["has_docker"] = True
            if (
                f_low.startswith("test")
                or "/test" in rel_path.lower()
                or "test_" in f_low
            ):
                analysis["has_tests"] = True

            if ext in (".py", ".sh", ".bat", ".ps1") and any(
                kw in f_low for kw in ["train", "run", "main"]
            ):
                analysis["has_scripts"] = True

            if ext in (".yaml", ".yml", ".json", ".cfg", ".ini", ".toml"):
                analysis["has_configs"] = True

            if "model" in f_low or "net" in f_low:
                analysis["has_models"] = True
            if "dataset" in f_low or "data" in f_low:
                analysis["has_datasets"] = True
            if "train" in f_low and ext in (".py", ".sh"):
                analysis["has_training"] = True
            if ("eval" in f_low or "test" in f_low) and ext in (".py", ".sh"):
                analysis["has_evaluation"] = True
            if "pretrain" in f_low or "weight" in f_low or "checkpoint" in f_low:
                analysis["has_pretrained"] = True
            if "demo" in f_low or "example" in f_low:
                analysis["has_demos"] = True

            # Collect important source files
            if ext in (
                ".py",
                ".java",
                ".cpp",
                ".h",
                ".hpp",
                ".rs",
                ".go",
                ".ts",
                ".js",
            ):
                if any(
                    kw in f_low
                    for kw in [
                        "model",
                        "train",
                        "eval",
                        "main",
                        "run",
                        "dataset",
                        "net",
                        "arch",
                        "utils",
                    ]
                ):
                    analysis["key_files"].append(rel_path)

    analysis["file_types"] = dict(analysis["file_types"])
    analysis["key_files"] = analysis["key_files"][:25]
    return analysis


# ---------------------------------------------------------------------------
#  Paper-to-code mapping
# ---------------------------------------------------------------------------


def _keyword_in_code(keyword: str, code_dir: str) -> bool:
    """Check if a keyword appears in any source file under code_dir."""
    if len(keyword) < 4:
        return False
    kw_lower = keyword.lower()
    for root, dirs, files in os.walk(code_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in (
                ".py",
                ".java",
                ".cpp",
                ".h",
                ".hpp",
                ".rs",
                ".go",
                ".ts",
                ".js",
                ".yaml",
                ".yml",
                ".json",
                ".cfg",
            ):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                if kw_lower in content.lower():
                    return True
            except Exception:
                continue
    return False


def map_paper_to_code(paper: dict, code_analysis: dict, code_dir: str) -> dict:
    """Cross-reference paper claims/experiments with code implementation."""
    mapping: dict = {
        "matched_methods": [],
        "unmatched_methods": [],
        "matched_datasets": [],
        "unmatched_datasets": [],
        "matched_metrics": [],
        "experiment_coverage": [],
        "ablation_implemented": False,
        "ablation_claimed": bool(paper["ablation_studies"]),
        "code_quality_notes": [],
    }

    # Methods
    for method_name in paper["methods"]:
        tokens = method_name.lower().split()
        # Use the last meaningful word as the search key
        key = next((t for t in reversed(tokens) if len(t) > 3), method_name)
        if _keyword_in_code(key, code_dir):
            mapping["matched_methods"].append(method_name)
        else:
            mapping["unmatched_methods"].append(method_name)

    # Datasets
    for ds in paper["datasets"]:
        if _keyword_in_code(ds, code_dir):
            mapping["matched_datasets"].append(ds)
        else:
            mapping["unmatched_datasets"].append(ds)

    # Metrics
    for met in paper["metrics"]:
        tokens = met.lower().split()
        key = tokens[-1] if len(tokens) > 1 else tokens[0]
        if len(key) > 3 and _keyword_in_code(key, code_dir):
            mapping["matched_metrics"].append(met)

    # Experiment coverage
    if code_analysis["has_training"]:
        mapping["experiment_coverage"].append("Training pipeline")
    if code_analysis["has_evaluation"]:
        mapping["experiment_coverage"].append("Evaluation / testing")
    if code_analysis["has_datasets"]:
        mapping["experiment_coverage"].append("Data loading / preprocessing")
    if code_analysis["has_configs"]:
        mapping["experiment_coverage"].append("Configuration / hyperparameters")
    if code_analysis["has_scripts"]:
        mapping["experiment_coverage"].append("Run scripts")
    if code_analysis["has_demos"]:
        mapping["experiment_coverage"].append("Demo / inference examples")

    # Ablation studies
    if paper["ablation_studies"]:
        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d != ".git"]
            if any("ablation" in f.lower() for f in files):
                mapping["ablation_implemented"] = True
                break

    # Quality notes
    if not code_analysis["has_readme"]:
        mapping["code_quality_notes"].append("No README — reproducibility may suffer")
    if not code_analysis["has_requirements"]:
        mapping["code_quality_notes"].append("No requirements/setup file found")
    if not code_analysis["has_configs"]:
        mapping["code_quality_notes"].append(
            "No configuration files — hyperparameters may be hard to reproduce"
        )
    if code_analysis["has_pretrained"]:
        mapping["code_quality_notes"].append(
            "Pretrained weights / checkpoints included"
        )
    if code_analysis["has_tests"]:
        mapping["code_quality_notes"].append("Test suite present")
    if code_analysis["has_docker"]:
        mapping["code_quality_notes"].append("Docker support available")
    if code_analysis["has_license"]:
        mapping["code_quality_notes"].append("License file present")

    return mapping


# ---------------------------------------------------------------------------
#  Report generation
# ---------------------------------------------------------------------------


def generate_report(
    paper: dict, code_analysis: dict, mapping: dict, output_dir: str
) -> str:
    """Write analysis_report.md and analysis_data.json to *output_dir* (Chinese)."""
    os.makedirs(output_dir, exist_ok=True)

    lines: list[str] = []
    ap = lambda: lines.append  # shorthand
    ap()("# 论文与代码审计报告")
    ap()("")
    ap()("---")
    ap()("")

    # ── 1. 论文概览 ──────────────────────────────────────────────────────
    ap()("## 1. 论文概览")
    ap()("")
    ap()("| 类别 | 数量 |")
    ap()("|------|-----:|")
    ap()(f"| 方法 / 架构组件 | {len(paper['methods'])} |")
    ap()(f"| 提取到的声明 | {len(paper['claims'])} |")
    ap()(f"| 提到的指标 | {len(paper['metrics'])} |")
    ap()(f"| 使用的数据集 | {len(paper['datasets'])} |")
    ap()(f"| 实验章节 | {len(paper['experiments'])} |")
    ap()(f"| 对比的 baseline | {len(paper['baselines'])} |")
    ap()(f"| 消融实验 | {'有' if paper['ablation_studies'] else '无'} |")
    ap()(f"| 表格数 | {paper['tables']} |")
    ap()(f"| 图数 | {paper['figures']} |")
    ap()("")

    # ── 2. 代码结构 ────────────────────────────────────────────────────
    ap()("## 2. 代码结构分析")
    ap()("")
    ap()(f"- **主要语言**：{code_analysis['language']}")
    ap()(f"- **文件总数**：{code_analysis['total_files']}")
    ap()("")
    ap()("**文件类型分布：**")
    ap()("")
    for ext, count in sorted(code_analysis["file_types"].items(), key=lambda x: -x[1])[
        :12
    ]:
        ap()(f"- `{ext}`：{count} 个")
    ap()("")
    ap()("**代码仓库能力检测：**")
    ap()("")
    capabilities = [
        ("训练代码", "has_training"),
        ("评估/测试代码", "has_evaluation"),
        ("数据集处理", "has_datasets"),
        ("模型定义", "has_models"),
        ("配置文件", "has_configs"),
        ("运行脚本", "has_scripts"),
        ("测试套件", "has_tests"),
        ("README", "has_readme"),
        ("依赖管理 / setup", "has_requirements"),
        ("Docker 支持", "has_docker"),
        ("许可证", "has_license"),
        ("Demo / 示例", "has_demos"),
        ("预训练权重", "has_pretrained"),
    ]
    for label, key in capabilities:
        present = code_analysis.get(key, False)
        ap()(f"- {'✅' if present else '❌'} {label}")
    ap()("")

    # ── 3. 论文与代码对照 ─────────────────────────────────────────────
    ap()("## 3. 论文与代码对照")
    ap()("")

    # 方法
    ap()("### 3.1 方法 / 架构")
    ap()("")
    if paper["methods"]:
        for m in paper["methods"]:
            status = "✅" if m in mapping["matched_methods"] else "⚠️"
            ap()(f"- {status} **{m}**")
    else:
        ap()("_(未提取到具体方法)_")
    ap()("")

    # 数据集
    ap()("### 3.2 数据集")
    ap()("")
    all_ds = mapping["matched_datasets"] + mapping["unmatched_datasets"]
    if all_ds:
        for d in all_ds:
            status = "✅" if d in mapping["matched_datasets"] else "❌"
            ap()(f"- {status} `{d}`")
    else:
        ap()("_(未提取到数据集)_")
    ap()("")

    # 指标
    ap()("### 3.3 指标与结果")
    ap()("")
    for m in paper["metrics"]:
        status = "✅" if m in mapping["matched_metrics"] else "🔶"
        ap()(f"- {status} `{m}`")
    if not paper["metrics"]:
        ap()("_(未提取到指标)_")
    ap()("")

    # 实验
    ap()("### 3.4 实验覆盖")
    ap()("")
    if paper["experiments"]:
        for e in paper["experiments"]:
            ap()(f"- **{e['section']}**")
            for cov in mapping["experiment_coverage"]:
                ap()(f"  - ✅ {cov}")
        ap()("")
    if mapping["ablation_implemented"]:
        ap()("- ✅ 消融实验代码已找到")
    elif mapping["ablation_claimed"]:
        ap()("- ⚠️ 论文提到了消融实验，但**代码里没有找到**")
    ap()("")

    # 质量备注
    if mapping["code_quality_notes"]:
        ap()("### 3.5 代码质量备注")
        ap()("")
        for note in mapping["code_quality_notes"]:
            ap()(f"- {note}")
        ap()("")

    # ── 4. 详细声明 ───────────────────────────────────────────────────
    ap()("## 4. 论文声明详情")
    ap()("")
    if paper["claims"]:
        for i, c in enumerate(paper["claims"], 1):
            ap()(f"### 声明 {i}")
            ap()("")
            ap()(f"> {c['text']}")
            ap()("")
            ap()(f"- 来源：`{c['source']}` ({c['section']})")
            ap()("")
    else:
        ap()("_(未提取到具体声明)_")
        ap()("")

    # ── 5. 关键文件 ───────────────────────────────────────────────────
    ap()("## 5. 关键源文件")
    ap()("")
    if code_analysis["key_files"]:
        for f in code_analysis["key_files"]:
            ap()(f"- `{f}`")
    else:
        ap()("_(未识别到关键文件)_")
    ap()("")

    # ── 6. 总结 ───────────────────────────────────────────────────────
    ap()("## 6. 总结")
    ap()("")
    total_methods = len(mapping["matched_methods"]) + len(mapping["unmatched_methods"])
    total_datasets = len(mapping["matched_datasets"]) + len(
        mapping["unmatched_datasets"]
    )
    method_pct = (
        round(100 * len(mapping["matched_methods"]) / total_methods, 0)
        if total_methods
        else 0
    )
    dataset_pct = (
        round(100 * len(mapping["matched_datasets"]) / total_datasets, 0)
        if total_datasets
        else 0
    )

    ap()(
        f"- **方法实现覆盖率**：{len(mapping['matched_methods'])}/{total_methods} "
        f"({method_pct:.0f}%)"
    )
    ap()(
        f"- **数据集覆盖率**：{len(mapping['matched_datasets'])}/{total_datasets} "
        f"({dataset_pct:.0f}%)"
    )
    ap()(
        f"- **实验支持**：覆盖 {len(mapping['experiment_coverage'])} 个方面"
    )
    ap()("")

    if mapping["unmatched_methods"] or mapping["unmatched_datasets"]:
        ap()("- ⚠️ **部分论文声明在代码中未能完全验证**")
    else:
        ap()("- ✅ **论文声明在代码中有良好支持**")
    ap()("")

    if mapping["ablation_claimed"] and not mapping["ablation_implemented"]:
        ap()("- ⚠️ **论文声称做了消融实验，但代码中未找到**")
    ap()("")

    report = "\n".join(lines)

    # Write report
    report_path = os.path.join(output_dir, "analysis_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Write JSON data
    json_path = os.path.join(output_dir, "analysis_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "paper": {
                    "claims": paper["claims"],
                    "methods": list(paper["methods"].keys()),
                    "datasets": paper["datasets"],
                    "metrics": paper["metrics"],
                    "experiment_count": len(paper["experiments"]),
                    "baselines": paper["baselines"],
                    "ablation_studies": paper["ablation_studies"],
                    "tables": paper["tables"],
                    "figures": paper["figures"],
                },
                "code": {
                    "language": code_analysis["language"],
                    "total_files": code_analysis["total_files"],
                    "capabilities": {
                        k: code_analysis.get(k, False)
                        for k in [
                            "has_training",
                            "has_evaluation",
                            "has_datasets",
                            "has_models",
                            "has_tests",
                            "has_scripts",
                            "has_configs",
                            "has_readme",
                            "has_license",
                            "has_requirements",
                            "has_docker",
                            "has_pretrained",
                        ]
                    },
                },
                "mapping": {
                    "matched_methods": mapping["matched_methods"],
                    "unmatched_methods": mapping["unmatched_methods"],
                    "matched_datasets": mapping["matched_datasets"],
                    "unmatched_datasets": mapping["unmatched_datasets"],
                    "matched_metrics": mapping["matched_metrics"],
                    "experiment_coverage": mapping["experiment_coverage"],
                    "ablation_implemented": mapping["ablation_implemented"],
                    "ablation_claimed": mapping["ablation_claimed"],
                    "code_quality_notes": mapping["code_quality_notes"],
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    return report_path


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare paper claims with code implementation"
    )
    parser.add_argument("latex_dir", help="Directory containing LaTeX source")
    parser.add_argument("code_dir", help="Directory containing code")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="compare",
        help="Output directory for report (default: compare)",
    )
    args = parser.parse_args()

    latex_dir = os.path.abspath(args.latex_dir)
    code_dir = os.path.abspath(args.code_dir)
    output_dir = os.path.abspath(args.output_dir)

    for d, name in [(latex_dir, "LaTeX"), (code_dir, "Code")]:
        if not os.path.isdir(d):
            print(f"Error: {name} directory not found: {d}")
            sys.exit(1)

    print("=" * 56)
    print("  Paper vs Code Analysis")
    print("=" * 56)
    print()

    # Step 1 — parse LaTeX
    print("1. Parsing LaTeX source …")
    latex_files = collect_latex_files(latex_dir)
    print(f"   → {len(latex_files)} .tex file(s)\n")

    print("2. Extracting paper claims …")
    paper = extract_paper_claims(latex_files)
    print(f"   → {len(paper['claims'])} claims")
    print(f"   → {len(paper['methods'])} methods")
    print(f"   → {len(paper['datasets'])} datasets")
    print(f"   → {len(paper['metrics'])} metrics")
    print(f"   → {len(paper['experiments'])} experiment sections")
    print(f"   → {paper['tables']} tables, {paper['figures']} figures\n")

    # Step 2 — analyze code
    print("3. Analyzing code structure …")
    code = analyze_code_structure(code_dir)
    print(f"   → Language: {code['language']}")
    print(f"   → {code['total_files']} total files\n")

    # Step 3 — map
    print("4. Mapping paper → code …")
    mapping = map_paper_to_code(paper, code, code_dir)
    print(f"   → Matched methods:   {len(mapping['matched_methods'])}")
    print(f"   → Unmatched methods: {len(mapping['unmatched_methods'])}")
    print(f"   → Matched datasets:  {len(mapping['matched_datasets'])}")
    print(f"   → Unmatched datasets:{len(mapping['unmatched_datasets'])}")
    print(f"   → Experiment areas:  {len(mapping['experiment_coverage'])}\n")

    # Step 4 — report
    print("5. Generating report …")
    report_path = generate_report(paper, code, mapping, output_dir)
    print(f"\n   ✓ Report  → {report_path}")
    print(f"   ✓ Data    → {os.path.join(output_dir, 'analysis_data.json')}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
