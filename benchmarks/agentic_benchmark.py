"""Agentic workflow benchmark: measure token cost, tool calls, and precision.

Simulates realistic agent tasks against plain vs annotated documents,
measuring the information an agent consumes at each step.

Token estimation: 1 token ≈ 4 characters (GPT/Claude average for English + JSON).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docweave.backends.markdown_native import MarkdownBackend
from docweave.models import NormalizedDocument

BENCH_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count. ~1 token per 4 chars for English/JSON mix."""
    return max(1, len(text) // 4)


def json_tokens(obj: Any) -> int:
    """Estimate tokens for a JSON-serialized object."""
    return estimate_tokens(json.dumps(obj, default=str))


# ---------------------------------------------------------------------------
# Simulated agent operations (mirrors what an LLM agent would do via CLI)
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    command: str
    args: dict
    output_tokens: int
    description: str


@dataclass
class AgentTrace:
    task: str
    strategy: str  # "plain" or "annotated"
    tool_calls: list[ToolCall] = field(default_factory=list)
    sections_examined: int = 0
    target_found: bool = False
    target_sections: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(tc.output_tokens for tc in self.tool_calls)

    @property
    def num_calls(self) -> int:
        return len(self.tool_calls)


class SimulatedAgent:
    """Simulates an LLM agent navigating a docweave document."""

    def __init__(self, backend: MarkdownBackend, path: Path):
        self.backend = backend
        self.path = path
        self.doc = backend.load_view(path)

    def inspect(self, tag: str | None = None) -> tuple[dict, int]:
        """Simulate `docweave inspect` and return (result_dict, token_count)."""
        result = self.backend.inspect(self.path)
        headings = result.headings

        if tag:
            tag_lower = tag.lower()
            headings = [
                h for h in headings
                if tag_lower in [t.lower() for t in h.annotations.get("tags", [])]
            ]

        result_dict = {
            "file": result.file,
            "backend": result.backend,
            "block_count": result.block_count,
            "headings": [h.model_dump() for h in headings],
        }
        tokens = json_tokens(result_dict)
        return result_dict, tokens

    def view_section(self, section_name: str) -> tuple[list[dict], int]:
        """Simulate `docweave view --section NAME`."""
        section_lower = section_name.lower()
        blocks = [
            b for b in self.doc.blocks
            if any(section_lower == s.lower() for s in b.section_path)
        ]
        block_dicts = [b.model_dump() for b in blocks]
        tokens = json_tokens(block_dicts)
        return block_dicts, tokens

    def view_tag(self, tag: str) -> tuple[list[dict], int]:
        """Simulate `docweave view --tag TAG`."""
        tag_lower = tag.lower()
        # Find headings with matching tag
        matching_headings = set()
        for b in self.doc.blocks:
            if b.kind == "heading" and tag_lower in [
                t.lower() for t in b.annotations.get("tags", [])
            ]:
                matching_headings.add(b.text.lower())

        blocks = [
            b for b in self.doc.blocks
            if any(s.lower() in matching_headings for s in b.section_path)
        ]
        block_dicts = [b.model_dump() for b in blocks]
        tokens = json_tokens(block_dicts)
        return block_dicts, tokens

    def view_all(self) -> tuple[list[dict], int]:
        """Simulate `docweave view` (full document)."""
        block_dicts = [b.model_dump() for b in self.doc.blocks]
        tokens = json_tokens(block_dicts)
        return block_dicts, tokens

    def find(self, query: str) -> tuple[list[dict], int]:
        """Simulate `docweave find <query>`."""
        from docweave.anchors import search_blocks
        matches = search_blocks(self.doc, query)
        match_dicts = [m.model_dump() for m in matches]
        tokens = json_tokens(match_dicts)
        return match_dicts, tokens


# ---------------------------------------------------------------------------
# Agentic task definitions
# ---------------------------------------------------------------------------

def task_find_performance_sections(agent: SimulatedAgent, has_annotations: bool) -> AgentTrace:
    """Task: Find all sections related to performance optimization.

    An agent needs to identify which sections discuss performance topics
    to write a performance review document.
    """
    task = "Find all sections related to performance optimization"
    trace = AgentTrace(task=task, strategy="annotated" if has_annotations else "plain")

    if has_annotations:
        # Strategy: inspect with --tag performance → done
        result, tokens = agent.inspect(tag="performance")
        trace.tool_calls.append(ToolCall(
            command="inspect", args={"tag": "performance"},
            output_tokens=tokens, description="Inspect with tag filter for performance",
        ))
        trace.sections_examined = len(result["headings"])
        trace.target_sections = [h["text"] for h in result["headings"]]
        trace.target_found = len(trace.target_sections) > 0
    else:
        # Strategy: inspect → read all headings → view each section to check content
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect full document",
        ))

        # Agent must read each section to determine if it's about performance
        for heading in result["headings"]:
            blocks, vtokens = agent.view_section(heading["text"])
            trace.tool_calls.append(ToolCall(
                command="view", args={"section": heading["text"]},
                output_tokens=vtokens,
                description=f"View section '{heading['text']}' to check for performance content",
            ))
            trace.sections_examined += 1

            # Simulate agent detecting performance-related content
            full_text = " ".join(b["text"] for b in blocks).lower()
            if any(kw in full_text for kw in ["performance", "latency", "throughput", "cache", "optimization", "pool"]):
                trace.target_sections.append(heading["text"])

        trace.target_found = len(trace.target_sections) > 0

    return trace


def task_find_draft_sections(agent: SimulatedAgent, has_annotations: bool) -> AgentTrace:
    """Task: Find all sections in draft status that need writing.

    An agent triaging work needs to identify incomplete sections.
    """
    task = "Find all sections in draft status"
    trace = AgentTrace(task=task, strategy="annotated" if has_annotations else "plain")

    if has_annotations:
        # Strategy: inspect → filter headings by status annotation
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect to read annotations",
        ))
        for heading in result["headings"]:
            ann = heading.get("annotations", {})
            if ann.get("status") == "draft":
                trace.target_sections.append(heading["text"])
        trace.sections_examined = len(result["headings"])
        trace.target_found = len(trace.target_sections) > 0
    else:
        # Strategy: no status metadata available — must read every section
        # and infer draft status from content (short sections, TODO markers, etc.)
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect full document",
        ))

        for heading in result["headings"]:
            blocks, vtokens = agent.view_section(heading["text"])
            trace.tool_calls.append(ToolCall(
                command="view", args={"section": heading["text"]},
                output_tokens=vtokens,
                description=f"View section '{heading['text']}' to assess completeness",
            ))
            trace.sections_examined += 1

            # Agent heuristic: short sections or few blocks might be drafts
            # But this is unreliable — the agent can't truly know status without annotations
            content_len = sum(len(b["text"]) for b in blocks)
            if content_len < 500:  # crude heuristic, will miss many
                trace.target_sections.append(heading["text"])

        trace.target_found = len(trace.target_sections) > 0

    return trace


def task_edit_security_section(agent: SimulatedAgent, has_annotations: bool) -> AgentTrace:
    """Task: Find and prepare to edit the token management security section.

    An agent needs to locate the specific section about JWT token lifecycle
    to update the refresh token policy.
    """
    task = "Find the token management section to update refresh policy"
    target = "Token Management"
    trace = AgentTrace(task=task, strategy="annotated" if has_annotations else "plain")

    if has_annotations:
        # Strategy: inspect --tag security → scan summaries → view target
        result, tokens = agent.inspect(tag="security")
        trace.tool_calls.append(ToolCall(
            command="inspect", args={"tag": "security"},
            output_tokens=tokens, description="Inspect filtered by security tag",
        ))

        # Agent reads summaries in the inspect result to find the right section
        found = False
        for heading in result["headings"]:
            ann = heading.get("annotations", {})
            summary = ann.get("summary", "").lower()
            if "token" in summary or "jwt" in summary:
                blocks, vtokens = agent.view_section(heading["text"])
                trace.tool_calls.append(ToolCall(
                    command="view", args={"section": heading["text"]},
                    output_tokens=vtokens,
                    description=f"View target section '{heading['text']}'",
                ))
                trace.sections_examined += 1
                trace.target_sections.append(heading["text"])
                found = True
                break
        trace.target_found = found
    else:
        # Strategy: inspect → scan headings by name → try find → view candidates
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect full document",
        ))

        # Agent tries to match heading names
        candidates = []
        for heading in result["headings"]:
            text_lower = heading["text"].lower()
            if "token" in text_lower or "auth" in text_lower or "security" in text_lower:
                candidates.append(heading)

        if not candidates:
            # Fallback: use find command
            matches, ftokens = agent.find("token")
            trace.tool_calls.append(ToolCall(
                command="find", args={"query": "token"},
                output_tokens=ftokens, description="Search for 'token' in document",
            ))

        # View each candidate to confirm
        for cand in candidates:
            blocks, vtokens = agent.view_section(cand["text"])
            trace.tool_calls.append(ToolCall(
                command="view", args={"section": cand["text"]},
                output_tokens=vtokens,
                description=f"View candidate section '{cand['text']}'",
            ))
            trace.sections_examined += 1

            full_text = " ".join(b["text"] for b in blocks).lower()
            if "refresh" in full_text or "jwt" in full_text or "token" in full_text:
                trace.target_sections.append(cand["text"])
                if cand["text"] == target:
                    trace.target_found = True
                    break  # Agent found it, stops looking

    return trace


def task_ops_audience_sections(agent: SimulatedAgent, has_annotations: bool) -> AgentTrace:
    """Task: Find all sections relevant to the ops team.

    An ops engineer needs to know which sections are relevant to them.
    """
    task = "Find all sections for ops audience"
    trace = AgentTrace(task=task, strategy="annotated" if has_annotations else "plain")

    if has_annotations:
        # Strategy: inspect → filter by audience annotation
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect to read audience annotations",
        ))
        for heading in result["headings"]:
            ann = heading.get("annotations", {})
            audience = ann.get("audience", "")
            if audience in ("ops", "all"):
                trace.target_sections.append(heading["text"])
        trace.sections_examined = len(result["headings"])
        trace.target_found = len(trace.target_sections) > 0
    else:
        # Strategy: must read everything — no audience metadata
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect full document",
        ))

        # Agent reads every section trying to infer audience from content
        for heading in result["headings"]:
            blocks, vtokens = agent.view_section(heading["text"])
            trace.tool_calls.append(ToolCall(
                command="view", args={"section": heading["text"]},
                output_tokens=vtokens,
                description=f"View section '{heading['text']}' to infer audience",
            ))
            trace.sections_examined += 1

            full_text = " ".join(b["text"] for b in blocks).lower()
            if any(kw in full_text for kw in [
                "deploy", "monitor", "alert", "ops", "infrastructure",
                "cluster", "backup", "rollback", "pagerduty", "slo",
            ]):
                trace.target_sections.append(heading["text"])

        trace.target_found = len(trace.target_sections) > 0

    return trace


def task_dependency_analysis(agent: SimulatedAgent, has_annotations: bool) -> AgentTrace:
    """Task: Find what sections depend on the Authentication Service.

    An architect wants to assess the blast radius of changing the auth service.
    """
    task = "Find sections that depend on Authentication Service"
    trace = AgentTrace(task=task, strategy="annotated" if has_annotations else "plain")

    if has_annotations:
        # Strategy: inspect → check dependency annotations
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect to read dependency annotations",
        ))
        for heading in result["headings"]:
            ann = heading.get("annotations", {})
            deps = ann.get("dependencies", [])
            if any("authentication" in d.lower() for d in deps):
                trace.target_sections.append(heading["text"])
        trace.sections_examined = len(result["headings"])
        trace.target_found = len(trace.target_sections) > 0
    else:
        # Strategy: search for references, then view each match to verify
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect full document",
        ))

        matches, ftokens = agent.find("authentication")
        trace.tool_calls.append(ToolCall(
            command="find", args={"query": "authentication"},
            output_tokens=ftokens, description="Search for 'authentication' references",
        ))

        matches2, ftokens2 = agent.find("auth")
        trace.tool_calls.append(ToolCall(
            command="find", args={"query": "auth"},
            output_tokens=ftokens2, description="Search for 'auth' references",
        ))

        # Deduplicate matched sections and view them
        seen_sections = set()
        all_matches = matches + matches2
        for m in all_matches:
            # Find which section this block belongs to
            for b in agent.doc.blocks:
                if b.block_id == m["block_id"] and b.section_path:
                    sec = b.section_path[-1]
                    if sec not in seen_sections and sec != "Authentication Service":
                        seen_sections.add(sec)
                        blocks, vtokens = agent.view_section(sec)
                        trace.tool_calls.append(ToolCall(
                            command="view", args={"section": sec},
                            output_tokens=vtokens,
                            description=f"View section '{sec}' to verify dependency",
                        ))
                        trace.sections_examined += 1
                        full_text = " ".join(bl["text"] for bl in blocks).lower()
                        if "auth" in full_text:
                            trace.target_sections.append(sec)

        trace.target_found = len(trace.target_sections) > 0

    return trace


def task_targeted_edit_by_tag(agent: SimulatedAgent, has_annotations: bool) -> AgentTrace:
    """Task: View only the compliance-related content for a review.

    A compliance officer needs to review all compliance sections.
    """
    task = "View all compliance sections for review"
    trace = AgentTrace(task=task, strategy="annotated" if has_annotations else "plain")

    if has_annotations:
        # Strategy: view --tag compliance → get exactly the right blocks
        blocks, tokens = agent.view_tag("compliance")
        trace.tool_calls.append(ToolCall(
            command="view", args={"tag": "compliance"},
            output_tokens=tokens, description="View filtered by compliance tag",
        ))
        seen = set()
        for b in blocks:
            if b["kind"] == "heading":
                seen.add(b["text"])
        trace.target_sections = list(seen)
        trace.sections_examined = len(seen)
        trace.target_found = len(trace.target_sections) > 0
    else:
        # Strategy: must read every section to find compliance content
        result, tokens = agent.inspect()
        trace.tool_calls.append(ToolCall(
            command="inspect", args={},
            output_tokens=tokens, description="Inspect full document",
        ))

        # Try find first
        matches, ftokens = agent.find("compliance")
        trace.tool_calls.append(ToolCall(
            command="find", args={"query": "compliance"},
            output_tokens=ftokens, description="Search for 'compliance'",
        ))

        # But agent still needs full context of those sections
        seen = set()
        for m in matches:
            for b in agent.doc.blocks:
                if b.block_id == m["block_id"] and b.section_path:
                    sec = b.section_path[-1]
                    if sec not in seen:
                        seen.add(sec)
                        blocks, vtokens = agent.view_section(sec)
                        trace.tool_calls.append(ToolCall(
                            command="view", args={"section": sec},
                            output_tokens=vtokens,
                            description=f"View section '{sec}' for compliance content",
                        ))
                        trace.sections_examined += 1
                        trace.target_sections.append(sec)

        # Agent also scans headings for compliance keywords it might have missed
        for heading in result["headings"]:
            if heading["text"] not in seen:
                text_lower = heading["text"].lower()
                if any(kw in text_lower for kw in ["compliance", "audit", "gdpr", "governance"]):
                    blocks, vtokens = agent.view_section(heading["text"])
                    trace.tool_calls.append(ToolCall(
                        command="view", args={"section": heading["text"]},
                        output_tokens=vtokens,
                        description=f"View section '{heading['text']}' (heading match)",
                    ))
                    trace.sections_examined += 1
                    trace.target_sections.append(heading["text"])

        trace.target_found = len(trace.target_sections) > 0

    return trace


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def format_trace(trace: AgentTrace, verbose: bool = False) -> str:
    lines = []
    lines.append(f"  Strategy: {trace.strategy}")
    lines.append(f"  Tool calls: {trace.num_calls}")
    lines.append(f"  Total tokens consumed: {trace.total_tokens:,}")
    lines.append(f"  Sections examined: {trace.sections_examined}")
    lines.append(f"  Target found: {trace.target_found}")
    lines.append(f"  Sections identified: {len(trace.target_sections)}")
    if verbose:
        for tc in trace.tool_calls:
            lines.append(f"    [{tc.command}] {tc.description} → {tc.output_tokens:,} tokens")
    return "\n".join(lines)


def main():
    ann_path = BENCH_DIR / "architecture_annotated.md"
    plain_path = BENCH_DIR / "architecture_plain.md"

    if not ann_path.exists() or not plain_path.exists():
        print("ERROR: Run generate_agentic_doc.py first.")
        sys.exit(1)

    backend = MarkdownBackend()
    agent_plain = SimulatedAgent(backend, plain_path)
    agent_ann = SimulatedAgent(backend, ann_path)

    tasks = [
        ("Find performance sections", task_find_performance_sections),
        ("Find draft sections", task_find_draft_sections),
        ("Edit token management", task_edit_security_section),
        ("Find ops audience sections", task_ops_audience_sections),
        ("Dependency analysis", task_dependency_analysis),
        ("View compliance content", task_targeted_edit_by_tag),
    ]

    print("=" * 90)
    print("AGENTIC WORKFLOW BENCHMARK — Annotations vs Plain Documents")
    print("=" * 90)

    # File stats
    for label, path in [("Plain", plain_path), ("Annotated", ann_path)]:
        content = path.read_text("utf-8")
        doc = backend.load_view(path)
        ann_count = content.count("<!-- docweave:")
        print(f"\n  {label}: {path.name}")
        print(f"    {len(content):,} chars, {content.count(chr(10)):,} lines, "
              f"{doc.block_count} blocks, {len(doc.headings)} headings, {ann_count} annotations")

    all_traces: list[tuple[str, AgentTrace, AgentTrace]] = []

    for task_name, task_func in tasks:
        print(f"\n{'─' * 90}")
        print(f"Task: {task_name}")
        print(f"{'─' * 90}")

        trace_plain = task_func(agent_plain, has_annotations=False)
        trace_ann = task_func(agent_ann, has_annotations=True)
        all_traces.append((task_name, trace_plain, trace_ann))

        print(f"\n  WITHOUT annotations:")
        print(format_trace(trace_plain, verbose=True))
        print(f"\n  WITH annotations:")
        print(format_trace(trace_ann, verbose=True))

        # Comparison
        token_saved = trace_plain.total_tokens - trace_ann.total_tokens
        token_pct = (token_saved / trace_plain.total_tokens * 100) if trace_plain.total_tokens > 0 else 0
        calls_saved = trace_plain.num_calls - trace_ann.num_calls
        print(f"\n  Savings:")
        print(f"    Tokens: {token_saved:+,} ({token_pct:+.1f}%)")
        print(f"    Tool calls: {calls_saved:+d}")

    # Summary table
    print(f"\n{'=' * 90}")
    print("SUMMARY")
    print(f"{'=' * 90}\n")

    print(f"{'Task':<30s} │ {'Plain':>10s} │ {'Annotated':>10s} │ {'Saved':>10s} │ {'Saved%':>7s} │ {'Calls P':>7s} │ {'Calls A':>7s}")
    print(f"{'─' * 30}─┼─{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 7}─┼─{'─' * 7}─┼─{'─' * 7}")

    total_plain_tokens = 0
    total_ann_tokens = 0
    total_plain_calls = 0
    total_ann_calls = 0

    for task_name, tp, ta in all_traces:
        saved = tp.total_tokens - ta.total_tokens
        pct = (saved / tp.total_tokens * 100) if tp.total_tokens > 0 else 0
        print(f"{task_name:<30s} │ {tp.total_tokens:>10,} │ {ta.total_tokens:>10,} │ "
              f"{saved:>+10,} │ {pct:>+6.1f}% │ {tp.num_calls:>7d} │ {ta.num_calls:>7d}")
        total_plain_tokens += tp.total_tokens
        total_ann_tokens += ta.total_tokens
        total_plain_calls += tp.num_calls
        total_ann_calls += ta.num_calls

    total_saved = total_plain_tokens - total_ann_tokens
    total_pct = (total_saved / total_plain_tokens * 100) if total_plain_tokens > 0 else 0
    print(f"{'─' * 30}─┼─{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 7}─┼─{'─' * 7}─┼─{'─' * 7}")
    print(f"{'TOTAL':<30s} │ {total_plain_tokens:>10,} │ {total_ann_tokens:>10,} │ "
          f"{total_saved:>+10,} │ {total_pct:>+6.1f}% │ {total_plain_calls:>7d} │ {total_ann_calls:>7d}")

    # Cost estimation
    print(f"\n{'=' * 90}")
    print("COST ESTIMATION (Claude Sonnet input pricing: $3/MTok)")
    print(f"{'=' * 90}\n")
    cost_plain = total_plain_tokens / 1_000_000 * 3.0
    cost_ann = total_ann_tokens / 1_000_000 * 3.0
    print(f"  Plain strategy cost:     ${cost_plain:.4f}")
    print(f"  Annotated strategy cost: ${cost_ann:.4f}")
    print(f"  Savings per run:         ${cost_plain - cost_ann:.4f}")
    print(f"  At 100 agent runs/day:   ${(cost_plain - cost_ann) * 100:.2f}/day")
    print(f"  At 1000 agent runs/day:  ${(cost_plain - cost_ann) * 1000:.2f}/day")

    # Qualitative analysis
    print(f"\n{'=' * 90}")
    print("QUALITATIVE ANALYSIS")
    print(f"{'=' * 90}\n")

    print("  Precision improvement with annotations:")
    for task_name, tp, ta in all_traces:
        plain_precision = "N/A"
        ann_precision = "N/A"
        # Draft status is the starkest example — can't determine status without annotations
        if "draft" in task_name.lower():
            print(f"    {task_name}:")
            print(f"      Plain: heuristic-based (unreliable) — found {len(tp.target_sections)} via content length guess")
            print(f"      Annotated: metadata-based (exact) — found {len(ta.target_sections)} with status='draft'")
        elif "audience" in task_name.lower():
            print(f"    {task_name}:")
            print(f"      Plain: keyword-based (noisy) — found {len(tp.target_sections)} via content inference")
            print(f"      Annotated: metadata-based (exact) — found {len(ta.target_sections)} with audience='ops'")
        elif "depend" in task_name.lower():
            print(f"    {task_name}:")
            print(f"      Plain: text search (misses implicit deps) — found {len(tp.target_sections)}")
            print(f"      Annotated: explicit dependency graph — found {len(ta.target_sections)}")

    print(f"\n  Turnaround (tool calls as proxy for agent turns):")
    for task_name, tp, ta in all_traces:
        reduction = tp.num_calls - ta.num_calls
        pct = (reduction / tp.num_calls * 100) if tp.num_calls > 0 else 0
        print(f"    {task_name}: {tp.num_calls} → {ta.num_calls} calls ({reduction:+d}, {pct:+.0f}%)")

    # Save results
    results = {
        "tasks": [],
        "totals": {
            "plain_tokens": total_plain_tokens,
            "annotated_tokens": total_ann_tokens,
            "token_savings": total_saved,
            "token_savings_pct": round(total_pct, 1),
            "plain_calls": total_plain_calls,
            "annotated_calls": total_ann_calls,
        },
    }
    for task_name, tp, ta in all_traces:
        results["tasks"].append({
            "task": task_name,
            "plain": {"tokens": tp.total_tokens, "calls": tp.num_calls, "sections_found": len(tp.target_sections)},
            "annotated": {"tokens": ta.total_tokens, "calls": ta.num_calls, "sections_found": len(ta.target_sections)},
        })
    results_path = BENCH_DIR / "agentic_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n  Results saved to {results_path}")


if __name__ == "__main__":
    main()
