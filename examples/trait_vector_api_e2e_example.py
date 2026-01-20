import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path


def _default_messages():
    from app.models.schemas import Message

    now = datetime.now()
    return [
        Message(id="m1", speaker="user", content="我希望你回答更简洁一些，重点突出。", timestamp=now),
        Message(id="m2", speaker="target", content="好的，你想聊什么？", timestamp=now),
        Message(id="m3", speaker="user", content="那你更喜欢计划好行程还是随性一点？", timestamp=now),
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(description="E2E example: learn traits -> update trait_vector -> compile policy -> assemble prompt")
    parser.add_argument("--user-id", type=str, default="u_e2e_19_20")
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--quality", type=str, default="normal", choices=["cheap", "normal", "premium"])
    parser.add_argument("--call-llm", action="store_true")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    from app.services.user_profile_impl import UserProfileService
    from app.services.prompt_assembler import PromptAssembler
    from app.models.schemas import ContextResult, SceneAnalysisResult, PersonaSnapshot, ReplyGenerationInput

    user_profile_service = UserProfileService(llm_adapter=None)

    user_id = args.user_id
    await user_profile_service.create_profile(user_id)

    mappings = [
        {
            "action": "MAP",
            "target_trait": "brevity_preference",
            "inferred_value": 0.9,
            "confidence": 0.9,
            "original_trait_name": "偏好简洁",
            "trait_name": "偏好简洁",
            "reason": "用户明确提出要简洁",
            "trigger_conversation_id": "conv_e2e",
        },
        {
            "action": "MAP",
            "target_trait": "structure_need",
            "inferred_value": 0.8,
            "confidence": 0.85,
            "original_trait_name": "偏好结构化",
            "trait_name": "偏好结构化",
            "reason": "用户希望重点突出",
            "trigger_conversation_id": "conv_e2e",
        },
    ]

    tv_after = await user_profile_service.update_trait_vector_from_mappings(user_id, mappings, source="trait_mapping")

    from user_profile import compile_trait_vector_to_policy, format_policy_instructions

    profile = await user_profile_service.get_profile(user_id)
    core_profile = getattr(profile, "core_profile", None) if profile is not None else None
    trait_vector = getattr(core_profile, "trait_vector", None) if core_profile is not None else None
    compiled = compile_trait_vector_to_policy(trait_vector)
    policy_block = format_policy_instructions(compiled.instructions)

    context = ContextResult(
        conversation_summary="用户更偏好简洁、结构化的回复。",
        emotion_state="positive",
        current_intimacy_level=45,
        risk_flags=[],
        conversation=_default_messages(),
    )
    scene = SceneAnalysisResult(
        relationship_state="推进",
        scenario="BALANCED",
        intimacy_level=55,
        risk_flags=[],
        current_scenario="平衡/中风险策略",
        recommended_scenario="平衡/中风险策略",
        recommended_strategies=["story_snippet", "neutral_open_question"],
    )
    persona = PersonaSnapshot(
        style="理性",
        pacing="normal",
        risk_tolerance="medium",
        confidence=0.7,
        prompt="（示例 persona）",
    )

    assembler = PromptAssembler(user_profile_service)
    assembled_prompt = await assembler.assemble_reply_prompt(
        ReplyGenerationInput(
            user_id=user_id,
            prompt="",
            quality=args.quality,
            context=context,
            scene=scene,
            persona=persona,
            reply_sentence="那你更喜欢计划好行程还是随性一点？",
            language="zh",
        )
    )

    out = {
        "generated_at": datetime.now().isoformat(),
        "user_id": user_id,
        "trait_vector_api_result": tv_after,
        "policy": {"tags": compiled.tags, "instructions": compiled.instructions, "policy_block": policy_block},
        "assembled_prompt": assembled_prompt,
    }

    if args.call_llm:
        from app.services.llm_adapter import LLMAdapterImpl, LLMCall

        adapter = LLMAdapterImpl()
        llm_call = LLMCall(
            task_type="generation",
            prompt=assembled_prompt,
            quality=args.quality,
            user_id=user_id,
            provider=args.provider,
            model=args.model,
        )
        result = await adapter.call(llm_call)
        out["llm"] = {
            "text": result.text,
            "provider": result.provider,
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
        }

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
