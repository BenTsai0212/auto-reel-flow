"""
The Architect Agent — 結構師
根據 Premise Contract 推導敘事骨架與情緒曲線。
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


def _build_user_prompt(premise_contract: dict) -> str:
    template = _load_prompt("architect_user.txt")
    return template.replace("{{premise_contract}}", json.dumps(premise_contract, ensure_ascii=False, indent=2))


def run_architect(premise_contract: dict) -> dict:
    """
    執行 Architect Agent，回傳通過 Validator 的 Contract。
    最多重試 MAX_RETRIES 次，超過則拋出 PipelineError。
    """
    system_prompt = _load_prompt("architect_system.txt")
    last_output = {}
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        user_prompt = _build_user_prompt(premise_contract)
        if attempt > 1 and last_error:
            user_prompt += f"\n\n【前次驗證失敗，請修正以下問題】\n{last_error}\n請特別注意調整 intensity 分佈，確保有明顯情緒起伏。"

        raw_response = _call_llm(system_prompt, user_prompt)

        try:
            contract = json.loads(raw_response)
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            last_output = {"raw_response": raw_response}
            continue

        if not contract.get("architect_id"):
            contract["architect_id"] = f"arch_{uuid.uuid4().hex[:8]}"

        try:
            validate_architect(contract, premise_contract)
            return contract
        except ValidationError as e:
            last_error = str(e)
            last_output = contract

    raise PipelineError("architect", last_error, last_output)
