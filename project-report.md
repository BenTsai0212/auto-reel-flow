AutoReel-Flow 完整專案規格書

基於多 Agent 協作的戲劇化短影音自動化生產系統
版本	v3.1（技術驗證版）
定位	驗證核心技術可行性，建立穩定 Pipeline 後再落地量產
更新日期	2026-03-30
一、 專案定位

AutoReel-Flow Pro v3.1 的核心命題是：將非結構化的趨勢資訊，透過具備情緒曲線的劇本設計層，轉化為可穩定量產的戲劇化短影音 。
v3.1 相較於 v3.0 的核心調整：

    新增 The Premise Agent：在結構規劃前定義核心張力，解決故事性不足的問題 。

    引入 Contract Validator：在每個 Agent 產出後執行 Schema 驗證與邏輯檢查，防止錯誤流入執行層 。

    音畫對齊調整：從逐字級降為句子級，降低驗證期的技術複雜度 。

    暫不實作 Feedback Loop：待 Phase 4 穩定後再行規劃 。

二、 系統架構

系統採解耦設計，分為四層，層間通訊標準化為 JSON Contract 。
層級	名稱	核心職責
1	資料輸入層	

趨勢爬蟲，將外部內容轉化為 Raw Content
2	劇本設計層	

多 Agent 協作，產出具情緒曲線的 JSON Contract
3	素材生成層	

並行處理音軌（TTS + 對齊）與視覺素材（Pexels）
4	合成輸出層	

FFmpeg 渲染，輸出最終 .mp4 成品
三、 劇本設計層詳解

此層為系統核心競爭力，由四個 Agent 依序協作 ：
Agent	角色	輸入	輸出
The Premise	前提定義師	Raw Content	core_tension / audience / payoff
The Architect	結構師	Premise Contract	scenes 骨架 / intensity / duration_budget
The Wordsmith	修辭師	場景骨架	voice_script / tts_params / language_markers
The Director	導演	voice_script + intensity	visual.prompt / bgm / sync
3.1 The Premise — 前提定義師

負責定義「這個故事值得被說的理由」，提供核心張力作為敘事推導的基礎 。

    核心衝突類型 (conflict_type) ：

        belief_vs_reality：常識被現實打臉（建議：suspense）

        desire_vs_cost：想要的代價太高（建議：emotional）

        us_vs_system：個人對抗結構性困境（建議：emotional）

        known_vs_unknown：熟悉事物隱藏危機（建議：suspense）

3.2 The Architect — 結構師

將張力轉化為具體的場景配置與情緒曲線 。

    Hook 策略：根據衝突類型選擇開場方式，如 pain_amplification（直接放大痛點）或 false_familiarity（用熟悉包裝危機） 。

    Validator 規則：

        Hook 強度須在 0.5–0.7 之間 。

        全片至少一幕強度需超過 0.85 。

        總時長控制在 45–90 秒 。

3.3 The Wordsmith — 修辭師

核心任務是去除 AI 腔調，注入真人語感 。

    雙軌設計：提供 raw（人工評審用）與 annotated（含 TTS 停頓標記，如 [pause:0.6s]）兩種版本 。

    評估機制：由獨立 LLM 進行 naturalness_score 評分，維度包含口語自然度、情緒真實感、停頓合理性及禁忌規避。低於 70 分則退回重跑 。

3.4 The Director — 導演

將上游資訊轉化為視聽指令，確保音軌與視覺情緒同步 。

    視覺映射：根據 intensity 決定鏡頭類型（如 0.85–1.0 為 dynamic_cut 快切）；根據 emotional_target 決定色調（如 realization 對應 high_contrast） 。

四、 技術驗證四階段

採分階段策略，確保問題可被隔離定位 。

    Phase 1: 劇本品質：產出完整 JSON Contract，通過人工語感與情緒評審 。

    Phase 2: 音軌生成：結合 TTS 與 Whisper 句級對齊，產出帶時間軸的語音 。

    Phase 3: 合成驗證：使用 FFmpeg 合成影片，檢查音畫同步與 BGM 效果 。

    Phase 4: 端到端串接：全程自動化跑通，流程無阻斷性錯誤 。

五、 工程實作與技術選型

    狀態管理：使用狀態機管理 JSON 傳遞，配合 Contract Validator 攔截錯誤 。

    渲染優化：使用 FFmpeg 指令集（效能優於 MoviePy），處理 BGM Ducking 與動態字幕 。

    技術棧 ：

        LLM: Claude Sonnet / GPT-4o

        TTS: ElevenLabs API

        對齊: Whisper（句級）

        視覺素材: Pexels API

        渲染: FFmpeg (Headless)