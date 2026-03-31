"""
The Wordsmith Agent — 修辭師
將場景骨架轉化為具人類語感的文案與 TTS 執行參數。
逐幕呼叫，每幕獨立評審（naturalness_score）。
新增：Character Architect（角色語音特質）+ Dialogue Assassin（對白後處理）。
"""

import json
import uuid
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL, MAX_RETRIES, NATURALNESS_THRESHOLD
from dramaturgy.validator import validate_wordsmith, ValidationError
from dramaturgy.premise import PipelineError


_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _call_llm(system: str, user: str, max_tokens: int = 2048) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def _generate_character_profile(
    premise_contract: dict,
    framework_dna: dict | None,
) -> dict:
    """
    生成主角/旁白的語音特質與心理檔案（Character Architect 子系統）。
    讓 Wordsmith 生成文案時有一致的「聲音」。
    """
    template = _load_prompt("character_profile.txt")
    user = (
        template
        .replace("{{premise_contract}}", json.dumps(premise_contract, ensure_ascii=False, indent=2))
        .replace("{{framework_dna}}", json.dumps(framework_dna or {}, ensure_ascii=False, indent=2))
    )
    system = "你是角色語音設計師，專門為短影音旁白定義說話風格與心理底層。只輸出 JSON。"
    raw = _call_llm(system, user, max_tokens=1024)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 解析失敗時使用預設角色特質
        return {
            "protagonist_voice": {
                "speech_pattern": "習慣用反問引導觀眾，短句衝擊後留停頓",
                "vocabulary_level": "日常口語為主，偶爾夾入具體數據",
                "sample_phrases": ["說真的", "但問題是", "結果你猜"],
            },
            "core_flaw": "相信表面資訊，忽略深層機制",
            "hidden_motivation": "希望觀眾不要踩同樣的坑",
            "cannot_say_directly": ["我也曾經這樣以為", "這其實讓我很驚訝", "我不確定你會相信"],
        }


def _build_scene_prompt(
    arch_scene: dict,
    dominant_tone: str,
    forbidden_phrases: list[str],
    forbidden_enforced: list[str],
    protagonist_voice: dict,
    used_oral_hooks: list[str] | None = None,
    previous_scenes_raw: list[str] | None = None,
    flags: list[str] | None = None,
) -> str:
    template = _load_prompt("wordsmith_scene.txt")
    protagonist_voice_str = json.dumps(protagonist_voice, ensure_ascii=False, indent=2)

    # 格式化已用口頭禪清單
    if used_oral_hooks:
        hooks_str = "、".join(f"「{h}」" for h in used_oral_hooks)
        hooks_display = f"以下詞彙已在前幕使用，本幕禁止再次出現：{hooks_str}"
    else:
        hooks_display = "（這是第一幕，口頭禪工具庫全部可用）"

    # 格式化前幕內容摘要
    if previous_scenes_raw:
        prev_display = "\n".join(
            f"第{i+1}幕：{raw[:120]}{'...' if len(raw) > 120 else ''}"
            for i, raw in enumerate(previous_scenes_raw)
        )
    else:
        prev_display = "（這是第一幕，尚無前幕內容）"

    prompt = (
        template
        .replace("{{segment_id}}", str(arch_scene.get("segment_id", "")))
        .replace("{{role}}", arch_scene.get("role", ""))
        .replace("{{beat_label}}", arch_scene.get("beat_label", arch_scene.get("role", "")))
        .replace("{{dramatic_function}}", arch_scene.get("dramatic_function", ""))
        .replace("{{emotional_target}}", arch_scene.get("emotional_target", ""))
        .replace("{{intensity}}", str(arch_scene.get("intensity", 0)))
        .replace("{{v_start}}", arch_scene.get("v_start", "neutral"))
        .replace("{{v_end}}", arch_scene.get("v_end", "neutral"))
        .replace("{{transition_to_next}}", str(arch_scene.get("transition_to_next", "null")))
        .replace("{{duration_budget}}", arch_scene.get("duration_budget", ""))
        .replace("{{dominant_tone}}", dominant_tone)
        .replace("{{forbidden_phrases}}", json.dumps(forbidden_phrases, ensure_ascii=False))
        .replace("{{forbidden_enforced}}", json.dumps(forbidden_enforced, ensure_ascii=False))
        .replace("{{protagonist_voice}}", protagonist_voice_str)
        .replace("{{used_oral_hooks}}", hooks_display)
        .replace("{{previous_scenes_raw}}", prev_display)
    )
    if flags:
        prompt += f"\n\n【前次評審 flags，請針對以下問題修正】\n" + "\n".join(f"- {f}" for f in flags)
    return prompt


def _evaluate_naturalness(scene: dict) -> dict:
    """用獨立 LLM 呼叫評審 naturalness_score。"""
    template = _load_prompt("wordsmith_evaluator.txt")
    forbidden_phrases = []
    prompt = (
        template
        .replace("{{voice_script_raw}}", scene.get("voice_script", {}).get("raw", ""))
        .replace("{{emotional_target}}", scene.get("emotional_target", ""))
        .replace("{{intensity}}", str(scene.get("intensity", 0)))
        .replace("{{forbidden_phrases}}", json.dumps(forbidden_phrases, ensure_ascii=False))
        .replace("{{pause_count}}", str(scene.get("language_markers", {}).get("pause_count", 0)))
        .replace("{{duration_est}}", scene.get("duration_est", ""))
    )
    system = "你是短影音文案評審，只輸出 JSON 評分結果。"
    raw = _call_llm(system, prompt, max_tokens=512)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"score": 0, "breakdown": {}, "flags": [f"Evaluator parse error: {raw[:100]}"]}


def _run_dialogue_assassin(scene: dict) -> str:
    """
    Dialogue Assassin 後處理：移除直白情緒陳述，注入亞文本與行為矛盾。
    輸入：通過 naturalness 評審的場景
    輸出：修改後的 annotated 文案（替換原本的 voice_script.annotated）
    """
    template = _load_prompt("dialogue_assassin.txt")
    protagonist_voice = scene.get("_protagonist_voice", {})
    protagonist_voice_str = json.dumps(protagonist_voice, ensure_ascii=False, indent=2)

    user = (
        template
        .replace("{{segment_id}}", str(scene.get("segment_id", "")))
        .replace("{{role}}", scene.get("role", ""))
        .replace("{{emotional_target}}", scene.get("emotional_target", ""))
        .replace("{{intensity}}", str(scene.get("intensity", 0)))
        .replace("{{protagonist_voice}}", protagonist_voice_str)
        .replace("{{annotated_script}}", scene.get("voice_script", {}).get("annotated", ""))
    )
    system = "你是對白後處理專家，只輸出 JSON 結果。"
    raw = _call_llm(system, user, max_tokens=1024)
    try:
        result = json.loads(raw)
        return result.get("refined_annotated", scene.get("voice_script", {}).get("annotated", ""))
    except json.JSONDecodeError:
        # 解析失敗時保持原始文案
        return scene.get("voice_script", {}).get("annotated", "")


def _run_single_scene(
    arch_scene: dict,
    dominant_tone: str,
    forbidden_phrases: list[str],
    forbidden_enforced: list[str],
    protagonist_voice: dict,
    used_oral_hooks: list[str] | None = None,
    previous_scenes_raw: list[str] | None = None,
) -> dict:
    """對單一幕執行 Wordsmith + naturalness 評審 + Dialogue Assassin，帶重試。"""
    system_prompt = _load_prompt("wordsmith_system.txt")
    flags: list[str] = []
    last_scene = {}

    for attempt in range(1, MAX_RETRIES + 1):
        user_prompt = _build_scene_prompt(
            arch_scene, dominant_tone, forbidden_phrases, forbidden_enforced,
            protagonist_voice,
            used_oral_hooks=used_oral_hooks,
            previous_scenes_raw=previous_scenes_raw,
            flags=flags if attempt > 1 else None,
        )
        raw_response = _call_llm(system_prompt, user_prompt)

        try:
            scene = json.loads(raw_response)
        except json.JSONDecodeError as e:
            flags = [f"JSON parse error: {e}"]
            last_scene = {"raw_response": raw_response}
            continue

        # 暫存 protagonist_voice 供 Dialogue Assassin 使用（不寫入最終輸出）
        scene["_protagonist_voice"] = protagonist_voice

        eval_result = _evaluate_naturalness(scene)
        score = eval_result.get("score", 0)
        scene["naturalness_score"] = score

        if score >= NATURALNESS_THRESHOLD:
            # 通過 naturalness 評審後，執行 Dialogue Assassin 後處理
            refined_annotated = _run_dialogue_assassin(scene)
            scene["voice_script"]["annotated"] = refined_annotated
            # 清除暫存欄位
            scene.pop("_protagonist_voice", None)
            return scene

        flags = eval_result.get("flags", [f"Score {score} < {NATURALNESS_THRESHOLD}"])
        last_scene = scene

    seg_id = arch_scene.get("segment_id", "?")
    raise PipelineError(
        f"wordsmith_scene_{seg_id}",
        f"naturalness_score never reached {NATURALNESS_THRESHOLD} after {MAX_RETRIES} attempts",
        last_scene,
    )


def run_wordsmith(
    architect_contract: dict,
    premise_contract: dict,
    framework_dna: dict | None = None,
) -> dict:
    """
    執行 Wordsmith Agent（逐幕呼叫）。
    回傳完整的 Wordsmith Contract，通過 Validator。

    Args:
        architect_contract: Architect Agent 的輸出 Contract
        premise_contract: Premise Agent 的輸出 Contract
        framework_dna: Framework DNA（用於生成角色語音特質）
    """
    arch_scenes = architect_contract.get("scenes", [])
    dominant_tone = premise_contract.get("story_constraints", {}).get("tone", "")
    forbidden_phrases = architect_contract.get("forbidden_enforced", [])
    forbidden_enforced = architect_contract.get("forbidden_enforced", [])

    # Character Architect：為整個故事生成主角語音特質
    character_profile = _generate_character_profile(premise_contract, framework_dna)
    protagonist_voice = character_profile.get("protagonist_voice", {})

    completed_scenes = []
    used_oral_hooks: list[str] = []     # 跨幕追蹤：已用過的口頭禪
    previous_scenes_raw: list[str] = [] # 跨幕追蹤：前幕的原始文案

    for arch_scene in arch_scenes:
        scene = _run_single_scene(
            arch_scene, dominant_tone, forbidden_phrases, forbidden_enforced,
            protagonist_voice,
            used_oral_hooks=used_oral_hooks,
            previous_scenes_raw=previous_scenes_raw,
        )
        completed_scenes.append(scene)

        # 更新跨幕狀態，供下一幕使用
        new_hooks = scene.get("language_markers", {}).get("oral_hooks", [])
        for hook in new_hooks:
            if hook and hook not in used_oral_hooks:
                used_oral_hooks.append(hook)
        raw_script = scene.get("voice_script", {}).get("raw", "")
        if raw_script:
            previous_scenes_raw.append(raw_script)

    contract = {
        "wordsmith_id": f"ws_{uuid.uuid4().hex[:8]}",
        "architect_id": architect_contract.get("architect_id", ""),
        "character_profile": character_profile,
        "scenes": completed_scenes,
        "global_language_profile": {
            "dominant_tone": dominant_tone,
            "forbidden_phrases": forbidden_phrases,
            "signature_transitions": ["其實", "但問題是", "結果你猜"],
        },
    }

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            validate_wordsmith(contract, architect_contract)
            return contract
        except ValidationError as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                continue

    raise PipelineError("wordsmith", last_error, contract)
