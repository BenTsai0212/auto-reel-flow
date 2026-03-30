"""
AutoReel-Flow — Streamlit 前端介面（MVP-1 劇本驗證）
啟動：streamlit run app.py
"""

import json
import uuid
from pathlib import Path

import streamlit as st

from dramaturgy.premise import run_premise, PipelineError
from dramaturgy.architect import run_architect
from dramaturgy.wordsmith import run_wordsmith
from dramaturgy.director import run_director

OUTPUT_DIR = Path("outputs/contracts")

st.set_page_config(
    page_title="AutoReel-Flow",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 AutoReel-Flow — 劇本設計驗證")
st.caption("MVP-1：多 Agent 劇本品質驗證介面")

# ── 側邊欄：輸入 ──────────────────────────────────────────────
with st.sidebar:
    st.header("📝 輸入 Raw Content")

    use_default = st.checkbox("使用預設測試資料（睡眠主題）", value=True)

    if use_default:
        title = "你以為多睡覺就能恢復體力？科學說你錯了"
        summary = (
            "最新研究發現，睡眠時間超過 9 小時反而會增加疲勞感與認知障礙風險。"
            "許多人誤以為補眠能解決疲憊，卻不知道睡眠品質比時間更關鍵。"
            "慢波睡眠與 REM 睡眠的比例，才是決定隔天狀態的真正因素。"
        )
        keywords_str = "睡眠, 生產力, 疲勞, 科學研究, 健康"
        engagement_score = 87
    else:
        title = st.text_input("標題", placeholder="趨勢內容標題")
        summary = st.text_area("摘要", placeholder="詳細說明...", height=120)
        keywords_str = st.text_input("關鍵詞（逗號分隔）", placeholder="關鍵詞1, 關鍵詞2")
        engagement_score = st.slider("互動熱度分數", 0, 100, 75)

    if use_default:
        st.info(f"**標題：** {title}")
        st.caption(f"關鍵詞：{keywords_str}")
        st.caption(f"熱度：{engagement_score}")

    st.divider()
    run_btn = st.button("▶ 執行 Pipeline", type="primary", use_container_width=True)


# ── 狀態初始化 ────────────────────────────────────────────────
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = None
if "running" not in st.session_state:
    st.session_state.running = False


# ── Pipeline 執行 ─────────────────────────────────────────────
if run_btn:
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    raw_content = {
        "title": title,
        "summary": summary,
        "keywords": keywords,
        "engagement_score": engagement_score,
    }
    project_id = f"proj_{uuid.uuid4().hex[:8]}"

    state = {
        "project_id": project_id,
        "status": "running",
        "current_stage": "premise",
        "contracts": {},
        "errors": [],
    }

    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    stages = ["Premise", "Architect", "Wordsmith", "Director"]
    stage_icons = {"Premise": "🧠", "Architect": "🏗️", "Wordsmith": "✍️", "Director": "🎬"}

    def update_progress(stage_index: int, message: str):
        with progress_placeholder.container():
            cols = st.columns(4)
            for i, s in enumerate(stages):
                with cols[i]:
                    if i < stage_index:
                        st.success(f"{stage_icons[s]} {s} ✓")
                    elif i == stage_index:
                        st.info(f"{stage_icons[s]} {s} ⋯")
                    else:
                        st.empty()

    # Stage 1: Premise
    update_progress(0, "分析核心張力中...")
    try:
        premise = run_premise(raw_content)
        state["contracts"]["premise"] = premise
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        st.error(f"❌ Premise 失敗：{e.reason}")
        st.session_state.pipeline_state = state
        st.stop()

    # Stage 2: Architect
    update_progress(1, "規劃敘事結構中...")
    try:
        architect = run_architect(premise)
        state["contracts"]["architect"] = architect
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        st.error(f"❌ Architect 失敗：{e.reason}")
        st.session_state.pipeline_state = state
        st.stop()

    # Stage 3: Wordsmith
    update_progress(2, "撰寫文案中（逐幕處理）...")
    try:
        wordsmith = run_wordsmith(architect, premise)
        state["contracts"]["wordsmith"] = wordsmith
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        st.error(f"❌ Wordsmith 失敗：{e.reason}")
        st.session_state.pipeline_state = state
        st.stop()

    # Stage 4: Director
    update_progress(3, "規劃視聽指令中...")
    try:
        director = run_director(wordsmith, architect, premise, project_id)
        state["contracts"]["director"] = director
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        st.error(f"❌ Director 失敗：{e.reason}")
        st.session_state.pipeline_state = state
        st.stop()

    state["status"] = "completed"
    st.session_state.pipeline_state = state

    # 儲存 Contracts
    out_dir = OUTPUT_DIR / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, contract in state["contracts"].items():
        (out_dir / f"{name}_contract.json").write_text(
            json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    progress_placeholder.empty()
    st.success(f"✅ Pipeline 完成！project_id: `{project_id}`")


# ── 結果顯示 ──────────────────────────────────────────────────
state = st.session_state.pipeline_state

if state and state["status"] == "completed":
    contracts = state["contracts"]
    premise = contracts.get("premise", {})
    architect = contracts.get("architect", {})
    wordsmith = contracts.get("wordsmith", {})
    director = contracts.get("director", {})

    tab1, tab2, tab3, tab4 = st.tabs(["🧠 Premise", "🏗️ Architect", "✍️ Wordsmith", "🎬 Director"])

    # ── Tab 1: Premise ────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("核心張力")
            ct = premise.get("core_tension", {})
            st.markdown(f"**衝突類型：** `{ct.get('conflict_type', '')}`")
            col_a, col_b = st.columns(2)
            with col_a:
                st.info(f"**Force A（原有認知）**\n\n{ct.get('force_a', '')}")
            with col_b:
                st.warning(f"**Force B（現實打臉）**\n\n{ct.get('force_b', '')}")

            st.subheader("受眾分析")
            audience = premise.get("audience", {})
            st.markdown(f"**痛點：** {audience.get('pain_point', '')}")
            st.markdown(f"**原有假設：** {audience.get('assumed_belief', '')}")
            st.markdown(f"**期望轉變：** {audience.get('desired_shift', '')}")

        with col2:
            st.subheader("故事設定")
            constraints = premise.get("story_constraints", {})
            st.metric("推薦弧線", constraints.get("recommended_arc", "").upper())
            st.markdown(f"**語氣基調：** {constraints.get('tone', '')}")
            st.markdown("**敘事禁忌：**")
            for f in constraints.get("forbidden", []):
                st.markdown(f"- {f}")

            payoff = premise.get("payoff", {})
            st.subheader("報酬設計")
            st.markdown(f"**承諾：** {payoff.get('promise', '')}")
            st.markdown(f"**情緒回報：** {payoff.get('emotional_reward', '')}")
            st.markdown(f"**收穫類型：** `{payoff.get('takeaway_type', '')}`")

        with st.expander("原始 JSON"):
            st.json(premise)

    # ── Tab 2: Architect ──────────────────────────────────────
    with tab2:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("情緒曲線")
            scenes = architect.get("scenes", [])
            if scenes:
                import altair as alt
                import pandas as pd
                df = pd.DataFrame([
                    {"幕次": f"Scene {s['segment_id']}\n{s['role']}", "強度": s["intensity"]}
                    for s in scenes
                ])
                chart = (
                    alt.Chart(df)
                    .mark_bar()
                    .encode(
                        x=alt.X("幕次", sort=None),
                        y=alt.Y("強度", scale=alt.Scale(domain=[0, 1])),
                        color=alt.condition(
                            alt.datum["強度"] >= 0.85,
                            alt.value("#FF4B4B"),
                            alt.value("#4B8BFF"),
                        ),
                    )
                    .properties(height=250)
                )
                st.altair_chart(chart, use_container_width=True)

            st.subheader("場景骨架")
            for s in scenes:
                with st.expander(f"Scene {s['segment_id']} — {s['role']} (intensity={s['intensity']})"):
                    st.markdown(f"**戲劇功能：** {s['dramatic_function']}")
                    st.markdown(f"**情緒目標：** `{s['emotional_target']}`")
                    st.markdown(f"**時長預算：** {s['duration_budget']}")
                    st.markdown(f"**轉場方式：** `{s.get('transition_to_next', 'null')}`")

        with col2:
            st.subheader("全局設定")
            st.metric("故事弧線", architect.get("story_arc", "").upper())
            st.metric("目標時長", architect.get("total_duration_target", ""))
            hook = architect.get("hook_strategy", {})
            st.markdown(f"**Hook 策略：** `{hook.get('type', '')}`")
            st.markdown(f"**開場策略：** {hook.get('opening_move', '')}")
            st.markdown(f"**節奏備注：** {architect.get('pacing_notes', '')}")

        with st.expander("原始 JSON"):
            st.json(architect)

    # ── Tab 3: Wordsmith ──────────────────────────────────────
    with tab3:
        ws_scenes = wordsmith.get("scenes", [])

        st.subheader("Naturalness Score 總覽")
        score_cols = st.columns(len(ws_scenes))
        for i, scene in enumerate(ws_scenes):
            score = scene.get("naturalness_score", 0)
            with score_cols[i]:
                color = "normal" if score and score >= 70 else "inverse"
                st.metric(
                    label=f"Scene {scene['segment_id']} {scene['role']}",
                    value=score if score else "N/A",
                    delta="通過" if score and score >= 70 else "未達標",
                    delta_color=color,
                )

        st.divider()
        st.subheader("文案內容")

        for scene in ws_scenes:
            score = scene.get("naturalness_score", 0)
            score_badge = f"✅ {score}" if score and score >= 70 else f"⚠️ {score}"
            with st.expander(
                f"Scene {scene['segment_id']} — {scene['role']} | naturalness={score_badge} | {scene['duration_est']}"
            ):
                st.markdown("**原始文案（raw）**")
                st.markdown(
                    f"<div style='font-size:1.1em; line-height:1.8; padding:12px; "
                    f"background:#f0f2f6; border-radius:8px;'>"
                    f"{scene['voice_script']['raw']}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("**TTS 標記版本（annotated）**")
                st.code(scene["voice_script"]["annotated"], language=None)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**語言標記**")
                    lm = scene.get("language_markers", {})
                    st.markdown(f"- 停頓數量：{lm.get('pause_count', 0)}")
                    st.markdown(f"- 平均句長：{lm.get('avg_sentence_length', 0)} 字")
                    st.markdown(f"- 修辭手法：`{lm.get('rhetorical_device', '')}`")
                    st.markdown(f"- 口語鉤子：{', '.join(lm.get('oral_hooks', []))}")
                with col2:
                    st.markdown("**TTS 參數**")
                    tts = scene.get("tts_params", {})
                    st.markdown(f"- 風格：`{tts.get('style', '')}`")
                    st.markdown(f"- 穩定度：{tts.get('stability', 0):.2f}")
                    st.markdown(f"- 語速：{tts.get('speaking_rate', 1.0):.2f}x")
                    st.markdown(f"- 相似度增強：{tts.get('similarity_boost', 0):.2f}")

        with st.expander("原始 JSON"):
            st.json(wordsmith)

    # ── Tab 4: Director ───────────────────────────────────────
    with tab4:
        dir_scenes = director.get("scenes", [])

        col1, col2 = st.columns([1, 1])
        with col1:
            st.metric("總時長", director.get("total_duration_est", ""))
        with col2:
            av = director.get("global_av_profile", {})
            st.metric("畫面比例", av.get("aspect_ratio", "9:16"))

        st.subheader("AV 弧線")
        av = director.get("global_av_profile", {})
        arc_cols = st.columns(len(dir_scenes))
        for i, scene in enumerate(dir_scenes):
            with arc_cols[i]:
                st.markdown(f"**Scene {scene['segment_id']}**")
                st.caption(f"色調: {scene['visual']['color_grade']}")
                st.caption(f"BGM: {scene['audio']['bgm']['mood']}")

        st.divider()
        st.subheader("場景視聽指令")

        for scene in dir_scenes:
            with st.expander(
                f"Scene {scene['segment_id']} — {scene['role']} | {scene['visual']['shot_type']} | {scene['duration_est']}"
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("**視覺**")
                    visual = scene.get("visual", {})
                    st.markdown(f"🔍 Pexels Prompt：`{visual.get('prompt', '')}`")
                    st.markdown(f"- 鏡頭類型：`{visual.get('shot_type', '')}`")
                    st.markdown(f"- 色調：`{visual.get('color_grade', '')}`")
                    st.markdown(f"- 運動：`{visual.get('motion', '')}`")
                with col2:
                    st.markdown("**音頻**")
                    audio = scene.get("audio", {})
                    bgm = audio.get("bgm", {})
                    st.markdown(f"- BGM 氛圍：{bgm.get('mood', '')}")
                    st.markdown(f"- 音量壓低：{bgm.get('volume_duck', 0):.0%}")
                    st.markdown(f"- 漸入時間：{bgm.get('fade_in', '')}")
                    st.markdown(f"- 音效：{audio.get('sfx', 'none')}")
                with col3:
                    st.markdown("**同步**")
                    sync = scene.get("sync", {})
                    st.markdown(f"- 剪輯觸發：`{sync.get('cut_trigger', '')}`")
                    st.markdown(f"- 剪輯時間點：{sync.get('cut_at_second', 0):.1f}s")
                    st.markdown(f"- 字幕風格：`{sync.get('subtitle_style', '')}`")

        with st.expander("原始 JSON"):
            st.json(director)

elif state and state["status"] == "failed":
    st.error("Pipeline 執行失敗")
    for err in state.get("errors", []):
        st.markdown(f"**Stage:** `{err['stage']}`")
        st.markdown(f"**原因：** {err['reason']}")
else:
    st.info("👈 在左側填入內容後，按「執行 Pipeline」開始驗證。")
    with st.expander("關於 AutoReel-Flow MVP-1"):
        st.markdown("""
        **MVP-1 劇本設計層** 驗證目標：

        1. **Premise Agent** — 從趨勢內容提煉核心張力
        2. **Architect Agent** — 設計具情緒曲線的四幕骨架
        3. **Wordsmith Agent** — 將骨架轉化為真人語感文案（逐幕 + naturalness 評審）
        4. **Director Agent** — 輸出完整視聽執行指令

        每個 Agent 產出後均通過 **Contract Validator** 強制驗證。
        Wordsmith 每幕有獨立的自然度評審（naturalness_score ≥ 70 才通過）。
        """)
