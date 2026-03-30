"""
AutoReel-Flow — Audio Pipeline (MVP-2)
Director Contract → ElevenLabs TTS（逐幕）→ pydub 合併 → Whisper 句級對齊 → subtitle.srt
"""

import json
import logging
import re
from pathlib import Path

from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, WHISPER_MODEL

logger = logging.getLogger(__name__)

# ── ElevenLabs style 字串 → style exaggeration float 映射 ────────────────────
# ElevenLabs style 參數：0.0 = 無誇張（穩定）, 1.0 = 最大誇張（容易失真）
STYLE_MAP: dict[str, float] = {
    "intimate_whisper":  0.15,
    "measured_serious":  0.20,
    "grounded_warm":     0.25,
    "revelatory_rising": 0.55,
    "urgent_direct":     0.75,
}

# ── 正則：匹配 [pause:Xs] 或 [pause:X.Xs] ────────────────────────────────────
_PAUSE_RE = re.compile(r"\[pause:(\d+(?:\.\d+)?)s\]")


def _annotated_to_ssml(annotated: str) -> str:
    """
    將 Wordsmith annotated 文稿轉為 ElevenLabs SSML。
    [pause:Xs] → <break time="Xs"/>
    整段包裹在 <speak>...</speak>。
    """
    ssml_body = _PAUSE_RE.sub(lambda m: f'<break time="{m.group(1)}s"/>', annotated)
    return f"<speak>{ssml_body}</speak>"


def _tts_params_to_voice_settings(tts_params: dict):
    """
    將 Wordsmith tts_params 轉為 ElevenLabs VoiceSettings。
    style 字串映射為 ElevenLabs style float；其餘參數直接傳入。
    """
    from elevenlabs import VoiceSettings

    style_str = tts_params.get("style", "measured_serious")
    style_float = STYLE_MAP.get(style_str, 0.25)

    return VoiceSettings(
        stability=float(tts_params.get("stability", 0.5)),
        similarity_boost=float(tts_params.get("similarity_boost", 0.75)),
        style=style_float,
        use_speaker_boost=True,
    )


def generate_scene_audio(
    scene: dict,
    output_path: Path,
) -> Path:
    """
    呼叫 ElevenLabs TTS，為單一場景生成音檔。

    Args:
        scene: Director contract 的單一 scene 物件
        output_path: 輸出 MP3 檔案路徑

    Returns:
        輸出檔案路徑
    """
    from elevenlabs.client import ElevenLabs

    audio_data = scene.get("audio", {})
    annotated_script = audio_data.get("voice_script", "")
    tts_params = audio_data.get("tts_params", {})

    ssml_text = _annotated_to_ssml(annotated_script)
    voice_settings = _tts_params_to_voice_settings(tts_params)

    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    logger.info(f"呼叫 ElevenLabs TTS — Scene {scene.get('segment_id')}")
    audio_generator = client.text_to_speech.convert(
        voice_id=ELEVENLABS_VOICE_ID,
        text=ssml_text,
        model_id="eleven_multilingual_v2",
        voice_settings=voice_settings,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)

    logger.info(f"  ✓ 儲存至 {output_path}")
    return output_path


def combine_audio(scene_files: list[Path], output_path: Path) -> Path:
    """
    用 pydub 串接所有場景 MP3，輸出 voice_combined.mp3。

    Args:
        scene_files: 依序排列的場景 MP3 路徑清單
        output_path: 輸出合併音檔路徑

    Returns:
        輸出檔案路徑
    """
    from pydub import AudioSegment

    if not scene_files:
        raise ValueError("scene_files is empty")

    logger.info(f"合併 {len(scene_files)} 個場景音檔...")
    combined = AudioSegment.empty()
    for path in scene_files:
        seg = AudioSegment.from_mp3(str(path))
        combined += seg
        logger.info(f"  + {path.name} ({len(seg) / 1000:.1f}s)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(output_path), format="mp3")
    logger.info(f"  ✓ 合併完成 → {output_path} (總長 {len(combined) / 1000:.1f}s)")
    return output_path


def _seconds_to_srt_time(seconds: float) -> str:
    """將秒數轉為 SRT 時間格式：HH:MM:SS,mmm"""
    ms = int((seconds % 1) * 1000)
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def align_with_whisper(
    audio_path: Path,
    output_path: Path,
) -> list[dict]:
    """
    用 Whisper 對合併音檔做句級對齊，輸出 subtitle.srt。
    精度目標：±0.3s（MVP-2 成功標準 ±0.5s）

    Args:
        audio_path: 合併後的 MP3 路徑
        output_path: subtitle.srt 輸出路徑

    Returns:
        alignment list: [{index, start, end, text}, ...]
    """
    import whisper

    logger.info(f"載入 Whisper 模型（{WHISPER_MODEL}）...")
    model = whisper.load_model(WHISPER_MODEL)

    logger.info(f"執行 Whisper 句級對齊：{audio_path}")
    result = model.transcribe(
        str(audio_path),
        language="zh",
        verbose=False,
    )

    segments = result.get("segments", [])
    alignment = []
    srt_lines = []

    for i, seg in enumerate(segments, start=1):
        start = float(seg["start"])
        end = float(seg["end"])
        text = seg["text"].strip()

        alignment.append({
            "index": i,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": text,
        })

        srt_lines.append(str(i))
        srt_lines.append(f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}")
        srt_lines.append(text)
        srt_lines.append("")  # 空行分隔

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(srt_lines), encoding="utf-8")
    logger.info(f"  ✓ 字幕輸出 → {output_path}（{len(segments)} 個句段）")

    return alignment


def _parse_seconds(duration_str: str) -> float:
    """將 '12s' 轉為浮點秒數。"""
    match = re.match(r"^(\d+(?:\.\d+)?)s?$", str(duration_str).strip())
    if not match:
        return 0.0
    return float(match.group(1))


def run_audio_pipeline(director_contract: dict, project_id: str) -> dict:
    """
    執行完整 Audio Pipeline（MVP-2）。

    流程：
    1. 逐幕呼叫 ElevenLabs TTS → scene_N.mp3
    2. pydub 合併 → voice_combined.mp3
    3. Whisper 對齊 → subtitle.srt
    4. 建立 duration_comparison（估算 vs 實際）

    Args:
        director_contract: Director Agent 產出的 Contract
        project_id: 專案 ID（用於輸出目錄命名）

    Returns:
        audio_result dict
    """
    from pydub import AudioSegment

    output_dir = Path("outputs/audio") / project_id
    output_dir.mkdir(parents=True, exist_ok=True)

    scenes = director_contract.get("scenes", [])
    if not scenes:
        raise ValueError("Director contract has no scenes")

    # ── Step 1: 逐幕 TTS ─────────────────────────────────────────────────────
    print(f"\n▶ Audio Step 1/3: ElevenLabs TTS（{len(scenes)} 幕）")
    scene_audio_files: list[Path] = []

    for scene in scenes:
        seg_id = scene.get("segment_id", len(scene_audio_files) + 1)
        output_path = output_dir / f"scene_{seg_id}.mp3"
        generate_scene_audio(scene, output_path)
        scene_audio_files.append(output_path)
        print(f"  ✓ Scene {seg_id} → {output_path.name}")

    # ── Step 2: 合併音檔 ──────────────────────────────────────────────────────
    print("\n▶ Audio Step 2/3: 合併音檔")
    combined_path = output_dir / "voice_combined.mp3"
    combine_audio(scene_audio_files, combined_path)
    print(f"  ✓ voice_combined.mp3 → {combined_path}")

    # ── Step 3: Whisper 對齊 ──────────────────────────────────────────────────
    print("\n▶ Audio Step 3/3: Whisper 句級對齊")
    srt_path = output_dir / "subtitle.srt"
    alignment = align_with_whisper(combined_path, srt_path)
    print(f"  ✓ subtitle.srt → {srt_path}（{len(alignment)} 個句段）")

    # ── 建立 duration_comparison ──────────────────────────────────────────────
    duration_comparison = []
    for i, (scene, audio_path) in enumerate(zip(scenes, scene_audio_files)):
        seg_id = scene.get("segment_id", i + 1)
        estimated_str = scene.get("duration_est", "0s")
        estimated = _parse_seconds(estimated_str)

        try:
            actual_seg = AudioSegment.from_mp3(str(audio_path))
            actual = round(len(actual_seg) / 1000, 2)
        except Exception:
            actual = 0.0

        deviation = round(abs(actual - estimated), 2)
        duration_comparison.append({
            "segment_id": seg_id,
            "role": scene.get("role", ""),
            "estimated": estimated_str,
            "estimated_sec": estimated,
            "actual_sec": actual,
            "deviation_sec": deviation,
            "within_threshold": deviation <= 0.5,
        })

    audio_result = {
        "project_id": project_id,
        "scene_audio_files": [str(p) for p in scene_audio_files],
        "combined_audio": str(combined_path),
        "subtitle_srt": str(srt_path),
        "alignment": alignment,
        "duration_comparison": duration_comparison,
    }

    # 儲存結果 JSON
    result_path = output_dir / "audio_result.json"
    result_path.write_text(
        json.dumps(audio_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  💾 audio_result.json → {result_path}")

    return audio_result
