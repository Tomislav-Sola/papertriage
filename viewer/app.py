import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from papertriage.core.config import settings as _settings
from state import load_review, save_review

st.set_page_config(page_title="PaperTriage Viewer", layout="wide")
st.title("PaperTriage Viewer")

outputs_dir = _settings.output_dir

# Sidebar: run selection (skip regenerated_* subdirs — they live inside a run dir)
run_dirs = []
if outputs_dir.exists():
    run_dirs = sorted(
        [
            d
            for d in outputs_dir.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and not d.name.startswith("regenerated_")
        ],
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

tab_report, tab_clusters, tab_critique, tab_papers, tab_graph, tab_cost = st.tabs(
    ["Report", "Clusters", "Critique", "Papers", "Graph", "Cost"]
)

_NO_RUN_MSG = "Select a run from the sidebar to view this tab."

# ---------------------------------------------------------------------------
# Session-state review: load from disk once per run selection
# ---------------------------------------------------------------------------

if run_dir is not None:
    if (
        "review_run_id" not in st.session_state
        or st.session_state.review_run_id != selected
    ):
        st.session_state.review = load_review(run_dir)
        st.session_state.review_run_id = selected


def _get_review():
    return st.session_state.get("review", {"paper_overrides": {}, "cluster_overrides": {}})


def _flush_review():
    if run_dir is not None:
        save_review(run_dir, _get_review())


# --- Report ---
with tab_report:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        regen_dirs = sorted(
            [d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith("regenerated_")],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if regen_dirs:
            options = ["Original"] + [d.name for d in regen_dirs]
            chosen_report = st.selectbox("Report version", options, key="report_selector")
            report_dir = run_dir if chosen_report == "Original" else run_dir / chosen_report
        else:
            report_dir = run_dir

        report_path = report_dir / "report.md"
        if report_path.exists():
            st.markdown(report_path.read_text(encoding="utf-8"))
        else:
            st.info("No report available for this run.")

# --- Clusters ---
with tab_clusters:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        clusters_path = run_dir / "clusters.json"
        if not clusters_path.exists():
            st.info("No clusters data for this run.")
        else:
            clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
            papers_path_c = run_dir / "papers.json"
            id_to_title: dict[str, str] = {}
            if papers_path_c.exists():
                for p in json.loads(papers_path_c.read_text(encoding="utf-8")):
                    id_to_title[p["id"]] = p.get("title") or p["id"][:8]

            review = _get_review()
            cluster_overrides = review.setdefault("cluster_overrides", {})

            st.caption("Edit cluster labels below — changes are saved automatically.")
            for cluster in clusters:
                cid = str(cluster["id"])
                default_label = cluster.get("label", f"Cluster {cid}")
                current_label = cluster_overrides.get(cid, {}).get("label", default_label)

                col_label, col_info = st.columns([3, 1])
                with col_label:
                    new_label = st.text_input(
                        f"Label for cluster {cid}",
                        value=current_label,
                        key=f"cluster_label_{cid}",
                        label_visibility="collapsed",
                    )
                with col_info:
                    st.caption(f"{len(cluster.get('paper_ids', []))} papers")

                if new_label != current_label:
                    cluster_overrides[cid] = {"label": new_label}
                    _flush_review()

                keywords = cluster.get("keywords", [])
                paper_ids = cluster.get("paper_ids", [])
                with st.expander(
                    f"**{new_label}** — {len(paper_ids)} paper(s)", expanded=True
                ):
                    if keywords:
                        st.caption("Keywords: " + " · ".join(keywords))
                    for pid in paper_ids:
                        title = id_to_title.get(pid)
                        if title:
                            st.markdown(f"- {title}")
                        else:
                            st.markdown(f"- `{pid[:8]}` *(no title extracted)*")

# --- Critique ---
_SEVERITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
_CRITIC_BADGE = {
    "factuality": ":orange[factuality]",
    "coverage": ":blue[coverage]",
    "novelty": ":violet[novelty]",
}


def _render_critique(critique_dir: Path) -> None:
    critique_json_path = critique_dir / "critique.json"
    critique_md_path = critique_dir / "critique.md"

    if critique_json_path.exists():
        data = json.loads(critique_json_path.read_text(encoding="utf-8"))
        st.markdown(f"**Overall Assessment:** {data['overall_assessment']}")
        st.divider()
        for finding in data.get("findings", []):
            sev = finding["severity"]
            emoji = _SEVERITY_EMOJI.get(sev, "⚪")
            claim = finding["claim"]
            parts = claim.split(". ", 1)
            first_sentence = parts[0]
            has_more = len(parts) > 1
            if len(first_sentence) > 100:
                preview = first_sentence[:97] + "..."
            elif has_more:
                preview = first_sentence + "..."
            else:
                preview = first_sentence
            source = finding.get("source_critic")
            badge = f" · {_CRITIC_BADGE.get(source, source)}" if source else ""
            with st.expander(f"{emoji} **{sev.title()}**{badge} — {preview}"):
                st.write(f"**Claim:** {finding['claim']}")
                st.write(f"**Reason:** {finding['reason']}")
                st.write(f"**Suggested fix:** {finding['suggested_fix']}")
    elif critique_md_path.exists():
        st.markdown(critique_md_path.read_text(encoding="utf-8"))
    else:
        st.info("No critique available for this run.")


with tab_critique:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        regen_dirs = sorted(
            [d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith("regenerated_")],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if regen_dirs:
            options = ["Original"] + [d.name for d in regen_dirs]
            chosen = st.selectbox("Critique version", options, key="critique_selector")
            critique_dir = run_dir if chosen == "Original" else run_dir / chosen
        else:
            critique_dir = run_dir

        _render_critique(critique_dir)

# --- Papers (with Include/Exclude review) ---
with tab_papers:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        papers_path = run_dir / "papers.json"
        if not papers_path.exists():
            st.info("No papers data for this run.")
        else:
            papers = json.loads(papers_path.read_text(encoding="utf-8"))
            review = _get_review()
            paper_overrides = review.setdefault("paper_overrides", {})

            # Summary dataframe (quick overview, always visible)
            rows = [
                {
                    "title": p.get("title") or f"(no title) {p['id'][:8]}",
                    "authors": ", ".join(p.get("authors", [])),
                    "year": p.get("year"),
                    "method": p.get("method", ""),
                    "contributions": len(p.get("contributions", [])),
                    "included": paper_overrides.get(p["id"], {}).get("included", True),
                }
                for p in papers
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.divider()

            st.caption(
                "Toggle papers to include or exclude them from the next regeneration. "
                "Notes are saved with the review."
            )
            st.warning(
                "review.json is last-write-wins — do not edit this run in multiple "
                "browser tabs at the same time.",
                icon="⚠️",
            )

            n_total = len(papers)
            n_excluded = sum(
                1 for p in papers
                if not paper_overrides.get(p["id"], {}).get("included", True)
            )
            st.markdown(
                f"**{n_total} papers** · {n_total - n_excluded} included · {n_excluded} excluded"
            )

            st.divider()

            for paper in papers:
                pid = paper["id"]
                title = paper.get("title") or f"*(no title)* `{pid[:8]}`"
                override = paper_overrides.get(pid, {})
                included = override.get("included", True)
                notes = override.get("notes", "")

                is_failed = paper.get("title") == "<extraction failed>"
                col_toggle, col_title = st.columns([1, 8])
                with col_toggle:
                    new_included = st.toggle(
                        "Include",
                        value=included,
                        key=f"include_{pid}",
                        disabled=is_failed,
                        label_visibility="collapsed",
                    )
                with col_title:
                    strike = "~~" if not new_included or is_failed else ""
                    badge = " `failed`" if is_failed else ""
                    st.markdown(f"{strike}{title}{strike}{badge}")

                with st.expander("Details / Notes", expanded=False):
                    authors = paper.get("authors", [])
                    st.caption(
                        f"ID: `{pid[:8]}` · Year: {paper.get('year', '?')}"
                        + (f" · {', '.join(authors)}" if authors else "")
                    )
                    problem = paper.get("problem", "")
                    if problem:
                        st.markdown(f"**Problem:** {problem}")
                    st.markdown(f"**Method:** {paper.get('method', '') or '—'}")
                    for field, label in [
                        ("contributions", "Contributions"),
                        ("key_results", "Key results"),
                        ("datasets", "Datasets"),
                        ("limitations", "Limitations"),
                    ]:
                        items = paper.get(field, [])
                        if items:
                            st.markdown(
                                f"**{label}:**\n"
                                + "\n".join(f"- {item}" for item in items)
                            )
                    new_notes = st.text_area(
                        "Notes",
                        value=notes,
                        key=f"notes_{pid}",
                        height=60,
                        label_visibility="collapsed",
                        placeholder="Optional reviewer notes…",
                    )

                # Persist changes
                changed = (new_included != included) or (new_notes != notes)
                if changed:
                    paper_overrides[pid] = {"included": new_included, "notes": new_notes}
                    _flush_review()

            st.divider()
            with st.expander("Raw JSON", expanded=False):
                st.json(papers)

            st.divider()

            # Regenerate button
            meta_path = run_dir / "meta.json"
            orig_critic = "multi"
            if meta_path.exists():
                orig_critic = json.loads(meta_path.read_text(encoding="utf-8")).get(
                    "critic_mode", "multi"
                )

            if st.button("Regenerate report, critique and cost with current selections", type="primary"):
                from papertriage.llm.client import ClaudeClient
                from papertriage.orchestration.regenerate import regenerate

                claude = ClaudeClient(_settings)
                with st.spinner(
                    f"Regenerating synthesis and critique ({orig_critic} critic)…"
                ):
                    try:
                        ctx = regenerate(
                            run_id=selected,
                            claude=claude,
                            settings=_settings,
                            critic_mode=orig_critic,
                        )
                        st.success(
                            f"Done! Results written to `{ctx.output_dir.name}`. "
                            "Select it from the dropdown in the Report, Critique and Cost tabs."
                        )
                    except Exception as exc:
                        st.error(f"Regeneration failed: {exc}")

# --- Graph ---
with tab_graph:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        graph_html = run_dir / "knowledge_graph.html"
        if not graph_html.exists():
            st.info(
                "No knowledge graph for this run. "
                "Re-run with `--clusterer embedding` (graph is built automatically) "
                "or add `--enable-graph` to any run."
            )
        else:
            html_content = graph_html.read_text(encoding="utf-8")
            components.html(html_content, height=620, scrolling=False)

# --- Cost ---
with tab_cost:
    if run_dir is None:
        st.info(_NO_RUN_MSG)
    else:
        regen_dirs = sorted(
            [d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith("regenerated_")],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if regen_dirs:
            options = ["Original"] + [d.name for d in regen_dirs]
            chosen_cost = st.selectbox("Cost version", options, key="cost_selector")
            cost_dir = run_dir if chosen_cost == "Original" else run_dir / chosen_cost
        else:
            cost_dir = run_dir

        cost_path = cost_dir / "cost.json"
        if not cost_path.exists():
            st.info("No cost data for this run.")
        else:
            cost_data = json.loads(cost_path.read_text(encoding="utf-8"))
            st.metric("Total Cost", f"${cost_data['total_usd']:.6f}")
            per_stage = cost_data.get("per_stage", {})
            if per_stage:
                df = pd.DataFrame.from_dict(per_stage, orient="index", columns=["cost_usd"])
                st.bar_chart(df)
