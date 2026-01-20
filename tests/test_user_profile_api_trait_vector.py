import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.container import reset_container


@pytest.fixture(autouse=True)
def _reset_services():
    reset_container()
    yield
    reset_container()


@pytest.mark.asyncio
async def test_trait_vector_endpoints_smoke():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id = "u_api_trait_vector_smoke"

        # Initially no profile
        resp = await client.post("/api/v1/user_profile/trait_vector/get", json={"user_id": user_id})
        assert resp.status_code == 404

        # Update (creates profile implicitly in core manager)
        mappings = [
            {
                "action": "MAP",
                "target_trait": "brevity_preference",
                "inferred_value": 0.9,
                "confidence": 0.9,
                "original_trait_name": "prefers concise",
                "trait_name": "prefers concise",
            }
        ]
        resp = await client.post(
            "/api/v1/user_profile/trait_vector/update",
            json={"user_id": user_id, "mappings": mappings, "source": "trait_mapping"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user_id
        assert "trait_vector" in data

        # Get again
        resp = await client.post("/api/v1/user_profile/trait_vector/get", json={"user_id": user_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user_id
        assert "trait_vector" in data

        # Freeze
        resp = await client.post(
            "/api/v1/user_profile/trait_vector/freeze",
            json={"user_id": user_id, "trait_name": "brevity_preference", "frozen": True},
        )
        assert resp.status_code == 200

        # Version history
        resp = await client.post(
            "/api/v1/user_profile/profile/version_history",
            json={"user_id": user_id, "limit": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user_id
        assert isinstance(data["history"], list)
