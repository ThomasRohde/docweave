"""Generate large Markdown files with and without annotations for benchmarking."""

from __future__ import annotations

import json
import random
from pathlib import Path

BENCH_DIR = Path(__file__).parent


def _lorem(sentences: int = 3) -> str:
    """Generate pseudo-lorem text."""
    pool = [
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.",
        "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum.",
        "Excepteur sint occaecat cupidatat non proident, sunt in culpa.",
        "Nulla facilisi morbi tempus iaculis urna id volutpat lacus.",
        "Pellentesque habitant morbi tristique senectus et netus et malesuada.",
        "Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere.",
        "Curabitur vitae nunc sed velit dignissim sodales ut eu sem.",
        "Faucibus scelerisque eleifend donec pretium vulputate sapien nec sagittis.",
    ]
    return " ".join(random.choices(pool, k=sentences))


def _code_block(lang: str = "python") -> str:
    snippets = {
        "python": 'def process(data):\n    """Process input data."""\n    result = []\n    for item in data:\n        if item.is_valid():\n            result.append(item.transform())\n    return result',
        "javascript": 'function fetchData(url) {\n  return fetch(url)\n    .then(res => res.json())\n    .then(data => data.results);\n}',
        "bash": '#!/bin/bash\nset -euo pipefail\nfor f in *.md; do\n  echo "Processing $f"\n  docweave inspect "$f"\ndone',
    }
    code = snippets.get(lang, snippets["python"])
    return f"```{lang}\n{code}\n```"


def _table(rows: int = 4) -> str:
    lines = ["| Column A | Column B | Column C |", "|----------|----------|----------|"]
    for i in range(rows):
        lines.append(f"| Value {i+1}A | Value {i+1}B | Value {i+1}C |")
    return "\n".join(lines)


def _list_block(items: int = 5) -> str:
    return "\n".join(f"- {_lorem(1)}" for _ in range(items))


def _annotation(section_idx: int, level: int) -> str:
    tags_pool = ["api", "performance", "security", "architecture", "testing",
                 "deployment", "monitoring", "database", "frontend", "backend",
                 "infrastructure", "documentation", "review", "draft", "complete"]
    statuses = ["draft", "review", "complete", "archived"]
    audiences = ["developer", "architect", "ops", "manager", "all"]

    annotation = {
        "summary": f"Section {section_idx} covers {random.choice(tags_pool)} topics at depth level {level}.",
        "tags": random.sample(tags_pool, k=random.randint(1, 4)),
        "status": random.choice(statuses),
        "audience": random.choice(audiences),
    }
    if random.random() > 0.5:
        annotation["dependencies"] = [f"Section {random.randint(1, max(1, section_idx - 1))}"]
    if random.random() > 0.7:
        annotation["priority"] = random.choice(["low", "medium", "high", "critical"])

    return f"<!-- docweave: {json.dumps(annotation)} -->"


def generate_document(
    num_sections: int,
    with_annotations: bool,
    subsections_per_section: int = 3,
    paragraphs_per_subsection: int = 2,
) -> str:
    """Generate a large Markdown document."""
    parts: list[str] = []

    # Title
    if with_annotations:
        parts.append(_annotation(0, 1))
    parts.append("# Benchmark Document\n")
    parts.append(_lorem(5) + "\n")

    section_counter = 0
    for s in range(1, num_sections + 1):
        section_counter += 1

        # H2 section
        if with_annotations:
            parts.append(_annotation(section_counter, 2))
        parts.append(f"## Section {s}: {random.choice(['Architecture', 'Implementation', 'Testing', 'Deployment', 'Monitoring', 'Security', 'Performance', 'API Design'])} Overview\n")
        parts.append(_lorem(4) + "\n")

        # Add a code block every 3rd section
        if s % 3 == 0:
            parts.append(_code_block(random.choice(["python", "javascript", "bash"])) + "\n")

        # Add a table every 4th section
        if s % 4 == 0:
            parts.append(_table(random.randint(3, 6)) + "\n")

        for sub in range(1, subsections_per_section + 1):
            section_counter += 1

            # H3 subsection
            if with_annotations:
                parts.append(_annotation(section_counter, 3))
            parts.append(f"### {s}.{sub} Detail Topic {sub}\n")

            for _ in range(paragraphs_per_subsection):
                parts.append(_lorem(random.randint(3, 6)) + "\n")

            # Add list blocks
            if random.random() > 0.5:
                parts.append(_list_block(random.randint(3, 7)) + "\n")

            # Occasional H4
            if random.random() > 0.7:
                section_counter += 1
                if with_annotations:
                    parts.append(_annotation(section_counter, 4))
                parts.append(f"#### {s}.{sub}.1 Deep Dive\n")
                parts.append(_lorem(4) + "\n")

    return "\n".join(parts)


def main():
    random.seed(42)  # reproducible

    sizes = {
        "small": {"num_sections": 10, "subsections_per_section": 2, "paragraphs_per_subsection": 2},
        "medium": {"num_sections": 50, "subsections_per_section": 3, "paragraphs_per_subsection": 3},
        "large": {"num_sections": 150, "subsections_per_section": 4, "paragraphs_per_subsection": 3},
        "xlarge": {"num_sections": 500, "subsections_per_section": 4, "paragraphs_per_subsection": 4},
    }

    BENCH_DIR.mkdir(exist_ok=True)

    for size_name, params in sizes.items():
        for annotated in (False, True):
            suffix = "annotated" if annotated else "plain"
            filename = f"{size_name}_{suffix}.md"
            content = generate_document(with_annotations=annotated, **params)
            path = BENCH_DIR / filename
            path.write_text(content, encoding="utf-8")
            line_count = content.count("\n")
            size_kb = len(content.encode("utf-8")) / 1024
            heading_count = content.count("\n#")
            annotation_count = content.count("<!-- docweave:")
            print(f"  {filename:<30s}  {line_count:>6,} lines  {size_kb:>8.1f} KB  "
                  f"{heading_count:>4} headings  {annotation_count:>4} annotations")


if __name__ == "__main__":
    main()
