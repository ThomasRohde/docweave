"""Generate a realistic large document for agentic workflow benchmarking.

Creates a software architecture document with well-defined sections,
each annotated with tags, summaries, status, audience, and dependencies.
An agent must navigate this document to complete specific tasks.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

BENCH_DIR = Path(__file__).parent

# Realistic section taxonomy for a software project
SECTIONS = [
    {
        "title": "System Overview",
        "tags": ["architecture", "overview"],
        "summary": "High-level architecture and system components",
        "status": "complete",
        "audience": "all",
        "subsections": [
            {"title": "Design Philosophy", "tags": ["architecture"], "summary": "Core principles and trade-offs", "status": "complete", "audience": "architect"},
            {"title": "Component Diagram", "tags": ["architecture", "diagrams"], "summary": "Visual component relationships", "status": "review", "audience": "developer"},
            {"title": "Technology Stack", "tags": ["architecture", "infrastructure"], "summary": "Languages, frameworks, and tools used", "status": "complete", "audience": "developer"},
        ],
    },
    {
        "title": "Authentication Service",
        "tags": ["api", "security"],
        "summary": "OAuth2/OIDC authentication and authorization flows",
        "status": "complete",
        "audience": "developer",
        "subsections": [
            {"title": "OAuth2 Flow", "tags": ["api", "security"], "summary": "Authorization code and token exchange flows", "status": "complete", "audience": "developer"},
            {"title": "Token Management", "tags": ["security", "performance"], "summary": "JWT lifecycle, refresh, and revocation", "status": "review", "audience": "developer"},
            {"title": "Rate Limiting", "tags": ["security", "performance"], "summary": "Per-client and per-endpoint rate limits", "status": "draft", "audience": "ops"},
            {"title": "Security Audit Log", "tags": ["security", "compliance"], "summary": "Immutable audit trail for auth events", "status": "draft", "audience": "ops"},
        ],
    },
    {
        "title": "Database Layer",
        "tags": ["database", "infrastructure"],
        "summary": "PostgreSQL schema, migrations, and query patterns",
        "status": "complete",
        "audience": "developer",
        "subsections": [
            {"title": "Schema Design", "tags": ["database"], "summary": "Entity relationships and normalization choices", "status": "complete", "audience": "developer"},
            {"title": "Migration Strategy", "tags": ["database", "deployment"], "summary": "Zero-downtime migration patterns", "status": "complete", "audience": "ops"},
            {"title": "Query Optimization", "tags": ["database", "performance"], "summary": "Index strategy and slow query analysis", "status": "review", "audience": "developer"},
            {"title": "Connection Pooling", "tags": ["database", "performance", "infrastructure"], "summary": "PgBouncer config and pool sizing", "status": "draft", "audience": "ops"},
            {"title": "Backup and Recovery", "tags": ["database", "ops"], "summary": "Point-in-time recovery and backup schedules", "status": "draft", "audience": "ops"},
        ],
    },
    {
        "title": "API Gateway",
        "tags": ["api", "infrastructure"],
        "summary": "Request routing, middleware, and API versioning",
        "status": "review",
        "audience": "developer",
        "subsections": [
            {"title": "Route Configuration", "tags": ["api"], "summary": "Endpoint mapping and path parameters", "status": "complete", "audience": "developer"},
            {"title": "Middleware Pipeline", "tags": ["api", "security"], "summary": "Auth, logging, CORS, and compression middleware", "status": "complete", "audience": "developer"},
            {"title": "API Versioning", "tags": ["api"], "summary": "URL-based versioning strategy and deprecation policy", "status": "review", "audience": "architect"},
            {"title": "Error Handling", "tags": ["api"], "summary": "Structured error responses and error codes", "status": "complete", "audience": "developer"},
            {"title": "GraphQL Integration", "tags": ["api", "frontend"], "summary": "GraphQL schema and resolver architecture", "status": "draft", "audience": "developer"},
        ],
    },
    {
        "title": "Caching Layer",
        "tags": ["performance", "infrastructure"],
        "summary": "Redis caching strategy and invalidation patterns",
        "status": "review",
        "audience": "developer",
        "subsections": [
            {"title": "Cache Strategy", "tags": ["performance"], "summary": "Cache-aside pattern and TTL policies", "status": "complete", "audience": "developer"},
            {"title": "Invalidation Patterns", "tags": ["performance"], "summary": "Event-driven and time-based invalidation", "status": "review", "audience": "developer"},
            {"title": "Redis Cluster Config", "tags": ["performance", "infrastructure"], "summary": "Cluster topology and failover settings", "status": "draft", "audience": "ops"},
        ],
    },
    {
        "title": "Event System",
        "tags": ["architecture", "infrastructure"],
        "summary": "Async event bus, domain events, and CQRS patterns",
        "status": "review",
        "audience": "developer",
        "subsections": [
            {"title": "Event Schema", "tags": ["architecture"], "summary": "Event envelope format and versioning", "status": "complete", "audience": "developer"},
            {"title": "Kafka Configuration", "tags": ["infrastructure"], "summary": "Topic partitioning and consumer groups", "status": "review", "audience": "ops"},
            {"title": "Dead Letter Queue", "tags": ["infrastructure", "ops"], "summary": "Failed event handling and retry policies", "status": "draft", "audience": "ops"},
            {"title": "Event Sourcing", "tags": ["architecture", "database"], "summary": "Event store and projection rebuilds", "status": "draft", "audience": "architect"},
        ],
    },
    {
        "title": "Monitoring and Observability",
        "tags": ["ops", "infrastructure"],
        "summary": "Metrics, logging, tracing, and alerting",
        "status": "review",
        "audience": "ops",
        "subsections": [
            {"title": "Metrics Collection", "tags": ["ops", "performance"], "summary": "Prometheus metrics and custom counters", "status": "complete", "audience": "ops"},
            {"title": "Distributed Tracing", "tags": ["ops", "performance"], "summary": "OpenTelemetry spans and trace propagation", "status": "review", "audience": "developer"},
            {"title": "Log Aggregation", "tags": ["ops"], "summary": "Structured logging and ELK pipeline", "status": "complete", "audience": "ops"},
            {"title": "Alerting Rules", "tags": ["ops"], "summary": "PagerDuty integration and alert thresholds", "status": "draft", "audience": "ops"},
            {"title": "SLO Dashboard", "tags": ["ops", "performance"], "summary": "Service level objectives and error budgets", "status": "draft", "audience": "all"},
        ],
    },
    {
        "title": "CI/CD Pipeline",
        "tags": ["deployment", "infrastructure"],
        "summary": "Build, test, and deployment automation",
        "status": "complete",
        "audience": "developer",
        "subsections": [
            {"title": "Build Configuration", "tags": ["deployment"], "summary": "Docker multi-stage builds and caching", "status": "complete", "audience": "developer"},
            {"title": "Test Strategy", "tags": ["testing", "deployment"], "summary": "Unit, integration, and e2e test stages", "status": "complete", "audience": "developer"},
            {"title": "Deployment Stages", "tags": ["deployment"], "summary": "Canary and blue-green deployment strategies", "status": "review", "audience": "ops"},
            {"title": "Rollback Procedures", "tags": ["deployment", "ops"], "summary": "Automated and manual rollback triggers", "status": "draft", "audience": "ops"},
        ],
    },
    {
        "title": "Frontend Architecture",
        "tags": ["frontend", "architecture"],
        "summary": "React SPA structure, state management, and SSR",
        "status": "review",
        "audience": "developer",
        "subsections": [
            {"title": "Component Library", "tags": ["frontend"], "summary": "Design system and reusable UI components", "status": "complete", "audience": "developer"},
            {"title": "State Management", "tags": ["frontend", "architecture"], "summary": "Redux toolkit and server state with React Query", "status": "review", "audience": "developer"},
            {"title": "Performance Budget", "tags": ["frontend", "performance"], "summary": "Core Web Vitals targets and bundle analysis", "status": "draft", "audience": "developer"},
            {"title": "Accessibility", "tags": ["frontend", "compliance"], "summary": "WCAG 2.1 AA conformance and ARIA patterns", "status": "draft", "audience": "developer"},
        ],
    },
    {
        "title": "Data Processing Pipeline",
        "tags": ["data", "infrastructure"],
        "summary": "ETL jobs, data lake, and analytics pipeline",
        "status": "draft",
        "audience": "developer",
        "subsections": [
            {"title": "Ingestion Layer", "tags": ["data"], "summary": "Streaming ingestion from multiple sources", "status": "draft", "audience": "developer"},
            {"title": "Transformation Rules", "tags": ["data"], "summary": "dbt models and data quality checks", "status": "draft", "audience": "developer"},
            {"title": "Analytics Warehouse", "tags": ["data", "database"], "summary": "Star schema and materialized views", "status": "draft", "audience": "developer"},
        ],
    },
    {
        "title": "Compliance and Governance",
        "tags": ["compliance", "security"],
        "summary": "GDPR, SOC2, and data governance policies",
        "status": "draft",
        "audience": "all",
        "subsections": [
            {"title": "Data Classification", "tags": ["compliance", "security"], "summary": "PII handling and data sensitivity levels", "status": "review", "audience": "all"},
            {"title": "GDPR Compliance", "tags": ["compliance"], "summary": "Right to erasure, data portability, consent management", "status": "draft", "audience": "developer"},
            {"title": "Audit Requirements", "tags": ["compliance", "security"], "summary": "SOC2 controls and evidence collection", "status": "draft", "audience": "ops"},
        ],
    },
]

LOREM_POOL = [
    "The service handles approximately 10,000 requests per second at peak load, requiring careful attention to connection pooling and resource management.",
    "All configuration is loaded from environment variables with sensible defaults, following twelve-factor app principles.",
    "Error responses follow RFC 7807 Problem Details format, providing structured error information to API consumers.",
    "The migration process uses advisory locks to prevent concurrent migrations from running on different instances.",
    "Cache keys are namespaced by service version to prevent stale data after deployments.",
    "Authentication tokens are validated using asymmetric key pairs, with public keys cached for 15 minutes.",
    "The circuit breaker opens after 5 consecutive failures and enters half-open state after 30 seconds.",
    "Database queries are instrumented with OpenTelemetry spans, providing end-to-end latency visibility.",
    "The event schema uses CloudEvents specification v1.0 for interoperability across services.",
    "Static assets are served through a CDN with a 30-day cache policy and content-based hashing for cache busting.",
    "The deployment pipeline requires manual approval for production releases, with automated canary analysis for 15 minutes.",
    "Structured logs include correlation IDs that propagate across service boundaries via HTTP headers.",
    "The data pipeline processes approximately 50GB of raw events daily, with a 4-hour SLA for analytics availability.",
    "RBAC policies are evaluated using Open Policy Agent, with policy bundles deployed independently of application code.",
    "The component library uses Storybook for visual testing and documentation of all UI primitives.",
    "Connection pool sizing is based on the formula: pool_size = (core_count * 2) + disk_spindles, with a minimum of 10.",
    "Kafka consumer groups use cooperative sticky partitioning to minimize rebalance disruption.",
    "The GraphQL schema is generated from TypeScript types using code-first approach with type-graphql decorators.",
    "Alert thresholds are defined as percentage of SLO error budget consumed, with p1 alerts at 50% consumption rate.",
    "Blue-green deployments use DNS-based switching with a 60-second TTL to minimize propagation delay.",
]

CODE_SNIPPETS = [
    ("python", """class AuthMiddleware:
    async def __call__(self, request, call_next):
        token = request.headers.get("Authorization")
        if not token:
            raise HTTPException(401, "Missing auth token")
        claims = await self.verify_token(token)
        request.state.user = claims
        return await call_next(request)"""),
    ("sql", """CREATE INDEX CONCURRENTLY idx_events_created_at
    ON events (created_at DESC)
    WHERE status = 'active'
    AND deleted_at IS NULL;"""),
    ("yaml", """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0"""),
    ("typescript", """interface EventEnvelope<T> {
  id: string;
  source: string;
  type: string;
  specversion: "1.0";
  time: string;
  data: T;
  datacontenttype: "application/json";
}"""),
    ("bash", """#!/bin/bash
# Canary deployment check
CANARY_ERROR_RATE=$(curl -s prometheus/api/v1/query \\
  --data-urlencode 'query=rate(http_errors{canary="true"}[5m])' | jq '.data.result[0].value[1]')
if (( $(echo "$CANARY_ERROR_RATE > 0.01" | bc -l) )); then
  echo "Canary error rate too high, rolling back"
  kubectl rollout undo deployment/api
fi"""),
    ("json", """{
  "rules": [
    {"alert": "HighErrorRate", "expr": "rate(http_5xx[5m]) > 0.05", "for": "5m", "severity": "critical"},
    {"alert": "HighLatency", "expr": "histogram_quantile(0.99, rate(http_duration_bucket[5m])) > 2", "for": "10m", "severity": "warning"}
  ]
}"""),
]


def _body_paragraphs(n: int = 3) -> str:
    return "\n\n".join(random.choices(LOREM_POOL, k=n))


def _maybe_code(prob: float = 0.4) -> str:
    if random.random() < prob:
        lang, code = random.choice(CODE_SNIPPETS)
        return f"\n\n```{lang}\n{code}\n```\n"
    return ""


def _maybe_table(prob: float = 0.2) -> str:
    if random.random() < prob:
        headers = random.choice([
            ("Parameter", "Type", "Default", "Description"),
            ("Metric", "Threshold", "Alert Level", "Action"),
            ("Endpoint", "Method", "Auth Required", "Rate Limit"),
            ("Field", "Type", "Required", "Notes"),
        ])
        rows = []
        for _ in range(random.randint(3, 6)):
            rows.append(tuple(f"value_{random.randint(1,99)}" for _ in headers))
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")
        return "\n\n" + "\n".join(lines) + "\n"
    return ""


def _maybe_list(prob: float = 0.3) -> str:
    if random.random() < prob:
        items = random.randint(3, 6)
        return "\n\n" + "\n".join(f"- {random.choice(LOREM_POOL)[:80]}" for _ in range(items)) + "\n"
    return ""


def generate_annotated() -> str:
    """Generate the annotated version with docweave comments."""
    random.seed(123)
    parts: list[str] = []

    parts.append('<!-- docweave: {"summary": "Complete software architecture document", "tags": ["architecture"], "status": "review", "audience": "all"} -->')
    parts.append("# Platform Architecture Document\n")
    parts.append("This document describes the complete architecture of the platform, covering all major subsystems, their interactions, and operational procedures.\n")

    for section in SECTIONS:
        ann = {
            "summary": section["summary"],
            "tags": section["tags"],
            "status": section["status"],
            "audience": section["audience"],
        }
        parts.append(f'<!-- docweave: {json.dumps(ann)} -->')
        parts.append(f"## {section['title']}\n")
        parts.append(_body_paragraphs(2) + "\n")
        parts.append(_maybe_code() + _maybe_table() + _maybe_list())

        for sub in section.get("subsections", []):
            deps = []
            # Add realistic dependencies
            if "performance" in sub["tags"]:
                deps.append("Monitoring and Observability")
            if "security" in sub["tags"] and sub["title"] != "OAuth2 Flow":
                deps.append("Authentication Service")
            if "deployment" in sub["tags"]:
                deps.append("CI/CD Pipeline")

            sub_ann = {
                "summary": sub["summary"],
                "tags": sub["tags"],
                "status": sub["status"],
                "audience": sub["audience"],
            }
            if deps:
                sub_ann["dependencies"] = deps

            parts.append(f'<!-- docweave: {json.dumps(sub_ann)} -->')
            parts.append(f"### {sub['title']}\n")
            parts.append(_body_paragraphs(random.randint(2, 4)) + "\n")
            parts.append(_maybe_code(0.5) + _maybe_table(0.3) + _maybe_list(0.4))

    return "\n".join(parts)


def generate_plain() -> str:
    """Generate the same document WITHOUT annotations."""
    random.seed(123)  # same seed = same content
    parts: list[str] = []

    parts.append("# Platform Architecture Document\n")
    parts.append("This document describes the complete architecture of the platform, covering all major subsystems, their interactions, and operational procedures.\n")

    for section in SECTIONS:
        parts.append(f"## {section['title']}\n")
        parts.append(_body_paragraphs(2) + "\n")
        parts.append(_maybe_code() + _maybe_table() + _maybe_list())

        for sub in section.get("subsections", []):
            parts.append(f"### {sub['title']}\n")
            parts.append(_body_paragraphs(random.randint(2, 4)) + "\n")
            parts.append(_maybe_code(0.5) + _maybe_table(0.3) + _maybe_list(0.4))

    return "\n".join(parts)


def main():
    BENCH_DIR.mkdir(exist_ok=True)

    annotated = generate_annotated()
    plain = generate_plain()

    ann_path = BENCH_DIR / "architecture_annotated.md"
    plain_path = BENCH_DIR / "architecture_plain.md"

    ann_path.write_text(annotated, encoding="utf-8")
    plain_path.write_text(plain, encoding="utf-8")

    for label, content, path in [("Plain", plain, plain_path), ("Annotated", annotated, ann_path)]:
        lines = content.count("\n")
        size_kb = len(content.encode("utf-8")) / 1024
        headings = content.count("\n#") + (1 if content.startswith("#") else 0)
        annotations = content.count("<!-- docweave:")
        print(f"  {label:<12s}: {path.name}")
        print(f"    {lines:>6,} lines, {size_kb:>7.1f} KB, {headings:>3} headings, {annotations:>3} annotations")

    # Also output section metadata for the benchmark harness
    meta_path = BENCH_DIR / "section_metadata.json"
    meta = []
    for section in SECTIONS:
        meta.append({
            "title": section["title"],
            "tags": section["tags"],
            "status": section["status"],
            "audience": section["audience"],
            "summary": section["summary"],
        })
        for sub in section.get("subsections", []):
            meta.append({
                "title": sub["title"],
                "tags": sub["tags"],
                "status": sub["status"],
                "audience": sub["audience"],
                "summary": sub["summary"],
                "parent": section["title"],
            })
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\n  Section metadata: {meta_path.name} ({len(meta)} entries)")


if __name__ == "__main__":
    main()
