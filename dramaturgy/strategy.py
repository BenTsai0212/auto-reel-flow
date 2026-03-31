"""
Strategy Intelligence Layer — 策略智能層
ThemeAnalyzer + StrategySynthesizer

在劇本生成前，分析主題特性並推薦最佳框架混合配方（Framework DNA）。
這是 DRAMATIX 架構中的「敘事診斷師」，解放使用者不必自行選擇編劇框架。
"""

import json
import uuid
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL
from dramaturgy.premise import PipelineError


_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _call_llm(system: str, user: str, max_tokens: int = 1024) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def run_theme_analyzer(raw_content: dict) -> dict:
    """
    分析輸入主題，輸出多維度向量 ThemeDimension。

    Args:
        raw_content: 包含 title, summary, keywords, engagement_score 的字典

    Returns:
        ThemeDimension dict：medium, tone, conflict_axis, myth_resonance,
                            knowledge_transfer, pace_requirement
    """
    system = _load_prompt("theme_analyzer_system.txt")
    user_template = _load_prompt("theme_analyzer_user.txt")
    keywords = ", ".join(raw_content.get("keywords", []))
    user = (
        user_template
        .replace("{{title}}", raw_content.get("title", ""))
        .replace("{{summary}}", raw_content.get("summary", ""))
        .replace("{{keywords}}", keywords)
        .replace("{{engagement_score}}", str(raw_content.get("engagement_score", "")))
    )

    raw = _call_llm(system, user)
    try:
        result = json.loads(raw)
        # 確保必要欄位存在
        required = ["medium", "tone", "conflict_axis", "myth_resonance",
                    "knowledge_transfer", "pace_requirement"]
        for field in required:
            if field not in result:
                raise PipelineError(
                    "theme_analyzer",
                    f"Missing required field: {field}",
                    {"raw": raw}
                )
        return result
    except json.JSONDecodeError as e:
        raise PipelineError("theme_analyzer", f"JSON parse error: {e}", {"raw": raw})


def run_strategy_synthesizer(theme_dimension: dict) -> dict:
    """
    基於 ThemeDimension 推導 Framework DNA 配方，輸出導演簡報。

    Args:
        theme_dimension: ThemeDimension 向量

    Returns:
        FrameworkDNA dict：primary_framework, weights, scene_count,
                          beat_structure, story_shape, emotional_arc, director_brief
    """
    system = _load_prompt("strategy_synthesizer_system.txt")
    user_template = _load_prompt("strategy_synthesizer_user.txt")
    user = user_template.replace(
        "{{theme_dimension}}",
        json.dumps(theme_dimension, ensure_ascii=False, indent=2)
    )

    raw = _call_llm(system, user, max_tokens=2048)
    try:
        dna = json.loads(raw)
        if not dna.get("dna_id"):
            dna["dna_id"] = f"dna_{uuid.uuid4().hex[:8]}"
        # 驗證 scene_count 在合理範圍
        scene_count = dna.get("scene_count", 4)
        if not (4 <= scene_count <= 8):
            dna["scene_count"] = max(4, min(8, scene_count))
        return dna
    except json.JSONDecodeError as e:
        raise PipelineError("strategy_synthesizer", f"JSON parse error: {e}", {"raw": raw})
