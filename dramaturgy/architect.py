"""
The Architect Agent — 結構師
根據 Premise Contract + Framework DNA 推導敘事骨架與情緒曲線。
支援可變幕數（4–8）與麥基場景電荷（v_start / v_end / scene_energy）。
"""

import json
import uuid
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL, MAX_RETRIES
from dramaturgy.validator import validate_architect, ValidationError
from dramaturgy.premise import PipelineError


_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _call_llm(system: str, user: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def _build_user_prompt(premise_contract: dict, framework_dna: dict | None) -> str:
    template = _load_prompt("architect_user.txt")
    dna = framework_dna or {}
    scene_count = dna.get("scene_count", 4)
    return (
        template
        .replace("{{premise_contract}}", json.dumps(premise_contract, ensure_ascii=False, indent=2))
        .replace("{{framework_dna}}", json.dumps(dna, ensure_ascii=False, indent=2))
        .replace("{{scene_count}}", str(scene_count))
    )


def run_architect(premise_contract: dict, framework_dna: dict | None = None) -> dict:
    """
    執行 Architect Agent，回傳通過 Validator 的 Contract。
    最多重試 MAX_RETRIES 次，超過則拋出 PipelineError。

    Args:
        premise_contract: Premise Agent 的輸出 Contract
        framework_dna: Strategy Synthesizer 的 Framework DNA（可選，若無則使用預設 4 幕結構）
    """
    system_prompt = _load_prompt("architect_system.txt")
    last_output = {}
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        user_prompt = _build_user_prompt(premise_contract, framework_dna)
        if attempt > 1 and last_error:
            user_prompt += (
                f"\n\n【前次驗證失敗，請修正以下問題】\n{last_error}\n"
                f"請特別注意：\n"
                f"1. intensity 分佈必須有明顯起伏（至少一幕 >= 0.85）\n"
                f"2. 每個場景的 scene_energy 必須 > 0（v_start ≠ v_end）\n"
                f"3. 幕數必須是 {(framework_dna or {}).get('scene_count', 4)} 幕"
            )

        raw_response = _call_llm(system_prompt, user_prompt)

        try:
            contract = json.loads(raw_response)
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            last_output = {"raw_response": raw_response}
            continue

        if not contract.get("architect_id"):
            contract["architect_id"] = f"arch_{uuid.uuid4().hex[:8]}"

        # 繼承 Framework DNA 資訊
        if framework_dna:
            if not contract.get("dna_id"):
                contract["dna_id"] = framework_dna.get("dna_id", "")
            if not contract.get("primary_framework"):
                contract["primary_framework"] = framework_dna.get("primary_framework", "three_act")

        try:
            validate_architect(contract, premise_contract)
            return contract
        except ValidationError as e:
            last_error = str(e)
            last_output = contract

    raise PipelineError("architect", last_error, last_output)
