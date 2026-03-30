"""
AutoReel-Flow — CLI 端到端 Pipeline 入口
用法：
  python main.py                  # MVP-1：劇本設計層
  python main.py --phase 2        # MVP-2：劇本 + 音軌生成
  python main.py --topic sleep    # 指定測試主題
"""

import argparse
import json
import uuid
from pathlib import Path

from dramaturgy.premise import run_premise, PipelineError
from dramaturgy.architect import run_architect
from dramaturgy.wordsmith import run_wordsmith
from dramaturgy.director import run_director

OUTPUT_DIR = Path("outputs/contracts")

# MVP-1 固定測試資料（睡眠與生產力主題）
SLEEP_TEST_INPUT = {
    "title": "你以為多睡覺就能恢復體力？科學說你錯了",
    "summary": "最新研究發現，睡眠時間超過 9 小時反而會增加疲勞感與認知障礙風險。"
               "許多人誤以為補眠能解決疲憊，卻不知道睡眠品質比時間更關鍵。"
               "慢波睡眠與 REM 睡眠的比例，才是決定隔天狀態的真正因素。",
    "keywords": ["睡眠", "生產力", "疲勞", "科學研究", "健康"],
    "engagement_score": 87,
}

TOPICS = {
    "sleep": SLEEP_TEST_INPUT,
}


def run_dramaturgy_pipeline(raw_content: dict, project_id: str) -> dict:
    """執行劇本設計 Pipeline（MVP-1），回傳包含所有 contracts 的狀態字典。"""
    state = {
        "project_id": project_id,
        "status": "running",
        "current_stage": "premise",
        "retry_count": {},
        "contracts": {},
        "errors": [],
    }

    print(f"\n[{project_id}] 啟動 Pipeline...")
    print("=" * 60)

    # Stage 1: Premise
    print("\n▶ Stage 1/4: The Premise Agent")
    try:
        premise = run_premise(raw_content)
        state["contracts"]["premise"] = premise
        print(f"  ✓ Premise 完成 | conflict_type: {premise['core_tension']['conflict_type']}")
        print(f"    force_a: {premise['core_tension']['force_a']}")
        print(f"    force_b: {premise['core_tension']['force_b']}")
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        print(f"  ✗ Premise 失敗: {e.reason}")
        return state

    # Stage 2: Architect
    print("\n▶ Stage 2/4: The Architect Agent")
    try:
        architect = run_architect(premise)
        state["contracts"]["architect"] = architect
        scenes_info = [(s["role"], s["intensity"]) for s in architect["scenes"]]
        print(f"  ✓ Architect 完成 | arc: {architect['story_arc']} | 共 {len(architect['scenes'])} 幕")
        for role, intensity in scenes_info:
            bar = "█" * int(intensity * 20)
            print(f"    {role:<15} intensity={intensity:.2f}  {bar}")
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        print(f"  ✗ Architect 失敗: {e.reason}")
        return state

    # Stage 3: Wordsmith
    print("\n▶ Stage 3/4: The Wordsmith Agent（逐幕處理）")
    try:
        wordsmith = run_wordsmith(architect, premise)
        state["contracts"]["wordsmith"] = wordsmith
        for scene in wordsmith["scenes"]:
            score = scene.get("naturalness_score", "N/A")
            score_icon = "✓" if isinstance(score, int) and score >= 70 else "⚠"
            print(f"  {score_icon} Scene {scene['segment_id']} [{scene['role']}] "
                  f"naturalness={score} | {scene['duration_est']}")
        if wordsmith["scenes"]:
            raw = wordsmith["scenes"][0]["voice_script"]["raw"]
            print(f"\n  文案預覽（Scene 1）：")
            print(f"  「{raw[:100]}{'...' if len(raw) > 100 else ''}」")
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        print(f"  ✗ Wordsmith 失敗: {e.reason}")
        return state

    # Stage 4: Director
    print("\n▶ Stage 4/4: The Director Agent")
    try:
        director = run_director(wordsmith, architect, premise, project_id)
        state["contracts"]["director"] = director
        print(f"  ✓ Director 完成 | total: {director['total_duration_est']}")
        for scene in director["scenes"]:
            print(f"    Scene {scene['segment_id']}: {scene['visual']['shot_type']} | "
                  f"{scene['visual']['color_grade']} | {scene['duration_est']}")
    except PipelineError as e:
        state["status"] = "failed"
        state["errors"].append({"stage": e.stage, "reason": e.reason})
        print(f"  ✗ Director 失敗: {e.reason}")
        return state

    state["status"] = "completed"
    return state


def save_contracts(state: dict) -> None:
    project_id = state["project_id"]
    out_dir = OUTPUT_DIR / project_id
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, contract in state["contracts"].items():
        path = out_dir / f"{name}_contract.json"
        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  💾 {path}")

    state_path = out_dir / "pipeline_state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  💾 {state_path}")


def run_audio_stage(director_contract: dict, project_id: str) -> dict | None:
    """執行 MVP-2 音軌生成階段。"""
    from execution.audio_pipeline import run_audio_pipeline

    print("\n" + "=" * 60)
    print("🎵 MVP-2: Audio Pipeline")
    print("=" * 60)

    try:
        audio_result = run_audio_pipeline(director_contract, project_id)
        print("\n✅ 音軌生成完成！")

        # 顯示 duration comparison
        print("\n時長比較（估算 vs 實際）：")
        print(f"  {'Scene':<8} {'Role':<15} {'估算':>8} {'實際':>8} {'誤差':>8} {'狀態'}")
        print("  " + "-" * 58)
        for row in audio_result.get("duration_comparison", []):
            status = "✓" if row["within_threshold"] else "⚠"
            print(f"  {row['segment_id']:<8} {row['role']:<15} "
                  f"{row['estimated_sec']:>7.1f}s {row['actual_sec']:>7.1f}s "
                  f"{row['deviation_sec']:>7.2f}s {status}")

        return audio_result
    except Exception as e:
        print(f"\n❌ 音軌生成失敗：{e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="AutoReel-Flow Pipeline")
    parser.add_argument(
        "--topic",
        default="sleep",
        choices=list(TOPICS.keys()),
        help="測試主題（預設：sleep）",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="專案 ID（預設自動產生）",
    )
    parser.add_argument(
        "--phase",
        type=int,
        default=1,
        choices=[1, 2],
        help="執行階段：1=劇本設計（預設），2=劇本+音軌生成",
    )
    args = parser.parse_args()

    project_id = args.project_id or f"proj_{uuid.uuid4().hex[:8]}"
    raw_content = TOPICS[args.topic]

    # ── Phase 1：劇本設計 ─────────────────────────────────────────────────────
    state = run_dramaturgy_pipeline(raw_content, project_id)

    print("\n" + "=" * 60)
    if state["status"] != "completed":
        print(f"❌ Pipeline 失敗於 stage: {state['errors'][-1]['stage'] if state['errors'] else 'unknown'}")
        for err in state["errors"]:
            print(f"   {err['stage']}: {err['reason']}")
        print("=" * 60)
        return

    print(f"✅ 劇本設計完成！project_id: {project_id}")
    print("\n儲存 Contracts...")
    save_contracts(state)
    print("=" * 60)

    # ── Phase 2：音軌生成 ─────────────────────────────────────────────────────
    if args.phase >= 2:
        director_contract = state["contracts"]["director"]
        audio_result = run_audio_stage(director_contract, project_id)
        if audio_result:
            print(f"\n  音檔：{audio_result['combined_audio']}")
            print(f"  字幕：{audio_result['subtitle_srt']}")
        print("=" * 60)


if __name__ == "__main__":
    main()
