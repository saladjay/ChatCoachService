import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.models.schemas import LLMResult
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.user_profile_impl import UserProfileService


class FakeLLMAdapter(BaseLLMAdapter):
    async def call(self, llm_call: LLMCall) -> LLMResult:
        prompt = llm_call.prompt or ""

        # Stage 2 mapping
        if "标准用户特征集合" in prompt and "\"action\"" in prompt:
            mapping = [
                {
                    "original_trait_name": "偏好深入讨论",
                    "action": "MAP",
                    "target_trait": "depth_preference",
                    "new_trait_name": "",
                    "inferred_value": 0.9,
                    "confidence": 0.86,
                    "reason": "该特征描述用户倾向于深入讨论问题，与 depth_preference 高度一致。",
                },
                {
                    "original_trait_name": "喜欢用反问推动思考",
                    "action": "NEW",
                    "target_trait": "",
                    "new_trait_name": "喜欢用反问推动思考",
                    "confidence": 0.74,
                    "reason": "属于表达/互动手法，标准特征集中缺少直接对应项。",
                },
            ]
            text = json.dumps(mapping, ensure_ascii=False)
            return LLMResult(
                text=text,
                provider=llm_call.provider or "fake",
                model=llm_call.model or "fake-model",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
            )

        # Stage 1 discovery
        discovery = {
            "general_traits": [
                {
                    "trait_name": "偏好深入讨论",
                    "description": "倾向于追问原因与底层逻辑，而不是停留在表面结论。",
                    "evidence": "多次要求解释‘为什么’以及‘能否展开’。",
                }
            ],
            "personal_traits": [
                {
                    "trait_name": "喜欢用反问推动思考",
                    "description": "常通过反问句引导对方澄清观点或进一步思考。",
                    "evidence": "多次使用‘那你觉得呢？’‘为什么不反过来想？’等表述。",
                }
            ],
        }
        text = json.dumps(discovery, ensure_ascii=False)
        return LLMResult(
            text=text,
            provider=llm_call.provider or "fake",
            model=llm_call.model or "fake-model",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )


async def main() -> None:
    svc = UserProfileService(llm_adapter=FakeLLMAdapter())
    user_id = f"example_user_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    selected_sentences = [f"示例句子 {i}：用户表达偏好与思考方式。" for i in range(1, 11)]

    for i in range(1, 4):
        print(f"\n=== Run #{i} (trait_vector updates after evidence_count>=3) ===")
        result = await svc.learn_new_traits(
            user_id=user_id,
            selected_sentences=selected_sentences,
            store=True,
            map_to_standard=True,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

        core_profile = svc._manager.get_profile(user_id)
        trait_vector = None
        if core_profile is not None:
            trait_vector = getattr(core_profile, "trait_vector", None)
        print("\n[Core] trait_vector")
        if trait_vector is None:
            print("null")
        else:
            tv = {
                "schema_version": trait_vector.schema_version,
                "traits": {
                    k: {
                        "value": v.value,
                        "evidence_count": v.evidence_count,
                        "confidence": v.confidence,
                        "last_direction": getattr(v, "last_direction", 0),
                        "direction_streak": getattr(v, "direction_streak", 0),
                        "frozen": v.frozen,
                    }
                    for k, v in trait_vector.traits.items()
                },
            }
            print(json.dumps(tv, ensure_ascii=False, indent=2))

    print("\n=== Freeze depth_preference and run once (value should NOT change) ===")
    core_profile = svc._manager.get_profile(user_id)
    version_before_freeze = None
    if core_profile is not None:
        version_before_freeze = core_profile.version
    svc._manager.set_trait_frozen(user_id, "depth_preference", True)
    await svc.learn_new_traits(
        user_id=user_id,
        selected_sentences=selected_sentences,
        store=True,
        map_to_standard=True,
    )
    core_profile = svc._manager.get_profile(user_id)
    if core_profile is not None and core_profile.trait_vector is not None:
        frozen_state = core_profile.trait_vector.traits.get("depth_preference")
        if frozen_state is not None:
            print(json.dumps({"value": frozen_state.value, "evidence_count": frozen_state.evidence_count, "frozen": frozen_state.frozen}, ensure_ascii=False, indent=2))

    print("\n=== Rollback to pre-freeze version ===")
    if version_before_freeze is not None:
        svc._manager.rollback_profile_to_version(user_id, version_before_freeze)
    core_profile = svc._manager.get_profile(user_id)
    if core_profile is not None and core_profile.trait_vector is not None:
        rb_state = core_profile.trait_vector.traits.get("depth_preference")
        if rb_state is not None:
            print(json.dumps({"value": rb_state.value, "evidence_count": rb_state.evidence_count, "frozen": rb_state.frozen}, ensure_ascii=False, indent=2))

    print("\n[Tags] learned_traits/general")
    print(json.dumps(await svc.get_tags(user_id, category="learned_traits/general"), ensure_ascii=False, indent=2))

    print("\n[Tags] learned_traits/personal")
    print(json.dumps(await svc.get_tags(user_id, category="learned_traits/personal"), ensure_ascii=False, indent=2))

    print("\n[Tags] learned_traits/mapping")
    print(json.dumps(await svc.get_tags(user_id, category="learned_traits/mapping"), ensure_ascii=False, indent=2))

    print("\n[Tags] new_trait_pool")
    print(json.dumps(await svc.get_tags(user_id, category="new_trait_pool"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
