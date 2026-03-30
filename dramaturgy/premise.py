"""
The Premise Agent — 前提定義師
從 Raw Content 提煉核心張力，定義「這個故事值得被說的理由」。
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL, MAX_RETRIES
from dramaturgy.validator import validate_premise, ValidationError


class PipelineError(Exception):
    def __init__(self, stage: str, reason: str, last_output: dict):
        self.stage = stage
        self.reason = reason
        self.last_output = last_output
        super().__init__(f"[{stage}] PipelineError: {reason}")


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


def _build_user_prompt(raw_content: dict) -> str:
    template = _load_prompt("premise_user.txt")
    keywords = ", ".join(raw_content.get("keywords", []))
    return (
        template
        .replace("{{title}}", raw_content.get("title", ""))
        .replace("{{summary}}", raw_content.get("summary", ""))
        .replace("{{keywords}}", keywords)
        .replace("{{engagement_score}}", str(raw_content.get("engagement_score", "")))
    )


def run_premise(raw_content: dict) -> dict:
    """
    執行 Premise Agent，回傳通過 Validator 的 Contract。
    最多重試 MAX_RETRIES 次，超過則拋出 PipelineError。
    """
    system_prompt = _load_prompt("premise_system.txt")
    last_output = {}
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        user_prompt = _build_user_prompt(raw_content)
        if attempt > 1 and last_error:
            user_prompt += f"\n\n【前次驗證失敗，請修正以下問題】\n{last_error}"

        raw_response = _call_llm(system_prompt, user_prompt)

        try:
            contract = json.loads(raw_response)
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            last_output = {"raw_response": raw_response}
            continue

        if not contract.get("premise_id"):
            contract["premise_id"] = f"premise_{uuid.uuid4().hex[:8]}"
        if not contract.get("generated_at"):
            contract["generated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            validate_premise(contract)
            return contract
        except ValidationError as e:
            last_error = str(e)
            last_output = contract

    raise PipelineError("premise", last_error, last_output)
