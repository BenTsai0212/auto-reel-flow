"""
AutoReel-Flow — Streamlit 前端介面
MVP-1：劇本設計驗證（含 Framework DNA 策略分析 + 確認閘道）
MVP-2：劇本設計 + 音軌生成驗證
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
from dramaturgy.strategy import run_theme_analyzer, run_strategy_synthesizer

OUTPUT_DIR = Path("outputs/contracts")

st.set_page_config(
    page_title="AutoReel-Flow",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 AutoReel-Flow — 驗證介面")

# ── 側邊欄：輸入 ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 設定")

    mvp_phase = st.radio(
        "MVP 階段",
        options=["MVP-1：劇本設計", "MVP-2：劇本 + 音軌"],
        index=0,
    )
    is_mvp2 = mvp_phase.startswith("MVP-2")

    st.divider()
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
    analyze_btn = st.button("🔍 分析主題（Strategy Layer）", type="secondary", use_container_width=True)
    run_btn = st.button("▶ 執行劇本 Pipeline", type="primary", use_container_width=True,
                        disabled=(st.session_state.get("framework_dna") is None
                                  and not analyze_btn))


# ── 狀態初始化 ────────────────────────────────────────────────
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = None
if "audio_result" not in st.session_state:
    st.session_state.audio_result = None
if "framework_dna" not in st.session_state:
    st.session_state.framework_dna = None
if "theme_dimension" not in st.session_state:
    st.session_state.theme_dimension = None


# ── Strategy Layer 分析 ───────────────────────────────────────
if analyze_btn:
    st.session_state.framework_dna = None
    st.session_state.theme_dimension = None
    st.session_state.pipeline_state = None
    st.session_state.audio_result = None

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    raw_content = {
        "title": title,
        "summary": summary,
        "keywords": keywords,
        "engagement_score": engagement_score,
    }

    with st.spinner("🔬 分析主題維度..."):
        try:
            theme_dim = run_theme_analyzer(raw_content)
            st.session_state.theme_dimension = theme_dim
        except PipelineError as e:
            st.error(f"❌ 主題分析失敗：{e.reason}")
            st.stop()

    with st.spinner("🧠 合成框架策略..."):
        try:
            framework_dna = run_strategy_synthesizer(theme_dim)
            st.session_state.framework_dna = framework_dna
        except PipelineError as e:
            st.error(f"❌ 策略合成失敗：{e.reason}")
            st.stop()

    st.rerun()


# ── 確認閘道：顯示導演簡報 ──────────────────────────────────────
framework_dna = st.session_state.framework_dna
theme_dim = st.session_state.theme_dimension

if framework_dna and not st.session_state.pipeline_state:
    st.divider()

    # 主題維度概覽
    if theme_dim:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("媒介類型", theme_dim.get("medium", "").replace("_", " ").title())
        with col2:
            st.metric("情緒基調", theme_dim.get("tone", "").replace("_", " ").title())
        with col3:
            st.metric("衝突軸", theme_dim.get("conflict_axis", "").replace("_", " ").title())

        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric("神話共鳴度", f"{theme_dim.get('myth_resonance', 0):.0%}")
        with col5:
            st.metric("知識傳遞比重", f"{theme_dim.get('knowledge_transfer', 0):.0%}")
        with col6:
            st.metric("節奏密度需求", f"{theme_dim.get('pace_requirement', 0):.0%}")

    st.divider()

    # Framework DNA 與導演簡報
    col_dna, col_brief = st.columns([1, 2])

    with col_dna:
        st.subheader("📐 Framework DNA")
        st.metric("主框架", framework_dna.get("primary_framework", "").replace("_", " ").title())
        st.metric("場景數量", f"{framework_dna.get('scene_count', 4)} 幕")
        st.caption(f"**故事形狀：** {framework_dna.get('story_shape', '')}")
        st.caption(f"**情感弧線：** {framework_dna.get('emotional_arc', '')}")

        # 框架權重
        weights = framework_dna.get("weights", {})
        if weights:
            st.markdown("**框架混合比例：**")
            for fw, w in sorted(weights.items(), key=lambda x: -x[1]):
                if w > 0:
                    pct = int(w * 100)
                    label = fw.replace("_", " ").title()
                    st.progress(w, text=f"{label}: {pct}%")

        # 節拍結構
        beats = framework_dna.get("beat_structure", [])
        if beats:
            with st.expander("節拍結構"):
                for b in beats:
                    st.markdown(f"**{b['beat_index']}.** {b['function']} `@{b['pct_of_story']}%`")

    with col_brief:
        st.subheader("🎬 導演簡報（Director's Brief）")
        brief = framework_dna.get("director_brief", "")
        st.info(brief)

        st.markdown("---")
        st.markdown("**確認後將以此框架策略執行劇本設計。**")
        col_confirm, col_reset = st.columns(2)
        with col_confirm:
            if st.button("✅ 確認策略，開始生成劇本", type="primary", use_container_width=True):
                # 觸發劇本 pipeline（標記已確認）
                st.session_state._run_pipeline = True
                st.rerun()
        with col_reset:
            if st.button("🔄 重新分析主題", use_container_width=True):
                st.session_state.framework_dna = None
                st.session_state.theme_dimension = None
                st.rerun()


# ── 劇本 Pipeline 執行 ────────────────────────────────────────
if st.session_state.get("_run_pipeline") and framework_dna:
    st.session_state._run_pipeline = False
    st.session_state.audio_result = None

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
        "contracts": {
            "framework_dna": framework_dna,
        },
        "errors": [],
    }

    progress_placeholder = st.empty()

    stages = ["Premise", "Architect", "Wordsmith", "Director"]
    stage_icons = {"Premise": "🧠", "Architect": "🏗️", "Wordsmith": "✍️", "Director": "🎬"}

    def update_progress(stage_index: int):
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

    update_progress(0)
    try:
        premise = run_premise(raw_content)
        state["contracts"]["premise"] = premise
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        st.error(f"❌ Premise 失敗：{e.reason}")
        st.session_state.pipeline_state = state
        st.stop()

    update_progress(1)
    try:
        architect = run_architect(premise, framework_dna)
        state["contracts"]["architect"] = architect
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        st.error(f"❌ Architect 失敗：{e.reason}")
        st.session_state.pipeline_state = state
        st.stop()

    update_progress(2)
    try:
        wordsmith = run_wordsmith(architect, premise, framework_dna)
        state["contracts"]["wordsmith"] = wordsmith
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        st.error(f"❌ Wordsmith 失敗：{e.reason}")
        st.session_state.pipeline_state = state
        st.stop()

    update_progress(3)
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
    st.success(f"✅ 劇本設計完成！project_id: `{project_id}`")


# ── 音軌生成（MVP-2）────────────────────────────────────────────
state = st.session_state.pipeline_state

if is_mvp2 and state and state["status"] == "completed" and not st.session_state.audio_result:
    st.divider()
    audio_btn = st.button("🎵 生成音軌（ElevenLabs + Whisper）", type="secondary", use_container_width=True)

    if audio_btn:
        from execution.audio_pipeline import run_audio_pipeline

        project_id = state["project_id"]
        director_contract = state["contracts"]["director"]

        with st.spinner("呼叫 ElevenLabs TTS 中...（每幕逐一處理）"):
            try:
                audio_result = run_audio_pipeline(director_contract, project_id)
                st.session_state.audio_result = audio_result
                st.success("✅ 音軌生成完成！")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 音軌生成失敗：{e}")


# ── 結果顯示 ──────────────────────────────────────────────────
state = st.session_state.pipeline_state
audio_result = st.session_state.audio_result

if state and state["status"] == "completed":
    contracts = state["contracts"]
    premise = contracts.get("premise", {})
    architect = contracts.get("architect", {})
    wordsmith = contracts.get("wordsmith", {})
    director = contracts.get("director", {})

    # 動態決定顯示哪些 Tab
    tab_labels = ["🧠 Premise", "🏗️ Architect", "✍️ Wordsmith", "🎬 Director"]
    if is_mvp2 and audio_result:
        tab_labels.append("🎵 Audio")

    tabs = st.tabs(tab_labels)
    tab1, tab2, tab3, tab4 = tabs[0], tabs[1], tabs[2], tabs[3]
    tab_audio = tabs[4] if len(tabs) > 4 else None

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
        # Framework DNA 摘要
        fw_dna = contracts.get("framework_dna", {})
        if fw_dna:
            col_fw1, col_fw2, col_fw3 = st.columns(3)
            with col_fw1:
                st.metric("主框架", fw_dna.get("primary_framework", "").replace("_", " ").title())
            with col_fw2:
                st.metric("場景數量", f"{architect.get('scenes', []).__len__()} 幕")
            with col_fw3:
                st.metric("故事弧線", architect.get("story_arc", "").upper())

        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("情緒曲線 + 場景電荷")
            scenes = architect.get("scenes", [])
            if scenes:
                import altair as alt
                import pandas as pd
                df = pd.DataFrame([
                    {
                        "幕次": f"Scene {s.get('segment_id', i+1)}\n{s.get('role', '')}",
                        "強度": s.get("intensity", 0),
                        "電荷": f"{s.get('v_start','?')}→{s.get('v_end','?')}",
                        "能量": s.get("scene_energy", 0),
                    }
                    for i, s in enumerate(scenes)
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
                        tooltip=["幕次", "強度", "電荷", "能量"],
                    )
                    .properties(height=250)
                )
                st.altair_chart(chart, use_container_width=True)

            st.subheader("場景骨架")
            for s in scenes:
                v_start = s.get("v_start", "?")
                v_end = s.get("v_end", "?")
                energy = s.get("scene_energy", "?")
                charge_label = f"電荷 {v_start}→{v_end} [E={energy}]"
                with st.expander(
                    f"Scene {s.get('segment_id', '')} — {s.get('role', '')} "
                    f"(intensity={s.get('intensity', 0)}) | {charge_label}"
                ):
                    st.markdown(f"**節拍標籤：** `{s.get('beat_label', s.get('role', ''))}`")
                    st.markdown(f"**戲劇功能：** {s.get('dramatic_function', '')}")
                    st.markdown(f"**情緒目標：** `{s.get('emotional_target', '')}`")
                    st.markdown(f"**時長預算：** {s.get('duration_budget', 'N/A')}")
                    st.markdown(f"**轉場方式：** `{s.get('transition_to_next', 'null')}`")
                    col_v1, col_v2, col_v3 = st.columns(3)
                    with col_v1:
                        st.metric("V_start", v_start.title())
                    with col_v2:
                        st.metric("V_end", v_end.title())
                    with col_v3:
                        st.metric("Scene Energy", energy)

        with col2:
            st.subheader("全局設定")
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
        char_profile = wordsmith.get("character_profile", {})

        # 角色語音特質
        if char_profile:
            with st.expander("🎭 主角語音特質（Character Profile）"):
                voice = char_profile.get("protagonist_voice", {})
                col_v1, col_v2 = st.columns(2)
                with col_v1:
                    st.markdown(f"**說話模式：** {voice.get('speech_pattern', '')}")
                    st.markdown(f"**詞彙層次：** {voice.get('vocabulary_level', '')}")
                    st.markdown("**範例短語：** " + " / ".join(
                        f"`{p}`" for p in voice.get("sample_phrases", [])
                    ))
                with col_v2:
                    st.markdown(f"**核心缺陷：** {char_profile.get('core_flaw', '')}")
                    st.markdown(f"**隱藏動機：** {char_profile.get('hidden_motivation', '')}")
                    st.markdown("**說不出口的事：**")
                    for item in char_profile.get("cannot_say_directly", []):
                        st.markdown(f"- {item}")

        st.subheader("Naturalness Score 總覽")
        score_cols = st.columns(len(ws_scenes))
        for i, scene in enumerate(ws_scenes):
            score = scene.get("naturalness_score", 0)
            with score_cols[i]:
                color = "normal" if score and score >= 70 else "inverse"
                st.metric(
                    label=f"Scene {scene.get('segment_id', i+1)} {scene.get('role', '')}",
                    value=score if score else "N/A",
                    delta="通過" if score and score >= 70 else "未達標",
                    delta_color=color,
                )

        st.divider()
        st.subheader("文案內容")

        for scene in ws_scenes:
            score = scene.get("naturalness_score", 0)
            score_badge = f"✅ {score}" if score and score >= 70 else f"⚠️ {score}"
            beat_label = scene.get("beat_label", scene.get("role", ""))
            with st.expander(
                f"Scene {scene.get('segment_id', '')} — {beat_label} | naturalness={score_badge} | {scene.get('duration_est', '')}"
            ):
                st.markdown("**原始文案（raw）**")
                voice_script = scene.get("voice_script", {})
                st.markdown(
                    f"<div style='font-size:1.1em; line-height:1.8; padding:12px; "
                    f"background:#f0f2f6; border-radius:8px;'>"
                    f"{voice_script.get('raw', '')}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("**TTS 標記版本（Dialogue Assassin 後處理）**")
                st.code(voice_script.get("annotated", ""), language=None)

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
                st.markdown(f"**Scene {scene.get('segment_id', i+1)}**")
                st.caption(f"色調: {scene.get('visual', {}).get('color_grade', '')}")
                st.caption(f"BGM: {scene.get('audio', {}).get('bgm', {}).get('mood', '')}")

        st.divider()
        st.subheader("場景視聽指令")

        for scene in dir_scenes:
            beat_label = scene.get("beat_label", scene.get("role", ""))
            with st.expander(
                f"Scene {scene.get('segment_id', '')} — {beat_label} | {scene.get('visual', {}).get('shot_type', '')} | {scene.get('duration_est', '')}"
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

    # ── Tab 5: Audio（MVP-2 專用）─────────────────────────────
    if tab_audio and audio_result:
        with tab_audio:
            st.subheader("🎵 音軌驗證")

            # 合併音檔
            combined_path = audio_result.get("combined_audio", "")
            if combined_path and Path(combined_path).exists():
                st.markdown("**合併音檔（voice_combined.mp3）**")
                with open(combined_path, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
            st.divider()

            # 逐幕音檔
            st.subheader("逐幕音檔")
            scene_files = audio_result.get("scene_audio_files", [])
            dir_scenes_list = director.get("scenes", [])
            for i, audio_path in enumerate(scene_files):
                scene_info = dir_scenes_list[i] if i < len(dir_scenes_list) else {}
                seg_id = scene_info.get("segment_id", i + 1)
                role = scene_info.get("beat_label", scene_info.get("role", ""))
                dur = scene_info.get("duration_est", "")
                label = f"Scene {seg_id} — {role} | {dur}"

                with st.expander(label):
                    if Path(audio_path).exists():
                        with open(audio_path, "rb") as f:
                            st.audio(f.read(), format="audio/mp3")
                    else:
                        st.warning(f"音檔不存在：{audio_path}")

            st.divider()

            # 時長比較表
            st.subheader("時長比較（估算 vs 實際）")
            comparison = audio_result.get("duration_comparison", [])
            if comparison:
                import pandas as pd
                df = pd.DataFrame(comparison)
                df = df.rename(columns={
                    "segment_id": "Scene",
                    "role": "Role",
                    "estimated": "估算",
                    "estimated_sec": "估算(s)",
                    "actual_sec": "實際(s)",
                    "deviation_sec": "誤差(s)",
                    "within_threshold": "≤0.5s",
                })
                st.dataframe(
                    df[["Scene", "Role", "估算", "估算(s)", "實際(s)", "誤差(s)", "≤0.5s"]],
                    use_container_width=True,
                )

                all_pass = all(r["within_threshold"] for r in comparison)
                if all_pass:
                    st.success("✅ 所有幕時長誤差均在 ±0.5s 內（MVP-2 成功標準通過）")
                else:
                    failed = [r for r in comparison if not r["within_threshold"]]
                    st.warning(f"⚠️ {len(failed)} 幕時長誤差超過 0.5s")

            st.divider()

            # 字幕內容
            st.subheader("Whisper 對齊結果（subtitle.srt）")
            srt_path = audio_result.get("subtitle_srt", "")
            alignment = audio_result.get("alignment", [])

            if alignment:
                for seg in alignment:
                    st.markdown(
                        f"`{seg['start']:.2f}s → {seg['end']:.2f}s` &nbsp; {seg['text']}",
                        unsafe_allow_html=True,
                    )

            if srt_path and Path(srt_path).exists():
                with st.expander("原始 SRT 內容"):
                    st.code(Path(srt_path).read_text(encoding="utf-8"), language=None)

elif state and state["status"] == "failed":
    st.error("Pipeline 執行失敗")
    for err in state.get("errors", []):
        st.markdown(f"**Stage:** `{err['stage']}`")
        st.markdown(f"**原因：** {err['reason']}")

elif not framework_dna:
    col1, col2 = st.columns(2)
    with col1:
        st.info("👈 在左側填入主題內容後，按「🔍 分析主題」開始框架策略分析。")
    with col2:
        with st.expander("使用說明"):
            st.markdown("""
            **Step 1：分析主題**
            - 填入標題、摘要、關鍵詞
            - 按「🔍 分析主題（Strategy Layer）」
            - 系統自動分析最適框架配方

            **Step 2：確認導演簡報**
            - 閱讀框架策略與情感弧線描述
            - 確認後開始生成劇本

            **Step 3：查看劇本結果**
            - Architect Tab 顯示場景電荷（v_start/v_end）
            - Wordsmith Tab 顯示角色語音特質與文案

            **MVP-2：生成音軌**
            - 需設定 `ELEVENLABS_API_KEY`
            """)
