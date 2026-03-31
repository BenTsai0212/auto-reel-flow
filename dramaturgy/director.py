"""
The Director Agent — 導演
將文案與場景參數轉化為完整視聽執行指令，輸出 Final JSON Contract。
"""

import json
import re
import uuid
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL, MAX_RETRIES
from dramaturgy.validator import validate_director, ValidationError
from dramaturgy.premise import PipelineError


_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _call_llm(system: str, user: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def _build_user_prompt(
    wordsmith_contract: dict,
    architect_contract: dict,
    dominant_tone: str,
    project_id: str,
    last_error: str = "",
) -> str:
    template = _load_prompt("director_scene.txt")
    prompt = (
        template
        .replace("{{wordsmith_contract}}", json.dumps(wordsmith_contract, ensure_ascii=False, indent=2))
        .replace("{{architect_contract}}", json.dumps(architect_contract, ensure_ascii=False, indent=2))
        .replace("{{dominant_tone}}", dominant_tone)
        .replace("{{project_id}}", project_id)
    )
    if last_error:
        prompt += f"\n\n【前次驗證失敗，請修正以下問題】\n{last_error}"
    return prompt


def run_director(
    wordsmith_contract: dict,
    architect_contract: dict,
    premise_contract: dict,
    project_id: str,
) -> dict:
    """
    執行 Director Agent，回傳通過 Validator 的 Final Contract。
    最多重試 MAX_RETRIES 次，超過則拋出 PipelineError。
    """
    system_prompt = _load_prompt("director_system.txt")
    dominant_tone = premise_contract.get("story_constraints", {}).get("tone", "")
    last_output = {}
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        user_prompt = _build_user_prompt(
            wordsmith_contract, architect_contract, dominant_tone, project_id,
            last_error=last_error if attempt > 1 else "",
        )
        raw_response = _call_llm(system_prompt, user_prompt)

        try:
            contract = json.loads(raw_response)
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            last_output = {"raw_response": raw_response}
            continue

        if not contract.get("director_id"):
            contract["director_id"] = f"dir_{uuid.uuid4().hex[:8]}"

        # 自動修正 total_duration_est：以各幕加總為準，避免 LLM 手算不一致導致驗證失敗
        try:
            scenes_dur = sum(
                float(re.sub(r"[^\d.]", "", s.get("duration_est", "0s")))
                for s in contract.get("scenes", [])
            )
            contract["total_duration_est"] = f"{scenes_dur:.1f}s"
        except Exception:
            pass

        try:
            validate_director(contract, wordsmith_contract, architect_contract)
            return contract
        except ValidationError as e:
            last_error = str(e)
            last_output = contract

    raise PipelineError("director", last_error, last_output)
