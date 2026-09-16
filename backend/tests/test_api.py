"""
test_api.py - Integration tests for FastAPI endpoints.
"""

from starlette.testclient import TestClient
from app.api.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ONLINE"


def test_get_state():
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "protocol" in data
    assert "storage" in data
    assert "transactions" in data
    assert "wal_records" in data


def test_submit_transaction_and_retrieve():
    payload = {
        "operations": [
            {"op_type": "WRITE", "key": "A", "value": 777},
            {"op_type": "READ", "key": "A"},
        ],
        "txn_id": "APITestTxn",
    }
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 200
    assert response.json()["txn_id"] == "APITestTxn"


def test_serializability_endpoint():
    res = client.post("/api/serializability/check", json={"schedule": "r1[x] w1[x] r2[x] w2[x] c1 c2"})
    assert res.status_code == 200
    assert res.json()["is_serializable"] is True

    res_cycle = client.post("/api/serializability/check", json={"schedule": "r1[x] w2[x] w1[x] c1 c2"})
    assert res_cycle.status_code == 200
    assert res_cycle.json()["is_serializable"] is False


def test_isolation_endpoint():
    res = client.post(
        "/api/isolation/run",
        json={"scenario": "dirty_read", "isolation_level": "READ_UNCOMMITTED"},
    )
    assert res.status_code == 200
    assert res.json()["anomaly_occurred"] is True

    res2 = client.post(
        "/api/isolation/run",
        json={"scenario": "dirty_read", "isolation_level": "SERIALIZABLE"},
    )
    assert res2.status_code == 200
    assert res2.json()["anomaly_occurred"] is False


def test_config_update():
    res = client.post("/api/config", json={"protocol": "OCC"})
    assert res.status_code == 200
    assert res.json()["config"]["protocol"] == "OCC"

    # Reset back to 2PL
    client.post("/api/config", json={"protocol": "2PL"})
