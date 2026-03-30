# AutoReel-Flow
> 基於多 Agent 協作的戲劇化短影音自動化生產系統

---

## 專案概覽

**核心命題**：將非結構化的趨勢資訊，透過具備情緒曲線的劇本設計層，轉化為可穩定量產的戲劇化短影音。

**當前階段**：技術驗證（Phase 1–4），優先確保 Pipeline 穩定，再考慮量產優化。

**技術選型**：
- LLM：Claude API（claude-sonnet-4-20250514）
- TTS：ElevenLabs API
- 語音對齊：Whisper（句級，非逐字）
- 視覺素材：Pexels API
- 渲染引擎：FFmpeg（Headless，優先於 MoviePy）
- 語言：Python 3.11+
- 套件管理：poetry 或 pip + requirements.txt

---

## 目錄結構

```
autoreel-flow-pro/
├── CLAUDE.md                  # 本文件
├── main.py                    # 端到端 Pipeline 入口
├── config.py                  # API Keys、全域參數
├── requirements.txt
│
├── ingestion/
│   └── scraper.py             # Trend Scraper：抓取並清洗趨勢內容
│
├── dramaturgy/                # 劇本設計層（核心）
│   ├── premise.py             # The Premise Agent
│   ├── architect.py           # The Architect Agent
│   ├── wordsmith.py           # The Wordsmith Agent
│   ├── director.py            # The Director Agent
│   ├── validator.py           # Contract Validator（每層產出後執行）
│   └── prompts/               # 所有 Agent 的 Prompt 模板
│       ├── premise_system.txt
│       ├── premise_user.txt
│       ├── architect_system.txt
│       ├── architect_user.txt
│       ├── wordsmith_system.txt
│       ├── wordsmith_scene.txt
│       ├── wordsmith_evaluator.txt
│       ├── director_system.txt
│       └── director_scene.txt
│
├── execution/                 # 素材生成層
│   ├── audio_pipeline.py      # ElevenLabs TTS + Whisper 對齊
│   └── visual_pipeline.py     # Pexels API 素材檢索與裁切
│
├── composer/
│   └── ffmpeg_composer.py     # 合成輸出層
│
├── contracts/                 # JSON Contract Schema 定義與範例
│   ├── schemas/
│   │   ├── premise_contract.json
│   │   ├── architect_contract.json
│   │   ├── wordsmith_contract.json
│   │   └── director_contract.json
│   └── examples/
│       └── sleep_example/     # 完整情境範例（睡眠主題）
│
├── outputs/                   # 最終輸出目錄
│   ├── contracts/             # 各 Agent 產出的 JSON
│   ├── audio/                 # 語音檔、BGM、字幕
│   ├── visual/                # 下載的視覺素材
│   └── final/                 # 最終 .mp4
│
└── tests/
    ├── test_validator.py
    ├── test_premise.py
    ├── test_architect.py
    ├── test_wordsmith.py
    └── test_director.py
```

---

## 系統架構：四層 Pipeline

```
[1. 資料輸入層]
  Trend Scraper
       ↓ Raw Content (dict)
[2. 劇本設計層]
  The Premise  →  The Architect  →  The Wordsmith  →  The Director
       ↓               ↓                  ↓                 ↓
  Validator        Validator           Validator          Validator
       ↓                                                    ↓
                                              Final JSON Contract
[3. 素材生成層（並行）]
  Audio Pipeline          Visual Pipeline
  TTS → Whisper           Pexels → 裁切
       ↓                       ↓
[4. 合成輸出層]
  FFmpeg Composer
       ↓
  output_reel.mp4
```

**重要原則**：每個 Agent 產出後立即執行 Contract Validator。驗證失敗則打回該 Agent 重跑，不允許錯誤靜默流入下一層。最多重試 3 次，超過則拋出 `PipelineError`。

---

## 劇本設計層詳細規格

### The Premise — 前提定義師

**職責**：從 Raw Content 提煉核心張力，定義「這個故事值得被說的理由」。

**輸入**：`dict` 包含 `title`, `summary`, `keywords`, `engagement_score`

**輸出 Schema**（`contracts/schemas/premise_contract.json`）：

```json
{
  "premise_id": "string",
  "generated_at": "ISO8601",
  "core_tension": {
    "force_a": "string（觀眾原本相信的）",
    "force_b": "string（現實打臉的）",
    "conflict_type": "belief_vs_reality | desire_vs_cost | us_vs_system | known_vs_unknown"
  },
  "audience": {
    "pain_point": "string（具體情緒或處境）",
    "assumed_belief": "string",
    "desired_shift": "string"
  },
  "payoff": {
    "promise": "string",
    "emotional_reward": "string",
    "takeaway_type": "reframe | revelation | permission"
  },
  "story_constraints": {
    "recommended_arc": "suspense | emotional",
    "tone": "string",
    "forbidden": ["string"]
  }
}
```

**conflict_type 對應邏輯**：
- `belief_vs_reality` → 常識被現實打臉 → 建議 `suspense`
- `desire_vs_cost` → 想要的東西代價太高 → 建議 `emotional`
- `us_vs_system` → 個人對抗結構性困境 → 建議 `emotional`
- `known_vs_unknown` → 熟悉事物隱藏危機 → 建議 `suspense`

**Validator 規則**：
- `core_tension.force_a` 與 `force_b` 不能語意相近（用 LLM 判斷）
- `audience.pain_point` 不能是抽象描述（字數 > 8 字，需包含情緒詞）
- `story_constraints.forbidden` 至少兩項
- 所有必填欄位存在且非空

---

### The Architect — 結構師

**職責**：根據 Premise Contract 推導敘事骨架與情緒曲線。

**輸入**：Premise Contract

**輸出 Schema**（`contracts/schemas/architect_contract.json`）：

```json
{
  "architect_id": "string",
  "premise_id": "string",
  "story_arc": "suspense | emotional",
  "total_duration_target": "string（如 '60s'）",
  "hook_strategy": {
    "type": "belief_affirmation_then_denial | pain_amplification | shared_enemy_framing | false_familiarity",
    "opening_move": "string",
    "tension_entry_point": "string"
  },
  "scenes": [
    {
      "segment_id": "integer",
      "role": "Hook | Tension_Build | Reveal | Reward",
      "duration_budget": "string（如 '5s'）",
      "dramatic_function": "string",
      "emotional_target": "recognition | curiosity_with_unease | realization | relief_and_clarity",
      "intensity": "float（0.0–1.0）",
      "transition_to_next": "sudden_reversal | escalate | release | callback | null"
    }
  ],
  "pacing_notes": "string",
  "forbidden_enforced": ["string"]
}
```

**hook_strategy 推導規則**（依 `conflict_type`）：
- `belief_vs_reality` → `belief_affirmation_then_denial`
- `desire_vs_cost` → `pain_amplification`
- `us_vs_system` → `shared_enemy_framing`
- `known_vs_unknown` → `false_familiarity`

**Validator 規則**：
```python
# 實作於 validator.py: validate_architect(contract)
assert 0.5 <= scenes[0]["intensity"] <= 0.7          # Hook 強度範圍
assert max(intensities) >= 0.85                       # 必須有情緒高峰
assert scenes[-1]["intensity"] < max(intensities)     # Reward 不是最高點
assert 45 <= total_duration_seconds <= 90             # 總時長範圍
assert set(forbidden_enforced) >= set(premise_forbidden)  # 繼承禁忌清單
```

---

### The Wordsmith — 修辭師

**職責**：將場景骨架轉化為具人類語感的文案與 TTS 執行參數。

**輸入**：單一 scene 物件（逐幕呼叫）+ global context（Premise tone、forbidden）

**輸出 Schema**（`contracts/schemas/wordsmith_contract.json`）：

```json
{
  "wordsmith_id": "string",
  "architect_id": "string",
  "scenes": [
    {
      "segment_id": "integer",
      "role": "string",
      "emotional_target": "string",
      "intensity": "float",
      "voice_script": {
        "raw": "string（純文字，供人工評審）",
        "annotated": "string（含 [pause:Xs] 標記，供 TTS）"
      },
      "language_markers": {
        "oral_hooks": ["string"],
        "pause_count": "integer",
        "avg_sentence_length": "integer",
        "rhetorical_device": "rhetorical_question | preemptive_defense | contrast_pivot | concrete_anchor | second_person_mirror | open_loop"
      },
      "tts_params": {
        "stability": "float（0.0–1.0）",
        "similarity_boost": "float（0.0–1.0）",
        "style": "intimate_whisper | measured_serious | revelatory_rising | grounded_warm | urgent_direct",
        "speaking_rate": "float（0.7–1.2）"
      },
      "naturalness_score": "integer | null",
      "duration_est": "string"
    }
  ],
  "global_language_profile": {
    "dominant_tone": "string",
    "forbidden_phrases": ["string"],
    "signature_transitions": ["string"]
  }
}
```

**tts_params 對應 intensity**：
- `intensity < 0.5` → `style: grounded_warm`, `stability: 0.55–0.7`
- `intensity 0.5–0.7` → `style: intimate_whisper` 或 `measured_serious`, `stability: 0.4–0.55`
- `intensity 0.7–0.85` → `style: revelatory_rising`, `stability: 0.35–0.5`
- `intensity > 0.85` → `style: urgent_direct`, `stability: 0.3–0.45`

**naturalness_score 評估**：
- Wordsmith 產出後，用第二個獨立 LLM 呼叫評審（`prompts/wordsmith_evaluator.txt`）
- 評分維度：口語自然度(25) + 情緒真實感(25) + 停頓合理性(25) + 禁忌規避(25)
- 分數 < 70：自動帶入 `flags` 重跑，最多重試 3 次
- 分數 ≥ 70：通過，寫入 `naturalness_score` 欄位

**Validator 規則**：
```python
# 實作於 validator.py: validate_wordsmith(contract, architect_contract)
for scene in scenes:
    arch_budget = parse_seconds(architect_scene["duration_budget"])
    est = parse_seconds(scene["duration_est"])
    assert abs(est - arch_budget) / arch_budget <= 0.2    # 時長誤差 ±20%
    assert abs(scene["intensity"] - arch_intensity) <= 0.05  # intensity 誤差 ±0.05
    if scene["intensity"] > 0.7:
        assert scene["language_markers"]["pause_count"] >= 3  # 高強度幕需要足夠停頓
    for phrase in forbidden_phrases:
        assert phrase not in scene["voice_script"]["raw"]    # 禁用詞檢查
```

---

### The Director — 導演

**職責**：將文案與場景參數轉化為完整視聽執行指令，輸出 Final JSON Contract。

**輸入**：Wordsmith Contract + Architect Contract + Premise `dominant_tone`（直接繼承，跳過中間層）

**輸出 Schema**（`contracts/schemas/director_contract.json`）：

```json
{
  "director_id": "string",
  "wordsmith_id": "string",
  "project_id": "string",
  "story_arc": "string",
  "total_duration_est": "string",
  "scenes": [
    {
      "segment_id": "integer",
      "role": "string",
      "intensity": "float",
      "duration_est": "string",
      "audio": {
        "voice_script": "string（annotated 版本）",
        "tts_params": {},
        "sfx": "string | none",
        "bgm": {
          "mood": "string",
          "volume_duck": "float（0.0–1.0）",
          "fade_in": "string"
        }
      },
      "visual": {
        "prompt": "string（英文，供 Pexels 搜尋）",
        "mood_tag": "string",
        "shot_type": "extreme_close_up | medium_shot | wide_shot | dynamic_cut",
        "color_grade": "muted_warm | cold_desaturated | high_contrast",
        "motion": "static | slow_push_in | dynamic_cut",
        "cut_timing": "on_pause | on_beat | on_sentence"
      },
      "sync": {
        "cut_trigger": "pause | beat | sentence_end",
        "cut_at_second": "float",
        "subtitle_style": "minimal_fade | bold_reveal"
      }
    }
  ],
  "global_av_profile": {
    "color_grade_arc": ["string"],
    "bgm_arc": ["string"],
    "subtitle_font_style": "string",
    "aspect_ratio": "9:16"
  }
}
```

**visual.prompt 生成規則**（三訊號疊加）：

| 訊號 | 來源 | 決定 |
|------|------|------|
| `intensity` | Architect | `shot_type` |
| `emotional_target` | Architect | `color_grade` |
| `dominant_tone` | Premise（直接繼承） | 整體視覺基調 |

**intensity → shot_type**：
- `0.0–0.5` → `extreme_close_up`
- `0.5–0.7` → `medium_shot`
- `0.7–0.85` → `wide_shot`
- `0.85–1.0` → `dynamic_cut`

**emotional_target → color_grade**：
- `recognition` → `muted_warm`
- `curiosity_with_unease` → `cold_desaturated`
- `realization` → `high_contrast`
- `relief_and_clarity` → `muted_warm`

**Validator 規則**：
```python
# 實作於 validator.py: validate_director(contract, wordsmith_contract, architect_contract)
assert len(scenes) == len(wordsmith_scenes) == len(architect_scenes)
for i, scene in enumerate(scenes):
    ws_dur = parse_seconds(wordsmith_scenes[i]["duration_est"])
    assert abs(parse_seconds(scene["duration_est"]) - ws_dur) < 0.1
total = sum(parse_seconds(s["duration_est"]) for s in scenes)
assert abs(total - parse_seconds(contract["total_duration_est"])) < 0.5
assert len(color_grade_arc) == len(bgm_arc) == len(scenes)
for i, scene in enumerate(scenes):
    assert scene["visual"]["color_grade"] == color_grade_arc[i]
    assert any(kw in scene["visual"]["prompt"].lower()
               for kw in ["close-up", "medium", "wide", "dynamic"])
```

---

## Prompt 模板規範

所有 Prompt 存放於 `dramaturgy/prompts/`，以 `.txt` 格式管理，方便迭代而不需改動 Python 程式碼。

### 共用規則（所有 Agent）

每個 Agent 的 Prompt 末尾必須加上：
```
請只輸出符合 schema 的 JSON，不含任何前言、說明文字或 markdown 代碼塊。
```

### Wordsmith 的特殊規則

`wordsmith_system.txt` 包含固定的語感禁忌：
- 禁止書面語：「然而」、「此外」、「值得注意的是」、「綜上所述」
- 禁止說教語氣：「你應該」、「你必須」、「重要的是」
- 必須使用口語轉折：「結果你猜」、「但問題是」、「其實」、「不是說」

`wordsmith_scene.txt` 逐幕呼叫，接收的變數：
```
{{segment_id}}, {{dramatic_function}}, {{emotional_target}},
{{intensity}}, {{transition_from_previous}}, {{forbidden_phrases}},
{{forbidden_enforced}}
```

`wordsmith_evaluator.txt` 用於 naturalness_score 評審，輸出格式：
```json
{
  "score": 0,
  "breakdown": {
    "oral_naturalness": 0,
    "emotional_authenticity": 0,
    "pause_logic": 0,
    "forbidden_compliance": 0
  },
  "flags": ["string"]
}
```

---

## 執行層規格

### Audio Pipeline（`execution/audio_pipeline.py`）

```python
# 執行順序
# 1. 逐幕呼叫 ElevenLabs API，傳入 annotated voice_script + tts_params
# 2. 合併四幕語音為單一 voice_combined.mp3
# 3. 用 Whisper 對 voice_combined.mp3 做句級對齊，輸出 subtitle.srt
# 4. 根據 bgm_arc 從素材庫選取 BGM，依 volume_duck 設定各段音量曲線

# 注意：使用句級對齊（非逐字），精度目標 ±0.3s
# Whisper model: "base" 或 "small" 在驗證階段已足夠
```

### Visual Pipeline（`execution/visual_pipeline.py`）

```python
# 執行順序
# 1. 逐幕用 visual.prompt 呼叫 Pexels API，取得 3 個候選素材
# 2. 依 color_grade 標籤過濾（muted_warm / cold_desaturated / high_contrast）
# 3. 依 shot_type 確認構圖合適性（close-up 優先人臉/物件特寫）
# 4. 下載並裁切為 9:16，時長對齊 duration_est
# 5. 若 Pexels 無合適素材，記錄 warning 並使用 fallback 素材

# 注意：驗證階段不使用 Sora，只用 Pexels
```

### FFmpeg Composer（`composer/ffmpeg_composer.py`）

```python
# 核心合成指令（概念）：
# - 拼接四幕影片 → scene_concat.mp4
# - 疊加語音 + BGM（sidechaincompress 做 Ducking）
# - 疊加動態字幕（drawtext，依 subtitle.srt 時間軸）
# - 輸出 H.264, 1080x1920, 9:16

# 使用 FFmpeg subprocess 呼叫，不使用 MoviePy
# BGM Ducking 參數：語音期間壓低至 volume_duck 比例
# 字幕樣式依 subtitle_style 切換（minimal_fade / bold_reveal）
```

---

## 狀態機與錯誤處理

### Pipeline 狀態

```python
# main.py 中維護的 pipeline_state
{
    "project_id": "string",
    "status": "running | failed | completed",
    "current_stage": "premise | architect | wordsmith | director | audio | visual | compose",
    "retry_count": {
        "premise": 0,
        "architect": 0,
        "wordsmith_scene_1": 0,
        # ...
    },
    "contracts": {
        "premise": {},      # 通過 Validator 後存入
        "architect": {},
        "wordsmith": {},
        "director": {}
    },
    "errors": []
}
```

### 重試規則

```python
MAX_RETRIES = 3

# Wordsmith 重試時，將 naturalness_score 的 flags 帶入下一次 prompt
# Architect 重試時，調整 intensity 分佈提示
# 任何 Agent 超過 MAX_RETRIES → raise PipelineError，記錄失敗原因
```

### PipelineError

```python
class PipelineError(Exception):
    def __init__(self, stage, reason, last_output):
        self.stage = stage
        self.reason = reason
        self.last_output = last_output  # 保留最後一次失敗的輸出，供除錯
```

---

## 技術驗證四階段

### Phase 1：劇本品質驗證
**目標**：Premise → Architect → Wordsmith → Director 能穩定產出一份通過 Validator 的 JSON Contract。

**成功標準**：
- 人工閱讀 `voice_script.raw`，語感自然，不像 AI 寫的
- 情緒曲線（intensity）有明顯起伏，不是一條平線
- `visual.prompt` 輸入 Pexels 能找到合適素材
- `naturalness_score` 全幕 ≥ 70

**驗證方式**：固定使用「睡眠與生產力」主題的 Raw Content 跑 10 次，觀察輸出穩定性。

### Phase 2：音軌生成驗證
**目標**：JSON Contract → TTS → Whisper 句級對齊，產出正確帶時間軸的語音。

**成功標準**：
- 語音播放自然，`[pause]` 位置符合預期
- Whisper 時間軸誤差 < ±0.3s
- BGM Ducking 在語音段落正確壓低

### Phase 3：合成驗證
**目標**：固定素材 + Phase 2 音軌 → FFmpeg 合成完整影片。

**成功標準**：
- 影片可完整播放，無黑屏或音畫不同步
- 字幕出現時間與語音對應
- BGM 在語音段落明顯壓低，語音結束後恢復

### Phase 4：端到端串接
**目標**：從 Raw Content 輸入到 `.mp4` 輸出，全程無人工介入。

**成功標準**：
- Pipeline 完整跑通，輸出一支完整影片
- 無 `PipelineError` 拋出
- 各 Agent 重試次數 ≤ 1（穩定性指標）

---

## 暫不實作（驗證階段排除）

| 功能 | 排除原因 | 規劃時程 |
|------|----------|----------|
| Feedback Loop | 產出量不足，無意義優化訊號 | Phase 4 穩定後 |
| 逐字卡點對齊 | 精度要求製造過高複雜度 | Phase 4 後升級 |
| Sora 視覺生成 | 成本高，一致性控制複雜 | 量產階段評估 |
| 多平台發佈 | 超出驗證範圍 | 量產階段 |

---

## 環境設定

```bash
# 安裝依賴
pip install anthropic elevenlabs openai-whisper requests ffmpeg-python jsonschema

# 環境變數（.env）
ANTHROPIC_API_KEY=...
ELEVENLABS_API_KEY=...
PEXELS_API_KEY=...

# FFmpeg 需要系統安裝
# macOS: brew install ffmpeg
# Ubuntu: apt install ffmpeg
```

---

## 開發注意事項

1. **所有 Agent 呼叫統一走 `dramaturgy/` 模組**，不在 `main.py` 直接寫 LLM 呼叫邏輯。

2. **Prompt 模板只改 `.txt` 檔**，不動 Python 程式碼，保持迭代靈活性。

3. **Validator 是強制關卡**，不可繞過。任何「先讓它跑起來再說」的衝動都應該抵抗——讓錯誤在早期爆出比讓它流到 FFmpeg 更容易 debug。

4. **`dominant_tone` 從 Premise 直接傳給 Director**，不經過 Architect 或 Wordsmith 轉譯。在 `main.py` 的 Pipeline 中明確傳遞這個值。

5. **Wordsmith 逐幕呼叫**，不是一次傳入所有場景。每幕獨立呼叫、獨立評審、獨立驗證。

6. **FFmpeg 使用 subprocess 呼叫**，不使用 MoviePy。如遇到 FFmpeg 指令問題，優先查 FFmpeg 文件而不是換用 MoviePy。

7. **輸出檔案統一存放 `outputs/` 下對應子目錄**，每次執行以 `project_id` 建立子資料夾隔離。