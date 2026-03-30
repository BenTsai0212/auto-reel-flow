"""
Contract Validator — 每個 Agent 產出後執行的強制關卡。
MVP-1 版本：跳過 LLM 語意判斷，只做 Python 可執行的規則檢查。
"""

import re
from typing import Any


class ValidationError(Exception):
    def __init__(self, stage: str, violations: list[str]):
        self.stage = stage
        self.violations = violations
        super().__init__(f"[{stage}] Validation failed: {'; '.join(violations)}")


def _parse_seconds(duration_str: str) -> float:
    """將 '12s' 或 '1.5s' 轉為浮點秒數。"""
    match = re.match(r"^(\d+(?:\.\d+)?)s?$", str(duration_str).strip())
    if not match:
        raise ValueError(f"Cannot parse duration: {duration_str!r}")
    return float(match.group(1))


def validate_premise(contract: dict[str, Any]) -> None:
    """
    驗證 Premise Contract。
    規則：
    - 所有必填欄位存在且非空
    - audience.pain_point 長度 > 8 字
    - story_constraints.forbidden 至少兩項
    """
    violations = []

    core = contract.get("core_tension", {})
    if not core.get("force_a"):
        violations.append("core_tension.force_a is empty")
    if not core.get("force_b"):
        violations.append("core_tension.force_b is empty")
    if core.get("force_a") and core.get("force_b"):
        if core["force_a"].strip() == core["force_b"].strip():
            violations.append("core_tension.force_a and force_b are identical")

    audience = contract.get("audience", {})
    pain_point = audience.get("pain_point", "")
    if len(pain_point) <= 8:
        violations.append(f"audience.pain_point too short ({len(pain_point)} chars, need > 8)")

    forbidden = contract.get("story_constraints", {}).get("forbidden", [])
    if len(forbidden) < 2:
        violations.append(f"story_constraints.forbidden needs >= 2 items (got {len(forbidden)})")

    for field in ["premise_id", "generated_at"]:
        if not contract.get(field):
            violations.append(f"Missing required field: {field}")

    if violations:
        raise ValidationError("premise", violations)


def validate_architect(contract: dict[str, Any], premise_contract: dict[str, Any]) -> None:
    """
    驗證 Architect Contract。
    規則：
    - Hook intensity 在 0.5–0.7
    - 至少一幕 intensity >= 0.85
    - Reward intensity < 全片最高點
    - 總時長 45–90 秒
    - forbidden_enforced 必須包含 premise 的所有 forbidden
    """
    violations = []
    scenes = contract.get("scenes", [])

    if not scenes:
        violations.append("scenes array is empty")
        raise ValidationError("architect", violations)

    intensities = [s.get("intensity", 0) for s in scenes]
    hook = scenes[0]

    hook_intensity = hook.get("intensity", 0)
    if not (0.5 <= hook_intensity <= 0.7):
        violations.append(
            f"Hook intensity must be 0.5–0.7 (got {hook_intensity})"
        )

    max_intensity = max(intensities)
    if max_intensity < 0.85:
        violations.append(
            f"At least one scene must have intensity >= 0.85 (max is {max_intensity})"
        )

    reward_scenes = [s for s in scenes if s.get("role") == "Reward"]
    if reward_scenes:
        reward_intensity = reward_scenes[-1].get("intensity", 0)
        if reward_intensity >= max_intensity:
            violations.append(
                f"Reward intensity ({reward_intensity}) must be < max intensity ({max_intensity})"
            )

    try:
        total_seconds = sum(
            _parse_seconds(s.get("duration_budget", "0s")) for s in scenes
        )
        if not (45 <= total_seconds <= 90):
            violations.append(
                f"Total duration must be 45–90s (got {total_seconds}s)"
            )
    except ValueError as e:
        violations.append(f"Duration parse error: {e}")

    premise_forbidden = set(premise_contract.get("story_constraints", {}).get("forbidden", []))
    enforced = set(contract.get("forbidden_enforced", []))
    missing = premise_forbidden - enforced
    if missing:
        violations.append(f"forbidden_enforced missing items from premise: {missing}")

    if violations:
        raise ValidationError("architect", violations)


def validate_wordsmith(
    contract: dict[str, Any], architect_contract: dict[str, Any]
) -> None:
    """
    驗證 Wordsmith Contract。
    規則（逐幕）：
    - duration_est 在 architect duration_budget ±20%
    - intensity 誤差 ≤ 0.05
    - intensity > 0.7 時 pause_count >= 3
    - forbidden_phrases 未出現在 raw script
    """
    violations = []
    ws_scenes = contract.get("scenes", [])
    arch_scenes = architect_contract.get("scenes", [])
    forbidden_phrases = contract.get("global_language_profile", {}).get("forbidden_phrases", [])

    if len(ws_scenes) != len(arch_scenes):
        violations.append(
            f"Scene count mismatch: wordsmith={len(ws_scenes)}, architect={len(arch_scenes)}"
        )

    for i, ws_scene in enumerate(ws_scenes):
        seg_id = ws_scene.get("segment_id", i + 1)

        if i < len(arch_scenes):
            arch_scene = arch_scenes[i]
            try:
                arch_budget = _parse_seconds(arch_scene.get("duration_budget", "0s"))
                ws_est = _parse_seconds(ws_scene.get("duration_est", "0s"))
                if arch_budget > 0:
                    ratio = abs(ws_est - arch_budget) / arch_budget
                    if ratio > 0.2:
                        violations.append(
                            f"Scene {seg_id}: duration_est {ws_est}s deviates >20% from budget {arch_budget}s"
                        )
            except ValueError as e:
                violations.append(f"Scene {seg_id}: duration parse error: {e}")

            arch_intensity = arch_scene.get("intensity", 0)
            ws_intensity = ws_scene.get("intensity", 0)
            if abs(ws_intensity - arch_intensity) > 0.05:
                violations.append(
                    f"Scene {seg_id}: intensity {ws_intensity} deviates >0.05 from architect {arch_intensity}"
                )

        ws_intensity = ws_scene.get("intensity", 0)
        pause_count = ws_scene.get("language_markers", {}).get("pause_count", 0)
        if ws_intensity > 0.7 and pause_count < 3:
            violations.append(
                f"Scene {seg_id}: intensity {ws_intensity} > 0.7 requires pause_count >= 3 (got {pause_count})"
            )

        raw_script = ws_scene.get("voice_script", {}).get("raw", "")
        for phrase in forbidden_phrases:
            if phrase and phrase in raw_script:
                violations.append(f"Scene {seg_id}: forbidden phrase found in raw script: '{phrase}'")

    if violations:
        raise ValidationError("wordsmith", violations)


def validate_director(
    contract: dict[str, Any],
    wordsmith_contract: dict[str, Any],
    architect_contract: dict[str, Any],
) -> None:
    """
    驗證 Director Contract。
    規則：
    - scene 數量與 wordsmith / architect 一致
    - 各幕 duration_est 與 wordsmith 誤差 < 0.1s
    - total_duration_est 與各幕加總誤差 < 0.5s
    - color_grade_arc 和 bgm_arc 長度等於 scenes 數量
    - 各幕 visual.prompt 包含 shot_type 關鍵字
    """
    violations = []
    dir_scenes = contract.get("scenes", [])
    ws_scenes = wordsmith_contract.get("scenes", [])
    arch_scenes = architect_contract.get("scenes", [])

    if len(dir_scenes) != len(ws_scenes):
        violations.append(
            f"Scene count mismatch: director={len(dir_scenes)}, wordsmith={len(ws_scenes)}"
        )
    if len(dir_scenes) != len(arch_scenes):
        violations.append(
            f"Scene count mismatch: director={len(dir_scenes)}, architect={len(arch_scenes)}"
        )

    shot_type_keywords = {
        "extreme_close_up": "close-up",
        "medium_shot": "medium",
        "wide_shot": "wide",
        "dynamic_cut": "dynamic",
    }

    total_dir = 0.0
    for i, dir_scene in enumerate(dir_scenes):
        seg_id = dir_scene.get("segment_id", i + 1)

        try:
            dir_dur = _parse_seconds(dir_scene.get("duration_est", "0s"))
            total_dir += dir_dur

            if i < len(ws_scenes):
                ws_dur = _parse_seconds(ws_scenes[i].get("duration_est", "0s"))
                if abs(dir_dur - ws_dur) >= 0.1:
                    violations.append(
                        f"Scene {seg_id}: duration_est {dir_dur}s deviates >= 0.1s from wordsmith {ws_dur}s"
                    )
        except ValueError as e:
            violations.append(f"Scene {seg_id}: duration parse error: {e}")

        shot_type = dir_scene.get("visual", {}).get("shot_type", "")
        prompt = dir_scene.get("visual", {}).get("prompt", "").lower()
        if shot_type in shot_type_keywords:
            keyword = shot_type_keywords[shot_type]
            if keyword not in prompt:
                violations.append(
                    f"Scene {seg_id}: visual.prompt must contain '{keyword}' for shot_type '{shot_type}'"
                )

    try:
        total_est = _parse_seconds(contract.get("total_duration_est", "0s"))
        if abs(total_dir - total_est) >= 0.5:
            violations.append(
                f"total_duration_est {total_est}s deviates >= 0.5s from scenes sum {total_dir:.1f}s"
            )
    except ValueError as e:
        violations.append(f"total_duration_est parse error: {e}")

    global_av = contract.get("global_av_profile", {})
    color_grade_arc = global_av.get("color_grade_arc", [])
    bgm_arc = global_av.get("bgm_arc", [])
    if len(color_grade_arc) != len(dir_scenes):
        violations.append(
            f"color_grade_arc length ({len(color_grade_arc)}) != scenes count ({len(dir_scenes)})"
        )
    if len(bgm_arc) != len(dir_scenes):
        violations.append(
            f"bgm_arc length ({len(bgm_arc)}) != scenes count ({len(dir_scenes)})"
        )

    if violations:
        raise ValidationError("director", violations)
