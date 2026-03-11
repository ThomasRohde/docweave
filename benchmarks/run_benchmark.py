"""Benchmark docweave operations on plain vs annotated Markdown files.

Measures: load_view, inspect, view (with/without --tag), apply (set_context),
and find across multiple document sizes.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Add src to path so we can import docweave directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docweave.backends.markdown_native import MarkdownBackend
from docweave.anchors import Anchor, resolve_anchor
from docweave.plan.schema import PatchFile
from docweave.plan.planner import generate_plan
from docweave.plan.applier import apply_plan

BENCH_DIR = Path(__file__).parent
WARMUP_RUNS = 3
BENCH_RUNS = 20


@dataclass
class BenchResult:
    name: str
    size: str
    variant: str  # "plain" or "annotated"
    times_ms: list[float] = field(default_factory=list)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms)

    @property
    def median_ms(self) -> float:
        return statistics.median(self.times_ms)

    @property
    def stdev_ms(self) -> float:
        return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.times_ms)

    @property
    def max_ms(self) -> float:
        return max(self.times_ms)


def bench(func, warmup: int = WARMUP_RUNS, runs: int = BENCH_RUNS) -> list[float]:
    """Run func warmup+runs times, return timing for the last `runs` iterations."""
    for _ in range(warmup):
        func()
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        func()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    return times


def benchmark_load_view(backend: MarkdownBackend, path: Path) -> list[float]:
    return bench(lambda: backend.load_view(path))


def benchmark_inspect(backend: MarkdownBackend, path: Path) -> list[float]:
    return bench(lambda: backend.inspect(path))


def benchmark_tag_filter(backend: MarkdownBackend, path: Path) -> list[float]:
    """Simulate the --tag filter that inspect+view use."""
    def run():
        result = backend.inspect(path)
        # Filter headings by tag (like CLI --tag option)
        filtered = [
            h for h in result.headings
            if "api" in [t.lower() for t in h.annotations.get("tags", [])]
        ]
        return filtered
    return bench(run)


def benchmark_resolve_anchor(backend: MarkdownBackend, path: Path) -> list[float]:
    """Resolve anchors by heading text — tests annotation-enriched blocks."""
    doc = backend.load_view(path)
    # Pick a heading from the middle of the document
    headings = [b for b in doc.blocks if b.kind == "heading"]
    if len(headings) < 3:
        return [0.0]
    target_heading = headings[len(headings) // 2].text
    anchor = Anchor(by="heading", value=target_heading)

    def run():
        resolve_anchor(doc, anchor)

    return bench(run)


def _make_patch(operations: list[dict]) -> PatchFile:
    """Build a PatchFile from operation dicts."""
    return PatchFile(version=1, target={"backend": "auto"}, operations=operations)


def benchmark_plan_generation(backend: MarkdownBackend, path: Path) -> list[float]:
    """Generate an execution plan from a patch targeting a heading."""
    doc = backend.load_view(path)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    if not headings:
        return [0.0]
    target = headings[0].text

    patch = _make_patch([{
        "id": "op_bench_replace",
        "op": "replace_block",
        "anchor": {"by": "heading", "value": target},
        "content": {"kind": "markdown", "value": "Replaced content for benchmarking purposes.\n"},
    }])

    def run():
        generate_plan(path, patch)

    return bench(run)


def benchmark_set_context(backend: MarkdownBackend, path: Path, tmp_dir: Path) -> list[float]:
    """Apply a set_context operation (annotation write)."""
    import shutil
    doc = backend.load_view(path)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    if not headings:
        return [0.0]
    target = headings[0].text

    patch = _make_patch([{
        "id": "op_bench_context",
        "op": "set_context",
        "anchor": {"by": "heading", "value": target},
        "context": {"summary": "Benchmark annotation", "tags": ["benchmark", "test"], "status": "complete"},
    }])

    def run():
        # Copy file to temp so we can write safely
        tmp_file = tmp_dir / path.name
        shutil.copy2(path, tmp_file)
        plan = generate_plan(tmp_file, patch)
        apply_plan(tmp_file, plan)

    return bench(run, warmup=2, runs=10)


def benchmark_full_pipeline(backend: MarkdownBackend, path: Path, tmp_dir: Path) -> list[float]:
    """Full pipeline: load → inspect → plan → apply (append)."""
    import shutil
    headings_cache = [b.text for b in backend.load_view(path).blocks if b.kind == "heading"]
    if not headings_cache:
        return [0.0]
    target = headings_cache[0]

    patch = _make_patch([{
        "id": "op_bench_append",
        "op": "insert_after",
        "anchor": {"by": "heading", "value": target},
        "content": {"kind": "markdown", "value": "Appended benchmark paragraph.\n"},
    }])

    def run():
        tmp_file = tmp_dir / path.name
        shutil.copy2(path, tmp_file)
        _ = backend.inspect(tmp_file)
        plan = generate_plan(tmp_file, patch)
        apply_plan(tmp_file, plan)

    return bench(run, warmup=2, runs=10)


def format_table(results: list[BenchResult]) -> str:
    """Format results as a Markdown table."""
    lines = []
    lines.append("| Size | Variant | Operation | Mean (ms) | Median (ms) | StdDev (ms) | Min (ms) | Max (ms) |")
    lines.append("|------|---------|-----------|-----------|-------------|-------------|----------|----------|")
    for r in results:
        lines.append(
            f"| {r.size:<6s} | {r.variant:<9s} | {r.name:<20s} | "
            f"{r.mean_ms:>9.2f} | {r.median_ms:>11.2f} | {r.stdev_ms:>11.2f} | "
            f"{r.min_ms:>8.2f} | {r.max_ms:>8.2f} |"
        )
    return "\n".join(lines)


def compute_overhead(results: list[BenchResult]) -> str:
    """Compute annotation overhead as % difference."""
    lines = []
    lines.append("\n| Size | Operation | Plain Mean (ms) | Annotated Mean (ms) | Overhead (%) | Overhead (ms) |")
    lines.append("|------|-----------|-----------------|---------------------|--------------|---------------|")

    # Group by (size, name)
    grouped: dict[tuple[str, str], dict[str, BenchResult]] = {}
    for r in results:
        key = (r.size, r.name)
        if key not in grouped:
            grouped[key] = {}
        grouped[key][r.variant] = r

    for (size, name), variants in sorted(grouped.items()):
        if "plain" in variants and "annotated" in variants:
            plain = variants["plain"].mean_ms
            annot = variants["annotated"].mean_ms
            overhead_pct = ((annot - plain) / plain * 100) if plain > 0 else 0
            overhead_ms = annot - plain
            lines.append(
                f"| {size:<6s} | {name:<20s} | {plain:>15.2f} | {annot:>19.2f} | "
                f"{overhead_pct:>+12.1f}% | {overhead_ms:>+13.2f} |"
            )

    return "\n".join(lines)


def file_stats(path: Path) -> dict:
    content = path.read_text("utf-8")
    return {
        "file": path.name,
        "size_kb": len(content.encode("utf-8")) / 1024,
        "lines": content.count("\n"),
        "headings": content.count("\n#") + (1 if content.startswith("#") else 0),
        "annotations": content.count("<!-- docweave:"),
    }


def main():
    import tempfile

    backend = MarkdownBackend()
    all_results: list[BenchResult] = []

    sizes = ["small", "medium", "large", "xlarge"]
    variants = ["plain", "annotated"]

    # Check that files exist
    for size in sizes:
        for var in variants:
            p = BENCH_DIR / f"{size}_{var}.md"
            if not p.exists():
                print(f"ERROR: {p} not found. Run generate_test_files.py first.")
                sys.exit(1)

    # Print file stats
    print("=" * 90)
    print("DOCWEAVE ANNOTATIONS BENCHMARK")
    print("=" * 90)
    print("\n## Test File Statistics\n")
    print(f"{'File':<30s}  {'Size (KB)':>10s}  {'Lines':>7s}  {'Headings':>9s}  {'Annotations':>12s}")
    print("-" * 75)
    for size in sizes:
        for var in variants:
            p = BENCH_DIR / f"{size}_{var}.md"
            st = file_stats(p)
            print(f"{st['file']:<30s}  {st['size_kb']:>10.1f}  {st['lines']:>7,}  "
                  f"{st['headings']:>9}  {st['annotations']:>12}")
    print()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        for size in sizes:
            for var in variants:
                path = BENCH_DIR / f"{size}_{var}.md"
                prefix = f"[{size}/{var}]"
                print(f"{prefix} Running benchmarks on {path.name}...")

                # 1. load_view
                r = BenchResult(name="load_view", size=size, variant=var)
                r.times_ms = benchmark_load_view(backend, path)
                all_results.append(r)

                # 2. inspect
                r = BenchResult(name="inspect", size=size, variant=var)
                r.times_ms = benchmark_inspect(backend, path)
                all_results.append(r)

                # 3. tag_filter (inspect + filter)
                r = BenchResult(name="tag_filter", size=size, variant=var)
                r.times_ms = benchmark_tag_filter(backend, path)
                all_results.append(r)

                # 4. resolve_anchor
                r = BenchResult(name="resolve_anchor", size=size, variant=var)
                r.times_ms = benchmark_resolve_anchor(backend, path)
                all_results.append(r)

                # 5. plan_generation
                r = BenchResult(name="plan_generation", size=size, variant=var)
                r.times_ms = benchmark_plan_generation(backend, path)
                all_results.append(r)

                # 6. set_context
                r = BenchResult(name="set_context", size=size, variant=var)
                r.times_ms = benchmark_set_context(backend, path, tmp_path)
                all_results.append(r)

                # 7. full_pipeline
                r = BenchResult(name="full_pipeline", size=size, variant=var)
                r.times_ms = benchmark_full_pipeline(backend, path, tmp_path)
                all_results.append(r)

    # Print results
    print("\n" + "=" * 90)
    print("## Detailed Results\n")
    print(format_table(all_results))

    print("\n" + "=" * 90)
    print("## Annotation Overhead Analysis\n")
    print(compute_overhead(all_results))

    # Summary
    print("\n" + "=" * 90)
    print("## Summary\n")

    # Compute average overhead per operation across sizes
    grouped: dict[str, list[float]] = {}
    for r in all_results:
        if r.variant == "annotated":
            # Find matching plain
            plain = [x for x in all_results
                     if x.size == r.size and x.name == r.name and x.variant == "plain"]
            if plain:
                pct = ((r.mean_ms - plain[0].mean_ms) / plain[0].mean_ms * 100)
                if r.name not in grouped:
                    grouped[r.name] = []
                grouped[r.name].append(pct)

    print(f"{'Operation':<20s}  {'Avg Overhead':>14s}")
    print("-" * 38)
    for op, pcts in sorted(grouped.items()):
        avg = statistics.mean(pcts)
        print(f"{op:<20s}  {avg:>+13.1f}%")

    # Save raw data as JSON
    raw_data = []
    for r in all_results:
        raw_data.append({
            "name": r.name,
            "size": r.size,
            "variant": r.variant,
            "mean_ms": round(r.mean_ms, 3),
            "median_ms": round(r.median_ms, 3),
            "stdev_ms": round(r.stdev_ms, 3),
            "min_ms": round(r.min_ms, 3),
            "max_ms": round(r.max_ms, 3),
            "runs": len(r.times_ms),
        })
    raw_path = BENCH_DIR / "results.json"
    raw_path.write_text(json.dumps(raw_data, indent=2), encoding="utf-8")
    print(f"\nRaw results saved to {raw_path}")


if __name__ == "__main__":
    main()
