import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path


def _format_conversation(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for m in messages:
        speaker = m.get("speaker", "unknown")
        content = m.get("content", "")
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def _score_response(*, response_text: str) -> dict[str, float]:
    """Heuristic scoring for policy adherence.

    This is intentionally simple and cheap. It is NOT a ground-truth evaluator.
    """
    text = (response_text or "").strip()
    length = len(text)

    # Medium brevity: not too short / not too long
    # (These thresholds are heuristic and should be tuned with real data.)
    brevity_score = 0.0
    if 80 <= length <= 500:
        brevity_score = 1.0
    elif 40 <= length < 80 or 500 < length <= 800:
        brevity_score = 0.5

    # Light structure: presence of bullets / numbering
    has_bullets = ("\n- " in text) or ("\n1." in text) or ("\n1、" in text) or ("\n①" in text)
    structure_score = 1.0 if has_bullets else 0.0

    # Neutral directness: start with a clear answer marker
    head = text[:40]
    directness_markers = ("建议", "可以", "我建议", "你可以", "结论", "先说")
    directness_score = 1.0 if any(m in head for m in directness_markers) else 0.0

    overall = (brevity_score + structure_score + directness_score) / 3.0
    return {
        "overall": overall,
        "brevity": brevity_score,
        "structure": structure_score,
        "directness": directness_score,
        "length_chars": float(length),
    }


def _build_prompt(*, policy_block: str) -> str:
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    from app.services.prompt import CHATCOACH_PROMPT

    conversation_summary = "用户和对方在轻松聊天，话题是旅行与兴趣。"
    conversation = _format_conversation(
        [
            {"speaker": "user", "content": "我周末喜欢出去走走，你呢？"},
            {"speaker": "target", "content": "我也喜欢！我最近在研究去哪儿旅行。"},
            {"speaker": "user", "content": "那你更喜欢计划好行程还是随性一点？"},
        ]
    )

    return CHATCOACH_PROMPT.format(
        scenario="BALANCED",
        current_intimacy_level=45,
        intimacy_level=55,
        emotion_state="positive",
        conversation_summary=conversation_summary,
        conversation=conversation,
        persona_snapshot_prompt="（示例画像：略）",
        policy_block=policy_block,
        reply_sentence="那你更喜欢计划好行程还是随性一点？",
        language="zh",
        recommended_strategies="story_snippet, neutral_open_question",
        current_scenario="平衡/中风险策略",
        recommended_scenario="平衡/中风险策略",
    )


def _aggregate_trials(trials: list[dict]) -> dict:
    scored = [t for t in trials if isinstance(t, dict) and "delta" in t]
    if not scored:
        return {"trials_scored": 0}

    def _get(path: list[str], default: float = 0.0) -> float:
        cur: object = t
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        if isinstance(cur, (int, float)):
            return float(cur)
        return default

    deltas: dict[str, float] = {
        "overall": 0.0,
        "brevity": 0.0,
        "structure": 0.0,
        "directness": 0.0,
        "length_chars": 0.0,
    }
    on_means: dict[str, float] = {"overall": 0.0, "brevity": 0.0, "structure": 0.0, "directness": 0.0}
    off_means: dict[str, float] = {"overall": 0.0, "brevity": 0.0, "structure": 0.0, "directness": 0.0}
    wins = 0
    ties = 0

    for t in scored:
        on_overall = _get(["policy_on", "score", "overall"], 0.0)
        off_overall = _get(["policy_off", "score", "overall"], 0.0)
        if on_overall > off_overall:
            wins += 1
        elif on_overall == off_overall:
            ties += 1

        for k in deltas.keys():
            cur = t.get("delta", {})
            if isinstance(cur, dict) and isinstance(cur.get(k), (int, float)):
                deltas[k] += float(cur[k])

        for k in on_means.keys():
            on_means[k] += _get(["policy_on", "score", k], 0.0)
            off_means[k] += _get(["policy_off", "score", k], 0.0)

    n = float(len(scored))
    return {
        "trials_scored": int(n),
        "win_rate_policy_on": wins / n,
        "tie_rate": ties / n,
        "mean_delta": {k: v / n for k, v in deltas.items()},
        "mean_score_policy_on": {k: v / n for k, v in on_means.items()},
        "mean_score_policy_off": {k: v / n for k, v in off_means.items()},
    }


async def _call_llm(
    *,
    prompt: str,
    user_id: str,
    quality: str,
    provider: str | None,
    model: str | None,
) -> dict:
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    from app.services.llm_adapter import LLMAdapterImpl, LLMCall

    adapter = LLMAdapterImpl()
    call = LLMCall(
        task_type="generation",
        prompt=prompt,
        quality=quality,
        user_id=user_id,
        provider=provider,
        model=model,
    )
    result = await adapter.call(call)
    return {
        "text": result.text,
        "provider": result.provider,
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd,
    }


def _build_policy_block(*, user_id: str) -> str:
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    sys.path.insert(0, str((PROJECT_ROOT / "core" / "user_profile" / "src").resolve()))
    from user_profile import ProfileManager, compile_trait_vector_to_policy, format_policy_instructions

    mgr = ProfileManager()

    # Force values into MEDIUM so you can see the MEDIUM default instructions.
    mappings = [
        {
            "action": "MAP",
            "target_trait": "brevity_preference",
            "inferred_value": 0.55,
            "confidence": 0.9,
            "original_trait_name": "中等简洁偏好",
            "trait_name": "中等简洁偏好",
        },
        {
            "action": "MAP",
            "target_trait": "structure_need",
            "inferred_value": 0.52,
            "confidence": 0.9,
            "original_trait_name": "适度结构",
            "trait_name": "适度结构",
        },
        {
            "action": "MAP",
            "target_trait": "directness_level",
            "inferred_value": 0.50,
            "confidence": 0.9,
            "original_trait_name": "中性直接",
            "trait_name": "中性直接",
        },
    ]

    mgr.update_trait_vector_from_mappings(user_id, mappings)
    profile = mgr.get_profile(user_id)
    compiled = compile_trait_vector_to_policy(profile.trait_vector)
    return format_policy_instructions(compiled.instructions)


async def _run(args: argparse.Namespace) -> None:
    user_id = args.user_id
    policy_block = _build_policy_block(user_id=user_id)

    prompt_with_policy = _build_prompt(policy_block=policy_block)
    prompt_without_policy = _build_prompt(policy_block="")

    trials: list[dict] = []

    if args.no_llm:
        trials.append(
            {
                "policy_on": {"prompt": prompt_with_policy},
                "policy_off": {"prompt": prompt_without_policy},
            }
        )
    else:
        for i in range(args.trials):
            on = await _call_llm(
                prompt=prompt_with_policy,
                user_id=user_id,
                quality=args.quality,
                provider=args.provider,
                model=args.model,
            )
            off = await _call_llm(
                prompt=prompt_without_policy,
                user_id=user_id,
                quality=args.quality,
                provider=args.provider,
                model=args.model,
            )

            on_score = _score_response(response_text=on.get("text", ""))
            off_score = _score_response(response_text=off.get("text", ""))

            trials.append(
                {
                    "trial": i + 1,
                    "policy_on": {"llm": on, "score": on_score},
                    "policy_off": {"llm": off, "score": off_score},
                    "delta": {
                        "overall": on_score["overall"] - off_score["overall"],
                        "brevity": on_score["brevity"] - off_score["brevity"],
                        "structure": on_score["structure"] - off_score["structure"],
                        "directness": on_score["directness"] - off_score["directness"],
                        "length_chars": on_score["length_chars"] - off_score["length_chars"],
                    },
                }
            )

    report = {
        "generated_at": datetime.now().isoformat(),
        "config": {
            "user_id": user_id,
            "provider": args.provider,
            "model": args.model,
            "quality": args.quality,
            "trials": args.trials,
            "no_llm": bool(args.no_llm),
        },
        "policy_block": policy_block,
        "prompt_with_policy": prompt_with_policy,
        "prompt_without_policy": prompt_without_policy,
        "trials": trials,
        "summary": _aggregate_trials(trials),
    }

    out_json = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out_json, encoding="utf-8")
    print(out_json)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A/B test: policy on/off prompts with optional real LLM calls",
    )
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--quality", type=str, default="normal", choices=["cheap", "normal", "premium"])
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--user-id", type=str, default="u_policy_ab_test")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Only output prompts; do not call LLM.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional output path for the JSON report.",
    )
    args = parser.parse_args()

    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
