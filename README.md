# CI/CD Failure Triage Agent

A lightweight, open-source, free-to-run CI/CD triage agent for Jenkins/GitHub/Azure DevOps style build logs.

This starter agent is intentionally **safe and interview-defensible**:
- No paid API required
- No API keys
- No backend needed for the CLI
- Works locally on Jenkins logs, Jest/RTL failures, TypeScript errors, .NET build errors, npm issues, flaky test signals, and infrastructure failures
- Generates a developer-ready Markdown report and a Teams/Slack-ready summary

## Why this is useful

Large engineering teams spend time repeatedly reading long CI logs. This agent turns raw logs into:

- Failure category
- Confidence score
- Evidence lines
- Likely root cause
- Suggested fix steps
- Owner hint
- Similar known fixes from a local knowledge base
- PR/Teams summary

## Architecture

```text
Jenkins / CI log
      |
      v
Log ingestion tool
      |
      v
Signal extraction tool
      |
      v
Failure classifier
      |
      v
Known-fix retriever
      |
      v
Report generator
      |
      v
Developer summary + Markdown report
```

## Agent tools

The MVP is built as a tool-based pipeline:

1. `extract_error_signals(log_text)`
2. `classify_failure(signals)`
3. `retrieve_known_fixes(category, signals)`
4. `generate_triage_report(log_text, source_name)`

This structure lets you later replace the rule-based classifier with LangGraph, LangChain, Semantic Kernel, OpenAI, Claude, Gemini, Ollama, or a local Llama model.

## Run locally

### Option 1: CLI, no dependencies

```bash
python triage_agent.py sample_logs/jest_failure.log
```

Save report:

```bash
python triage_agent.py sample_logs/dotnet_failure.log --out reports/dotnet_report.md
```

JSON output:

```bash
python triage_agent.py sample_logs/npm_failure.log --json
```

### Option 2: Streamlit UI

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then upload or paste a Jenkins log.

## Example output

```text
Category: FRONTEND_TEST_FAILURE
Confidence: 0.88
Root cause: React/Jest/RTL test failure likely caused by changed DOM, text, mock data, async timing, or missing provider/router/store setup.

Recommended actions:
1. Re-run the failing test locally with verbose output.
2. Check whether the component text, selector, translation key, or async rendering changed.
3. Use findBy*/waitFor for async UI and prefer accessible queries.
4. Verify Redux/router/i18n providers are present in the test wrapper.
```

## How to turn this into a stronger AI Engineering project

### Phase 1: Current MVP
- Rule-based triage
- Known-fix retrieval
- Markdown report generation

### Phase 2: RAG
- Store historical build failures and fixes in a vector DB
- Retrieve similar failures
- Include citations to past fixes

### Phase 3: Agentic workflow
- Connect to Jenkins API
- Pull latest failed build logs
- Search GitHub PR diff
- Search related files/tests
- Draft a PR comment or Teams message
- Keep human approval before posting

### Phase 4: Production-grade
- Add authentication
- Add role-based access
- Add audit logs
- Add hallucination guardrails
- Add confidence thresholds
- Add feedback buttons

## Resume bullet

> Built a CI/CD Failure Triage Agent that parses Jenkins logs, classifies Jest/RTL, TypeScript, .NET, npm, flaky test, and infrastructure failures, retrieves known fixes from a local knowledge base, and generates developer-ready remediation reports and Teams-ready summaries.
