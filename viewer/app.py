import json
from pathlib import Path

import pandas as pd
import streamlit as st

from papertriage.core.config import settings as _settings

st.set_page_config(page_title="PaperTriage Viewer", layout="wide")
st.title("PaperTriage Viewer")

outputs_dir = _settings.output_dir

# Sidebar: run selection
run_dirs = []
if outputs_dir.exists():
    run_dirs = sorted(
        [d for d in outputs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

run_dir: Path | None = None
if run_dirs:
    selected = st.sidebar.selectbox("Run", [d.name for d in run_dirs])
    run_dir = outputs_dir / selected
    st.sidebar.caption(f"Output: `{run_dir}`")
else:
    st.sidebar.info("No runs found.")
    st.info(
        'No run selected. Start one with: `papertriage run --papers <dir> --question "..."`'
    )

tab_report, tab_critique, tab_papers, tab_cost = st.tabs(["Report", "Critique", "Papers", "Cost"])

_NO_RUN_MSG = "Select a run from the sidebar to view this tab."

# --- Report ---
with tab_report:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        report_path = run_dir / "report.md"
        if report_path.exists():
            st.markdown(report_path.read_text(encoding="utf-8"))
        else:
            st.info("No report available for this run.")

# --- Critique ---
with tab_critique:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        critique_json_path = run_dir / "critique.json"
        critique_md_path = run_dir / "critique.md"

        if critique_json_path.exists():
            data = json.loads(critique_json_path.read_text(encoding="utf-8"))
            st.markdown(f"**Overall Assessment:** {data['overall_assessment']}")
            st.divider()
            _SEVERITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for finding in data.get("findings", []):
                sev = finding["severity"]
                emoji = _SEVERITY_EMOJI.get(sev, "⚪")
                preview = finding["claim"][:80]
                with st.expander(f"{emoji} **{sev.title()}** — {preview}"):
                    st.write(f"**Claim:** {finding['claim']}")
                    st.write(f"**Reason:** {finding['reason']}")
                    st.write(f"**Suggested fix:** {finding['suggested_fix']}")
        elif critique_md_path.exists():
            st.markdown(critique_md_path.read_text(encoding="utf-8"))
        else:
            st.info("No critique available for this run.")

# --- Papers ---
with tab_papers:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        papers_path = run_dir / "papers.json"
        if not papers_path.exists():
            st.info("No papers data for this run.")
        else:
            papers = json.loads(papers_path.read_text(encoding="utf-8"))
            rows = [
                {
                    "id": p["id"][:8],
                    "title": p.get("title", ""),
                    "year": p.get("year"),
                    "method": p.get("method", ""),
                    "num_contributions": len(p.get("contributions", [])),
                }
                for p in papers
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.divider()
            st.json(papers)

# --- Cost ---
with tab_cost:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        cost_path = run_dir / "cost.json"
        if not cost_path.exists():
            st.info("No cost data for this run.")
        else:
            cost_data = json.loads(cost_path.read_text(encoding="utf-8"))
            st.metric("Total Cost", f"${cost_data['total_usd']:.6f}")
            per_stage = cost_data.get("per_stage", {})
            if per_stage:
                df = pd.DataFrame.from_dict(per_stage, orient="index", columns=["cost_usd"])
                st.bar_chart(df)
