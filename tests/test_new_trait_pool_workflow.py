import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.container import get_container, reset_container


@pytest.fixture(autouse=True)
def _reset_services():
    reset_container()
    yield
    reset_container()


@pytest.mark.asyncio
async def test_new_trait_pool_review_workflow_smoke():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id = "u_new_trait_pool_smoke"
        trait_name = "喜欢用反问推动思考"

        container = get_container()
        svc = container.get_user_profile_service()
        core_mgr = getattr(svc, "manager", None)
        assert core_mgr is not None

        core_mgr.upsert_tag_with_incrementing_counter(
            user_id,
            "new_trait_pool",
            trait_name,
            {
                "trait_name": trait_name,
                "status": "pending_review",
                "first_seen": "2026-01-20T00:00:00",
                "last_seen": "2026-01-20T00:00:00",
                "frequency": 1,
                "example_users": [user_id],
                "candidate_merge_targets": [],
                "sample_mappings": [{"trait_name": trait_name, "action": "NEW"}],
                "review_history": [],
                "mapping": {"trait_name": trait_name, "action": "NEW"},
            },
            counter_key="count",
            delta=1,
        )

        resp = await client.post(
            "/api/v1/user_profile/new_trait_pool/list",
            json={"user_id": user_id},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["trait_name"] == trait_name
        assert items[0]["value"]["status"] == "pending_review"

        resp = await client.post(
            "/api/v1/user_profile/new_trait_pool/review",
            json={
                "user_id": user_id,
                "trait_name": trait_name,
                "action": "approve",
                "note": "looks useful",
            },
        )
        assert resp.status_code == 200
        reviewed = resp.json()["value"]
        assert reviewed["status"] == "approved"
        assert reviewed.get("review_action") == "approve"
        assert isinstance(reviewed.get("review_history"), list)
        assert len(reviewed["review_history"]) == 1

        resp = await client.post(
            "/api/v1/user_profile/new_trait_pool/review",
            json={
                "user_id": user_id,
                "trait_name": trait_name,
                "action": "merge",
                "merged_into": "depth_preference",
                "note": "merge into standard trait",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("merged_mapping_applied") is True

        resp = await client.post(
            "/api/v1/user_profile/trait_vector/get",
            json={"user_id": user_id},
        )
        assert resp.status_code == 200
        tv = resp.json()["trait_vector"]
        assert "depth_preference" in tv.get("traits", {})
