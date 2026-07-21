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


def _html_escape(text: str) -> str:
    """Escape text for safe HTML embedding."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def generate_report(
    paper: dict, code_analysis: dict, mapping: dict, output_dir: str
) -> str:
    """Write a single self-contained audit_report.html to *output_dir*.

    The HTML page includes all automated analysis data (paper overview, code
    structure, paper-vs-code mapping, extracted claims, key files, summary) in a
    clean light-theme layout.  JSON data is embedded in a <script> tag for any
    interactive use.
    """
    os.makedirs(output_dir, exist_ok=True)

    json_data = json.dumps(
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
        indent=2,
        ensure_ascii=False,
    )

    # ── helpers for building HTML blocks ──────────────────────────────────

    def _badge(ok: bool) -> str:
        return (
            '<span class="badge badge-ok">✅ 是</span>'
            if ok
            else '<span class="badge badge-no">❌ 否</span>'
        )

    # 1. Paper overview table rows
    overview_rows = [
        ("方法 / 架构组件", str(len(paper["methods"]))),
        ("提取到的声明", str(len(paper["claims"]))),
        ("提到的指标", str(len(paper["metrics"]))),
        ("使用的数据集", str(len(paper["datasets"]))),
        ("实验章节", str(len(paper["experiments"]))),
        ("对比的 baseline", str(len(paper["baselines"]))),
        ("消融实验", "有" if paper["ablation_studies"] else "无"),
        ("表格数", str(paper["tables"])),
        ("图数", str(paper["figures"])),
    ]
    overview_html = "\n".join(
        f"<tr><td>{l}</td><td>{v}</td></tr>" for l, v in overview_rows
    )

    # 2. Code structure — file types
    file_type_rows = []
    for ext, count in sorted(
        code_analysis["file_types"].items(), key=lambda x: -x[1]
    )[:12]:
        file_type_rows.append(f"<tr><td><code>{ext}</code></td><td>{count}</td></tr>")
    file_type_html = "\n".join(file_type_rows) if file_type_rows else "<tr><td colspan='2'>—</td></tr>"

    # Capabilities
    capabilities = [
        ("训练代码", "has_training"),
        ("评估 / 测试代码", "has_evaluation"),
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
    cap_rows = []
    for label, key in capabilities:
        present = code_analysis.get(key, False)
        cap_rows.append(
            f"<tr><td>{_badge(present)}</td><td>{label}</td></tr>"
        )
    cap_html = "\n".join(cap_rows)

    # 3a. Methods matching
    if paper["methods"]:
        meth_rows = []
        for m in paper["methods"]:
            ok = m in mapping["matched_methods"]
            status = "✅" if ok else "⚠️"
            cls = "match-yes" if ok else "match-warn"
            meth_rows.append(
                f'<tr class="{cls}"><td>{status}</td><td>{_html_escape(m)}</td></tr>'
            )
        methods_html = "\n".join(meth_rows)
    else:
        methods_html = '<tr><td colspan="2" class="muted">（未提取到具体方法）</td></tr>'

    # 3b. Datasets
    all_ds = mapping["matched_datasets"] + mapping["unmatched_datasets"]
    if all_ds:
        ds_rows = []
        for d in all_ds:
            ok = d in mapping["matched_datasets"]
            status = "✅" if ok else "❌"
            cls = "match-yes" if ok else "match-no"
            ds_rows.append(
                f'<tr class="{cls}"><td>{status}</td><td><code>{_html_escape(d)}</code></td></tr>'
            )
        ds_html = "\n".join(ds_rows)
    else:
        ds_html = '<tr><td colspan="2" class="muted">（未提取到数据集）</td></tr>'

    # 3c. Metrics
    if paper["metrics"]:
        met_rows = []
        for m in paper["metrics"]:
            ok = m in mapping["matched_metrics"]
            status = "✅" if ok else "🔶"
            cls = "match-yes" if ok else "match-maybe"
            met_rows.append(
                f'<tr class="{cls}"><td>{status}</td><td><code>{_html_escape(m)}</code></td></tr>'
            )
        metrics_html = "\n".join(met_rows)
    else:
        metrics_html = '<tr><td colspan="2" class="muted">（未提取到指标）</td></tr>'

    # 3d. Experiment coverage
    exp_items = ""
    if paper["experiments"]:
        for e in paper["experiments"]:
            exp_items += (
                f'<li class="exp-section"><strong>{_html_escape(e["section"])}</strong>'
            )
            if mapping["experiment_coverage"]:
                exp_items += "<ul>"
                for cov in mapping["experiment_coverage"]:
                    exp_items += f"<li>✅ {_html_escape(cov)}</li>"
                exp_items += "</ul>"
            exp_items += "</li>"
    else:
        exp_items = '<li class="muted">（未提取到实验章节）</li>'

    # Ablation
    ablation_html = ""
    if mapping["ablation_implemented"]:
        ablation_html = '<p class="note-ok">✅ 消融实验代码已找到</p>'
    elif mapping["ablation_claimed"]:
        ablation_html = '<p class="note-warn">⚠️ 论文提到了消融实验，但<strong>代码里没有找到</strong></p>'

    # 3e. Quality notes
    quality_html = ""
    if mapping["code_quality_notes"]:
        items = "".join(
            f"<li>{_html_escape(n)}</li>" for n in mapping["code_quality_notes"]
        )
        quality_html = f"<ul>{items}</ul>"
    else:
        quality_html = '<p class="muted">（无特别备注）</p>'

    # 4. Claims
    if paper["claims"]:
        claim_cards = []
        for i, c in enumerate(paper["claims"], 1):
            claim_cards.append(
                f"""<div class="claim-card">
  <div class="claim-header">声明 #{i} <span class="claim-src">来源：{_html_escape(c['source'])}（{_html_escape(c['section'])}）</span></div>
  <div class="claim-body">{_html_escape(c['text'])}</div>
</div>"""
            )
        claims_html = "\n".join(claim_cards)
    else:
        claims_html = '<p class="muted">（未提取到具体声明）</p>'

    # 5. Key files
    if code_analysis["key_files"]:
        kf_items = "".join(
            f"<li><code>{_html_escape(f)}</code></li>"
            for f in code_analysis["key_files"]
        )
        keyfiles_html = f"<ul>{kf_items}</ul>"
    else:
        keyfiles_html = '<p class="muted">（未识别到关键文件）</p>'

    # 6. Summary stats
    total_methods = len(mapping["matched_methods"]) + len(
        mapping["unmatched_methods"]
    )
    total_datasets = len(mapping["matched_datasets"]) + len(
        mapping["unmatched_datasets"]
    )
    method_pct = (
        round(100 * len(mapping["matched_methods"]) / total_methods)
        if total_methods
        else 0
    )
    dataset_pct = (
        round(100 * len(mapping["matched_datasets"]) / total_datasets)
        if total_datasets
        else 0
    )

    verdict_icon = "✅" if not (
        mapping["unmatched_methods"] or mapping["unmatched_datasets"]
    ) else "⚠️"
    verdict_text = (
        "论文声明在代码中有良好支持"
        if verdict_icon == "✅"
        else "部分论文声明在代码中未能完全验证"
    )

    ablation_note = ""
    if mapping["ablation_claimed"] and not mapping["ablation_implemented"]:
        ablation_note = (
            '<p class="note-warn">⚠️ 论文声称做了消融实验，但代码中未找到</p>'
        )

    # ══════════════════════════════════════════════════════════════════════
    #  Build the full HTML page
    # ══════════════════════════════════════════════════════════════════════
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>审计报告 — 论文 vs 代码</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif;
    background: #f8fafc;
    color: #1e293b;
    line-height: 1.7;
  }}

  /* ── top bar ── */
  .topbar {{
    background: #fff;
    padding: 14px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0; z-index: 100;
    border-bottom: 1px solid #e2e8f0;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
  }}
  .topbar .logo {{ font-weight: 700; font-size: 1rem; color: #1e293b; }}
  .topbar .logo span {{ color: #6366f1; }}

  /* ── main container ── */
  .container {{ max-width: 900px; margin: 0 auto; padding: 40px 24px 80px; }}

  h1 {{ text-align: center; font-size: 1.8rem; color: #0f172a; margin-bottom: 4px; font-weight: 800; }}
  .subtitle {{ text-align: center; color: #64748b; font-size: 0.9rem; margin-bottom: 40px; }}

  /* ── sections ── */
  section {{
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 28px 30px;
    margin-bottom: 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,.03);
  }}
  section h2 {{
    font-size: 1.25rem;
    color: #0f172a;
    margin-bottom: 18px;
    padding-bottom: 10px;
    border-bottom: 2px solid #eef2ff;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  section h3 {{
    font-size: 1.05rem;
    color: #334155;
    margin: 22px 0 10px;
  }}

  /* ── tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }}
  th, td {{
    text-align: left;
    padding: 10px 14px;
    border-bottom: 1px solid #f1f5f9;
  }}
  th {{
    background: #f8fafc;
    font-weight: 600;
    color: #475569;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  tr:last-child td {{ border-bottom: none; }}

  .match-yes {{ background: #f0fdf4; }}
  .match-warn {{ background: #fffbeb; }}
  .match-no {{ background: #fef2f2; }}
  .match-maybe {{ background: #fff7ed; }}

  /* ── badges ── */
  .badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
  }}
  .badge-ok {{ background: #dcfce7; color: #166534; }}
  .badge-no {{ background: #fef2f2; color: #991b1b; }}

  /* ── notes ── */
  .note-ok {{ color: #166534; background: #f0fdf4; padding: 10px 14px; border-radius: 8px; border: 1px solid #bbf7d0; }}
  .note-warn {{ color: #92400e; background: #fffbeb; padding: 10px 14px; border-radius: 8px; border: 1px solid #fde68a; }}

  /* ── claims ── */
  .claim-card {{
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    margin-bottom: 12px;
    overflow: hidden;
  }}
  .claim-header {{
    background: #f8fafc;
    padding: 8px 16px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #475569;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .claim-src {{ font-weight: 400; color: #94a3b8; font-size: 0.78rem; }}
  .claim-body {{
    padding: 14px 16px;
    font-size: 0.92rem;
    color: #334155;
    font-style: italic;
  }}

  /* ── summary cards ── */
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
    margin-bottom: 20px;
  }}
  .sum-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
  }}
  .sum-card .num {{
    font-size: 1.8rem;
    font-weight: 800;
    color: #6366f1;
  }}
  .sum-card .label {{
    font-size: 0.82rem;
    color: #64748b;
    margin-top: 2px;
  }}

  /* ── utility ── */
  .muted {{ color: #94a3b8; }}
  ul {{ padding-left: 20px; }}
  li {{ margin-bottom: 4px; }}
  code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; color: #6366f1; }}
  .exp-section {{ margin-bottom: 8px; }}

  /* ── manual review placeholder ── */
  .manual-placeholder {{
    border: 2px dashed #cbd5e1;
    border-radius: 12px;
    padding: 20px 24px;
    margin-top: 18px;
    background: #fafbfc;
    color: #94a3b8;
    font-size: 0.88rem;
    text-align: center;
  }}
  .manual-placeholder strong {{ color: #64748b; }}

  /* ── responsive ── */
  @media (max-width: 640px) {{
    .container {{ padding: 20px 14px 60px; }}
    section {{ padding: 18px 16px; }}
    .summary-grid {{ grid-template-columns: 1fr 1fr; }}
  }}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo">📋 code-<span>audit</span>-paper · 审计报告</div>
</div>

<div class="container">

  <h1>🧪 论文与代码审计报告</h1>
  <p class="subtitle">自动分析结果 — 由 audit.py 生成</p>

  <!-- ═══════════════════════════════════════════════════════ -->
  <!--  Section 1: 论文概览                                     -->
  <!-- ═══════════════════════════════════════════════════════ -->
  <section>
    <h2>📋 1. 论文概览</h2>
    <p class="muted" style="margin-bottom:12px;">从 LaTeX 源码中自动提取的论文结构信息。</p>
    <table>
      <thead><tr><th>类别</th><th>数量</th></tr></thead>
      <tbody>{overview_html}</tbody>
    </table>
  </section>

  <!-- ═══════════════════════════════════════════════════════ -->
  <!--  Section 2: 代码结构分析                                  -->
  <!-- ═══════════════════════════════════════════════════════ -->
  <section>
    <h2>📦 2. 代码结构分析</h2>
    <p class="muted" style="margin-bottom:12px;">对克隆下来的代码仓库的自动分析。</p>

    <div class="summary-grid">
      <div class="sum-card">
        <div class="num">{code_analysis['language']}</div>
        <div class="label">主要语言</div>
      </div>
      <div class="sum-card">
        <div class="num">{code_analysis['total_files']}</div>
        <div class="label">文件总数</div>
      </div>
    </div>

    <h3>文件类型分布</h3>
    <table>
      <thead><tr><th>扩展名</th><th>数量</th></tr></thead>
      <tbody>{file_type_html}</tbody>
    </table>

    <h3>代码仓库能力检测</h3>
    <table>
      <thead><tr><th>状态</th><th>能力</th></tr></thead>
      <tbody>{cap_html}</tbody>
    </table>
  </section>

  <!-- ═══════════════════════════════════════════════════════ -->
  <!--  Section 3: 论文与代码对照                                -->
  <!-- ═══════════════════════════════════════════════════════ -->
  <section>
    <h2>🔍 3. 论文与代码对照</h2>
    <p class="muted" style="margin-bottom:12px;">将论文中提取的声明与代码仓库中的实际实现进行交叉比对。</p>

    <h3>3.1 方法 / 架构</h3>
    <table>
      <thead><tr><th>状态</th><th>方法 / 架构组件</th></tr></thead>
      <tbody>{methods_html}</tbody>
    </table>

    <h3>3.2 数据集</h3>
    <table>
      <thead><tr><th>状态</th><th>数据集</th></tr></thead>
      <tbody>{ds_html}</tbody>
    </table>

    <h3>3.3 指标与结果</h3>
    <table>
      <thead><tr><th>状态</th><th>指标</th></tr></thead>
      <tbody>{metrics_html}</tbody>
    </table>

    <h3>3.4 实验覆盖</h3>
    <ul>{exp_items}</ul>
    {ablation_html}

    <h3>3.5 代码质量备注</h3>
    {quality_html}
  </section>

  <!-- ═══════════════════════════════════════════════════════ -->
  <!--  Section 4: 论文声明详情                                  -->
  <!-- ═══════════════════════════════════════════════════════ -->
  <section>
    <h2>📝 4. 论文声明详情</h2>
    <p class="muted" style="margin-bottom:12px;">从摘要和引言中自动提取的论文声明。</p>
    {claims_html}
  </section>

  <!-- ═══════════════════════════════════════════════════════ -->
  <!--  Section 5: 关键源文件                                    -->
  <!-- ═══════════════════════════════════════════════════════ -->
  <section>
    <h2>📂 5. 关键源文件</h2>
    <p class="muted" style="margin-bottom:12px;">代码仓库中识别到的与论文相关的关键实现文件。</p>
    {keyfiles_html}
  </section>

  <!-- ═══════════════════════════════════════════════════════ -->
  <!--  Section 6: 总结                                         -->
  <!-- ═══════════════════════════════════════════════════════ -->
  <section>
    <h2>📊 6. 自动审计总结</h2>

    <div class="summary-grid">
      <div class="sum-card">
        <div class="num">{len(mapping['matched_methods'])}/{total_methods}</div>
        <div class="label">方法实现覆盖率（{method_pct:.0f}%）</div>
      </div>
      <div class="sum-card">
        <div class="num">{len(mapping['matched_datasets'])}/{total_datasets}</div>
        <div class="label">数据集覆盖率（{dataset_pct:.0f}%）</div>
      </div>
      <div class="sum-card">
        <div class="num">{len(mapping['experiment_coverage'])}</div>
        <div class="label">实验覆盖方面</div>
      </div>
    </div>

    <p class="{'note-ok' if verdict_icon == '✅' else 'note-warn'}">{verdict_icon} {verdict_text}</p>
    {ablation_note}

    <div class="manual-placeholder" style="margin-top:20px;">
      <strong>📌 以上为自动分析结果。</strong><br>
      完整的四维度深度审计（可复现性 · 方法一致性 · 实验细节 · 代码覆盖率）<br>
      需要人工阅读 LaTeX 源码和代码后补充到此页面中。
    </div>
  </section>

</div>

<!-- ═══════════════════════════════════════════════════════ -->
<!--  Embedded JSON data for programmatic access             -->
<!-- ═══════════════════════════════════════════════════════ -->
<script type="application/json" id="audit-data">
{json_data}
</script>

</body>
</html>"""

    report_path = os.path.join(output_dir, "audit_report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

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
    print(f"   （JSON 数据已嵌入 HTML 的 &lt;script&gt; 标签中）")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
