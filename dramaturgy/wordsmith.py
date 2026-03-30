"""
The Wordsmith Agent — 修辭師
將場景骨架轉化為具人類語感的文案與 TTS 執行參數。
逐幕呼叫，每幕獨立評審（naturalness_score）。
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


def _build_scene_prompt(
    arch_scene: dict,
    dominant_tone: str,
    forbidden_phrases: list[str],
    forbidden_enforced: list[str],
    flags: list[str] | None = None,
) -> str:
    template = _load_prompt("wordsmith_scene.txt")
    prompt = (
        template
        .replace("{{segment_id}}", str(arch_scene.get("segment_id", "")))
        .replace("{{role}}", arch_scene.get("role", ""))
        .replace("{{dramatic_function}}", arch_scene.get("dramatic_function", ""))
        .replace("{{emotional_target}}", arch_scene.get("emotional_target", ""))
        .replace("{{intensity}}", str(arch_scene.get("intensity", 0)))
        .replace("{{transition_to_next}}", str(arch_scene.get("transition_to_next", "null")))
        .replace("{{duration_budget}}", arch_scene.get("duration_budget", ""))
        .replace("{{dominant_tone}}", dominant_tone)
        .replace("{{forbidden_phrases}}", json.dumps(forbidden_phrases, ensure_ascii=False))
        .replace("{{forbidden_enforced}}", json.dumps(forbidden_enforced, ensure_ascii=False))
    )
    if flags:
        prompt += f"\n\n【前次評審 flags，請針對以下問題修正】\n" + "\n".join(f"- {f}" for f in flags)
    return prompt


def _evaluate_naturalness(scene: dict) -> dict:
    """用獨立 LLM 呼叫評審 naturalness_score。"""
    template = _load_prompt("wordsmith_evaluator.txt")
    forbidden_phrases = []  # 評審時從 scene 本身取不到，用空陣列
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


def _run_single_scene(
    arch_scene: dict,
    dominant_tone: str,
    forbidden_phrases: list[str],
    forbidden_enforced: list[str],
) -> dict:
    """對單一幕執行 Wordsmith + naturalness 評審，帶重試。"""
    system_prompt = _load_prompt("wordsmith_system.txt")
    flags: list[str] = []
    last_scene = {}

    for attempt in range(1, MAX_RETRIES + 1):
        user_prompt = _build_scene_prompt(
            arch_scene, dominant_tone, forbidden_phrases, forbidden_enforced,
            flags=flags if attempt > 1 else None,
        )
        raw_response = _call_llm(system_prompt, user_prompt)

        try:
            scene = json.loads(raw_response)
        except json.JSONDecodeError as e:
            flags = [f"JSON parse error: {e}"]
            last_scene = {"raw_response": raw_response}
            continue

        eval_result = _evaluate_naturalness(scene)
        score = eval_result.get("score", 0)
        scene["naturalness_score"] = score

        if score >= NATURALNESS_THRESHOLD:
            return scene

        flags = eval_result.get("flags", [f"Score {score} < {NATURALNESS_THRESHOLD}"])
        last_scene = scene

    seg_id = arch_scene.get("segment_id", "?")
    raise PipelineError(
        f"wordsmith_scene_{seg_id}",
        f"naturalness_score never reached {NATURALNESS_THRESHOLD} after {MAX_RETRIES} attempts",
        last_scene,
    )


def run_wordsmith(architect_contract: dict, premise_contract: dict) -> dict:
    """
    執行 Wordsmith Agent（逐幕呼叫）。
    回傳完整的 Wordsmith Contract，通過 Validator。
    """
    arch_scenes = architect_contract.get("scenes", [])
    dominant_tone = premise_contract.get("story_constraints", {}).get("tone", "")
    forbidden_phrases = architect_contract.get("forbidden_enforced", [])
    forbidden_enforced = architect_contract.get("forbidden_enforced", [])

    completed_scenes = []
    for arch_scene in arch_scenes:
        scene = _run_single_scene(
            arch_scene, dominant_tone, forbidden_phrases, forbidden_enforced
        )
        completed_scenes.append(scene)

    contract = {
        "wordsmith_id": f"ws_{uuid.uuid4().hex[:8]}",
        "architect_id": architect_contract.get("architect_id", ""),
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
