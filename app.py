import streamlit as st
from triage_agent import generate_triage_report

st.set_page_config(
    page_title="CI/CD Failure Triage Agent",
    page_icon="🛠️",
    layout="wide",
)

st.title("🛠️ CI/CD Failure Triage Agent")
st.caption("Free local MVP: paste or upload Jenkins/CI logs and get a developer-ready triage report.")

with st.sidebar:
    st.header("What it detects")
    st.write("- Jest / React Testing Library failures")
    st.write("- TypeScript compile failures")
    st.write("- npm dependency failures")
    st.write("- .NET / MSBuild / NuGet failures")
    st.write("- Lint / formatting failures")
    st.write("- Flaky tests / timeouts")
    st.write("- Jenkins infrastructure failures")
    st.write("- Schema / API contract failures")

uploaded_file = st.file_uploader("Upload a Jenkins/CI log", type=["log", "txt"])
pasted_log = st.text_area("Or paste a build log", height=260, placeholder="Paste Jenkins console output here...")

source_name = "pasted-log"
log_text = ""

if uploaded_file:
    source_name = uploaded_file.name
    log_text = uploaded_file.read().decode("utf-8", errors="ignore")
elif pasted_log.strip():
    log_text = pasted_log

if st.button("Analyze failure", type="primary", disabled=not bool(log_text.strip())):
    report = generate_triage_report(log_text, source_name=source_name)

    c1, c2, c3 = st.columns(3)
    c1.metric("Category", report.category.label)
    c2.metric("Confidence", f"{report.category.confidence:.2f}")
    c3.metric("Evidence lines", len(report.evidence))

    st.subheader("Likely root cause")
    st.write(report.category.root_cause)

    st.subheader("Recommended actions")
    for action in report.category.recommended_actions:
        st.write(f"- {action}")

    st.subheader("Teams / Slack summary")
    st.code(report.teams_summary, language="text")

    st.subheader("Impacted areas")
    for area in report.impacted_areas:
        st.write(f"- {area}")

    st.subheader("Evidence")
    for ev in report.evidence:
        st.write(f"**Line {ev.line_number}:** `{ev.text}`")
        st.caption(ev.pattern)

    st.subheader("Known fix matches")
    if report.known_fixes:
        for fix in report.known_fixes:
            with st.expander(fix.get("title", "Known fix")):
                st.write(f"**Fix:** {fix.get('fix', '')}")
                st.write(f"**Prevention:** {fix.get('prevention', '')}")
    else:
        st.info("No known fix match found. Add this incident to knowledge_base.json after resolving it.")

    st.download_button(
        "Download Markdown report",
        data=report.markdown,
        file_name="ci_triage_report.md",
        mime="text/markdown",
    )
