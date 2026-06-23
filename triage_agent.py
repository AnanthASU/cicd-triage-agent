"""
CI/CD Failure Triage Agent

Free, local, lightweight starter agent for analyzing Jenkins/CI build logs.

No paid LLM API is required. The design is intentionally tool-based so you can
later swap the rule-based classifier with a real LLM + RAG layer.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class Evidence:
    line_number: int
    text: str
    pattern: str


@dataclass
class FailureCategory:
    key: str
    label: str
    confidence: float
    root_cause: str
    owner_hint: str
    recommended_actions: List[str]


@dataclass
class TriageReport:
    source_name: str
    category: FailureCategory
    evidence: List[Evidence]
    known_fixes: List[Dict[str, str]]
    impacted_areas: List[str]
    teams_summary: str
    markdown: str


PATTERNS: Dict[str, List[Tuple[str, str, float]]] = {
    "FRONTEND_TEST_FAILURE": [
        (r"TestingLibraryElementError", "React Testing Library query failure", 0.25),
        (r"Unable to find an element", "RTL unable to find element", 0.25),
        (r"expect\(received\)", "Jest expectation mismatch", 0.18),
        (r"Jest|jest", "Jest test failure", 0.10),
        (r"act\(\)|not wrapped in act", "React async act warning", 0.18),
        (r"Cannot read properties of undefined", "Undefined object in frontend test", 0.15),
        (r"Snapshot.*failed|snapshot failed", "Snapshot mismatch", 0.14),
    ],
    "TYPESCRIPT_COMPILE_FAILURE": [
        (r"TS\d{4}", "TypeScript compiler error", 0.35),
        (r"Type '.*' is not assignable", "Type assignability failure", 0.25),
        (r"Property '.*' does not exist", "Missing TypeScript property", 0.25),
        (r"Cannot find module .* or its corresponding type declarations", "Missing module or type declarations", 0.25),
        (r"tsc .*failed|TypeScript error", "TypeScript build failed", 0.20),
    ],
    "NPM_DEPENDENCY_FAILURE": [
        (r"npm ERR!", "npm error", 0.22),
        (r"ERESOLVE", "npm dependency resolution failure", 0.35),
        (r"peer dep|peer dependency", "peer dependency conflict", 0.25),
        (r"package-lock\.json", "package lock mismatch", 0.15),
        (r"node_modules", "node_modules install/build issue", 0.10),
        (r"Cannot find module", "Node module not found", 0.20),
    ],
    "DOTNET_BUILD_FAILURE": [
        (r"\bCS\d{4}\b", "C# compiler error", 0.35),
        (r"\bNU\d{4}\b", "NuGet restore error", 0.30),
        (r"dotnet build|MSBuild|Build FAILED", ".NET/MSBuild failure", 0.22),
        (r"project\.assets\.json", "NuGet assets file missing", 0.20),
        (r"NETSDK\d{4}", ".NET SDK error", 0.30),
        (r"System\.NullReferenceException", ".NET null reference exception", 0.18),
    ],
    "LINT_FORMAT_FAILURE": [
        (r"eslint", "ESLint failure", 0.25),
        (r"prettier", "Prettier formatting issue", 0.25),
        (r"no-unused-vars|no-explicit-any|react-hooks/exhaustive-deps", "Common lint rule failure", 0.20),
        (r"lint failed|Lint errors found", "Lint step failed", 0.20),
    ],
    "FLAKY_OR_TIMEOUT_FAILURE": [
        (r"timeout|timed out|Timeout", "Timeout signal", 0.22),
        (r"ECONNRESET|ETIMEDOUT|ECONNREFUSED|socket hang up", "Network instability signal", 0.25),
        (r"flake|flaky|intermittent", "Flaky test signal", 0.30),
        (r"Retrying|retry", "Retry behavior observed", 0.12),
        (r"503|504|502", "Transient service failure", 0.18),
    ],
    "JENKINS_INFRA_FAILURE": [
        (r"agent.*offline|node.*offline|slave.*offline", "Jenkins agent offline", 0.35),
        (r"No space left on device|disk quota exceeded", "Disk space failure", 0.35),
        (r"Permission denied|Access is denied", "Permission/access failure", 0.25),
        (r"workspace.*locked|Could not acquire lock", "Workspace lock issue", 0.25),
        (r"Cannot contact .*: java\.io", "Jenkins node communication issue", 0.25),
    ],
    "MEMORY_FAILURE": [
        (r"JavaScript heap out of memory|heap out of memory", "Node/JS heap memory failure", 0.40),
        (r"OutOfMemoryException|OutOfMemoryError", "Process out-of-memory failure", 0.35),
        (r"Allocation failed", "Memory allocation failure", 0.25),
        (r"GC overhead limit exceeded", "JVM memory pressure", 0.25),
    ],
    "SCHEMA_OR_CONTRACT_FAILURE": [
        (r"schema validation|Schema validation", "Schema validation failure", 0.30),
        (r"XSD|XML validation|invalid XML", "XML/XSD validation failure", 0.25),
        (r"contract test|API contract|breaking change", "API contract failure", 0.25),
        (r"required property|additional property|does not match schema", "JSON schema mismatch", 0.25),
    ],
}

CATEGORY_DETAILS = {
    "FRONTEND_TEST_FAILURE": {
        "label": "Frontend test failure",
        "root_cause": "React/Jest/RTL test failure likely caused by changed DOM, translation text, mock data, async timing, or missing provider/router/store setup.",
        "owner_hint": "Frontend owner or feature developer who changed the component/test wrapper.",
        "actions": [
            "Re-run the failing test locally with verbose output.",
            "Check whether UI text, selector, translation key, or mock data changed.",
            "Use findBy*/waitFor for async rendering and prefer accessible queries.",
            "Verify Redux, router, i18n, and feature-flag providers are present in the test wrapper.",
        ],
    },
    "TYPESCRIPT_COMPILE_FAILURE": {
        "label": "TypeScript compile failure",
        "root_cause": "Build failed during static type checking, likely due to interface drift, missing fields, incorrect imports, or stale generated types.",
        "owner_hint": "Developer who changed TypeScript models, props, selectors, or API contracts.",
        "actions": [
            "Open the first TS error; later errors may be cascading.",
            "Check recently changed interfaces, props, selectors, and API response types.",
            "Regenerate types if they are generated from API schemas.",
            "Avoid using any as a quick fix unless the contract is truly dynamic.",
        ],
    },
    "NPM_DEPENDENCY_FAILURE": {
        "label": "NPM dependency failure",
        "root_cause": "Dependency install/build failed, likely due to package-lock drift, peer dependency conflict, missing module, or incompatible Node/npm version.",
        "owner_hint": "Developer who changed package.json/package-lock.json or CI Node version.",
        "actions": [
            "Compare package.json and package-lock.json changes.",
            "Confirm CI Node/npm versions match local development.",
            "Run npm ci locally from a clean checkout.",
            "Avoid deleting lock files without understanding dependency impact.",
        ],
    },
    "DOTNET_BUILD_FAILURE": {
        "label": ".NET build failure",
        "root_cause": ".NET build/restore failed, likely due to C# compile errors, NuGet restore issues, SDK mismatch, or project reference changes.",
        "owner_hint": "Backend owner who changed C# code, csproj, NuGet packages, or shared contracts.",
        "actions": [
            "Fix the first C#/NuGet/MSBuild error before chasing cascaded errors.",
            "Run dotnet restore and dotnet build locally with the same SDK version as CI.",
            "Check csproj package references and project references.",
            "Validate API contracts if frontend/backend shared models changed.",
        ],
    },
    "LINT_FORMAT_FAILURE": {
        "label": "Lint or formatting failure",
        "root_cause": "Lint/format gate failed, likely due to ESLint, Prettier, hooks, or code style violations.",
        "owner_hint": "Developer who touched the failing file.",
        "actions": [
            "Run lint/format commands locally.",
            "Fix the exact reported rule instead of disabling it broadly.",
            "Check React hook dependency warnings carefully.",
            "Use targeted eslint-disable only when the rule is not applicable and add a reason.",
        ],
    },
    "FLAKY_OR_TIMEOUT_FAILURE": {
        "label": "Flaky or timeout failure",
        "root_cause": "Failure looks intermittent, timing-related, or caused by unstable network/service dependency.",
        "owner_hint": "Test owner or CI/platform owner depending on whether the failure is isolated or widespread.",
        "actions": [
            "Check whether the same test passed in a rerun or failed across multiple PRs.",
            "Look for async waits, hard-coded timers, network calls, or shared state.",
            "Replace arbitrary sleeps with deterministic waits.",
            "Quarantine only after creating a tracking ticket with failure evidence.",
        ],
    },
    "JENKINS_INFRA_FAILURE": {
        "label": "Jenkins infrastructure failure",
        "root_cause": "Build likely failed due to CI infrastructure rather than application code: offline agent, permissions, locked workspace, disk pressure, or node communication.",
        "owner_hint": "CI/platform owner; application developer may only need a rerun.",
        "actions": [
            "Check Jenkins node health and workspace availability.",
            "Rerun on a clean workspace or different agent.",
            "Clear disk/workspace issues if safe.",
            "Avoid code changes until infra failure is ruled out.",
        ],
    },
    "MEMORY_FAILURE": {
        "label": "Memory failure",
        "root_cause": "Build/test process exceeded available memory, commonly from large JS builds, test suites, bundlers, or JVM/MSBuild processes.",
        "owner_hint": "Build owner or developer who increased bundle/test memory usage.",
        "actions": [
            "Check memory usage trend and whether the failure started after a dependency/build config change.",
            "For Node builds, consider NODE_OPTIONS=--max-old-space-size only after checking bundle/test growth.",
            "Split large test suites or reduce parallelism if memory pressure is consistent.",
            "Look for memory leaks in long-running tests.",
        ],
    },
    "SCHEMA_OR_CONTRACT_FAILURE": {
        "label": "Schema or API contract failure",
        "root_cause": "Validation failed because produced data does not match expected schema/API/XML/XSD contract.",
        "owner_hint": "Backend/API owner or integration owner who changed payload shape, schema, or mappings.",
        "actions": [
            "Compare expected schema with actual payload from the failing log.",
            "Check optional vs required fields and default values.",
            "Add or update contract tests for the changed field.",
            "Confirm downstream consumers can handle the changed schema.",
        ],
    },
    "UNKNOWN": {
        "label": "Unknown failure",
        "root_cause": "The log does not contain enough known signals for confident classification.",
        "owner_hint": "Developer or CI owner should inspect the first failing stack trace/error manually.",
        "actions": [
            "Search for the first occurrence of ERROR, FAILED, Exception, or stack trace.",
            "Compare against recent PR changes.",
            "Rerun once if the failure looks environmental.",
            "Add this failure to the knowledge base after resolution.",
        ],
    },
}


def load_known_fixes() -> List[Dict[str, str]]:
    kb_path = Path(__file__).with_name("knowledge_base.json")
    if not kb_path.exists():
        return []
    return json.loads(kb_path.read_text(encoding="utf-8"))


def extract_error_signals(log_text: str) -> List[Evidence]:
    evidence: List[Evidence] = []
    lines = log_text.splitlines()

    for idx, line in enumerate(lines, start=1):
        normalized = line.strip()
        if not normalized:
            continue

        for category, patterns in PATTERNS.items():
            for regex, label, _weight in patterns:
                if re.search(regex, normalized, re.IGNORECASE):
                    evidence.append(Evidence(idx, normalized[:400], f"{category}: {label}"))
                    break

    # Include nearby generic error lines if the log has few specific matches.
    if len(evidence) < 5:
        generic = [r"\bERROR\b", r"\bFAILED\b", r"Exception", r"Traceback", r"stack trace", r"Build FAILED"]
        for idx, line in enumerate(lines, start=1):
            if any(re.search(g, line, re.IGNORECASE) for g in generic):
                ev = Evidence(idx, line.strip()[:400], "GENERIC_ERROR_SIGNAL")
                if ev not in evidence:
                    evidence.append(ev)

    # Keep report readable.
    return evidence[:18]


def classify_failure(signals: List[Evidence], log_text: str) -> FailureCategory:
    scores = {category: 0.0 for category in PATTERNS.keys()}

    for evidence in signals:
        for category in PATTERNS.keys():
            if evidence.pattern.startswith(category):
                # Find matching pattern label and use its configured weight.
                for _regex, label, weight in PATTERNS[category]:
                    if label in evidence.pattern:
                        scores[category] += weight

    # Extra scoring from full log body for cases where evidence was truncated.
    for category, patterns in PATTERNS.items():
        for regex, _label, weight in patterns:
            if re.search(regex, log_text, re.IGNORECASE):
                scores[category] += weight * 0.35

    best_category, best_score = max(scores.items(), key=lambda kv: kv[1]) if scores else ("UNKNOWN", 0.0)

    if best_score < 0.18:
        best_category = "UNKNOWN"

    details = CATEGORY_DETAILS[best_category]
    confidence = min(0.97, round(best_score, 2)) if best_category != "UNKNOWN" else 0.25

    return FailureCategory(
        key=best_category,
        label=details["label"],
        confidence=confidence,
        root_cause=details["root_cause"],
        owner_hint=details["owner_hint"],
        recommended_actions=details["actions"],
    )


def retrieve_known_fixes(category: FailureCategory, signals: List[Evidence]) -> List[Dict[str, str]]:
    kb = load_known_fixes()
    if not kb:
        return []

    signal_text = " ".join([s.text.lower() for s in signals])
    matches = []

    for item in kb:
        score = 0
        if item.get("category") == category.key:
            score += 3

        keywords = item.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in signal_text:
                score += 1

        if score > 0:
            enriched = dict(item)
            enriched["_score"] = score
            matches.append(enriched)

    matches.sort(key=lambda x: x["_score"], reverse=True)
    return [{k: v for k, v in m.items() if k != "_score"} for m in matches[:3]]


def infer_impacted_areas(signals: List[Evidence], log_text: str) -> List[str]:
    areas = set()
    text = log_text.lower()

    if any(token in text for token in ["jest", "testinglibrary", "react", "redux", "rtl"]):
        areas.add("Frontend tests / React components")
    if any(token in text for token in ["typescript", "tsc", "ts", "tsx"]):
        areas.add("TypeScript types / frontend build")
    if any(token in text for token in ["dotnet", "msbuild", "nuget", ".csproj", "cs"]):
        areas.add(".NET backend build")
    if any(token in text for token in ["schema", "xsd", "xml", "contract"]):
        areas.add("Schema / API contract validation")
    if any(token in text for token in ["jenkins", "agent", "workspace", "node offline"]):
        areas.add("Jenkins / CI infrastructure")
    if any(token in text for token in ["npm", "package-lock", "node_modules"]):
        areas.add("Node/npm dependency chain")
    if not areas:
        areas.add("Unknown; inspect first failing stack trace")

    # Try to extract paths.
    path_matches = re.findall(r"([\w./\\-]+\.(?:ts|tsx|js|jsx|cs|csproj|json|xml|xsd))", log_text)
    for path in path_matches[:6]:
        if len(path) > 3:
            areas.add(path)

    return sorted(areas)


def build_teams_summary(source_name: str, category: FailureCategory, evidence: List[Evidence]) -> str:
    first_evidence = evidence[0].text if evidence else "No strong evidence line found."
    return (
        f"CI triage for `{source_name}`: {category.label} "
        f"(confidence {category.confidence:.2f}). "
        f"Likely cause: {category.root_cause} "
        f"First evidence: {first_evidence}"
    )


def render_markdown(
    source_name: str,
    category: FailureCategory,
    evidence: List[Evidence],
    known_fixes: List[Dict[str, str]],
    impacted_areas: List[str],
    teams_summary: str,
) -> str:
    md = []
    md.append(f"# CI/CD Failure Triage Report\n")
    md.append(f"**Source:** `{source_name}`  ")
    md.append(f"**Category:** {category.label}  ")
    md.append(f"**Confidence:** {category.confidence:.2f}  ")
    md.append(f"**Owner hint:** {category.owner_hint}\n")

    md.append("## Likely Root Cause\n")
    md.append(category.root_cause + "\n")

    md.append("## Recommended Actions\n")
    for action in category.recommended_actions:
        md.append(f"- {action}")
    md.append("")

    md.append("## Impacted Areas\n")
    for area in impacted_areas:
        md.append(f"- `{area}`" if "." in area or "/" in area or "\\" in area else f"- {area}")
    md.append("")

    md.append("## Evidence Lines\n")
    if evidence:
        for ev in evidence:
            md.append(f"- Line {ev.line_number}: `{ev.text}`  ")
            md.append(f"  - Signal: {ev.pattern}")
    else:
        md.append("- No strong evidence lines found.")
    md.append("")

    md.append("## Known Fix Matches\n")
    if known_fixes:
        for fix in known_fixes:
            md.append(f"### {fix.get('title', 'Known fix')}")
            md.append(f"- Category: `{fix.get('category', '')}`")
            md.append(f"- Fix: {fix.get('fix', '')}")
            md.append(f"- Prevention: {fix.get('prevention', '')}")
            md.append("")
    else:
        md.append("- No known fix match found. Add this incident to `knowledge_base.json` after resolving it.\n")

    md.append("## Teams / Slack Summary\n")
    md.append(f"> {teams_summary}\n")

    md.append("## Guardrails\n")
    md.append("- This agent does not modify code or trigger deployments.")
    md.append("- Treat recommendations as triage assistance, not final approval.")
    md.append("- For customer or sensitive logs, remove secrets before sharing externally.")

    return "\n".join(md)


def generate_triage_report(log_text: str, source_name: str = "pasted-log") -> TriageReport:
    signals = extract_error_signals(log_text)
    category = classify_failure(signals, log_text)
    known_fixes = retrieve_known_fixes(category, signals)
    impacted_areas = infer_impacted_areas(signals, log_text)
    teams_summary = build_teams_summary(source_name, category, signals)
    markdown = render_markdown(source_name, category, signals, known_fixes, impacted_areas, teams_summary)

    return TriageReport(
        source_name=source_name,
        category=category,
        evidence=signals,
        known_fixes=known_fixes,
        impacted_areas=impacted_areas,
        teams_summary=teams_summary,
        markdown=markdown,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a Jenkins/CI build log and generate a triage report.")
    parser.add_argument("log_file", help="Path to the build log file.")
    parser.add_argument("--out", help="Optional path to write Markdown report.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    log_text = log_path.read_text(encoding="utf-8", errors="ignore")
    report = generate_triage_report(log_text, source_name=log_path.name)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(report.markdown)

    if args.out:
        Path(args.out).write_text(report.markdown, encoding="utf-8")
        print(f"\nReport written to {args.out}")


if __name__ == "__main__":
    main()
