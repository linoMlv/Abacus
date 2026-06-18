from fastapi.testclient import TestClient


def _balance_id(client, association_id, name="Ops", amount="0.00"):
    return client.post(
        "/api/balances_add",
        json={"name": name, "initialAmount": amount, "association_id": association_id},
    ).json()["id"]


def _op_payload(balance_id, **overrides):
    payload = {
        "name": "Don",
        "description": "Don mensuel",
        "group": "Dons",
        "amount": "42.50",
        "type": "income",
        "date": "2026-03-01T00:00:00",
        "balance_id": balance_id,
    }
    payload.update(overrides)
    return payload


def test_create_operation(auth):
    client, association_id = auth
    balance_id = _balance_id(client, association_id)
    response = client.post("/api/operations", json=_op_payload(balance_id))
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Don"


def test_create_operation_negative_amount_rejected(auth):
    client, association_id = auth
    balance_id = _balance_id(client, association_id)
    response = client.post(
        "/api/operations", json=_op_payload(balance_id, amount="-5.00")
    )
    assert response.status_code == 400


def test_create_operation_unknown_balance(auth):
    client, _ = auth
    response = client.post("/api/operations", json=_op_payload("nope"))
    assert response.status_code == 404


def test_update_operation(auth):
    client, association_id = auth
    balance_id = _balance_id(client, association_id)
    op_id = client.post("/api/operations", json=_op_payload(balance_id)).json()["id"]
    response = client.put(
        f"/api/operations/{op_id}",
        json=_op_payload(balance_id, name="Updated", amount="99.99"),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


def test_delete_operation(auth):
    client, association_id = auth
    balance_id = _balance_id(client, association_id)
    op_id = client.post("/api/operations", json=_op_payload(balance_id)).json()["id"]
    assert client.delete(f"/api/operations/{op_id}").status_code == 200
    # Listing operations should no longer include it.
    ops = client.get("/api/operations").json()
    assert all(o["id"] != op_id for o in ops)


def test_list_operations_date_filter(auth):
    client, association_id = auth
    balance_id = _balance_id(client, association_id)
    client.post(
        "/api/operations", json=_op_payload(balance_id, date="2026-01-15T00:00:00")
    )
    client.post(
        "/api/operations", json=_op_payload(balance_id, date="2026-06-15T00:00:00")
    )

    filtered = client.get(
        "/api/operations",
        params={"start_date": "2026-05-01T00:00:00", "end_date": "2026-07-01T00:00:00"},
    ).json()
    assert len(filtered) == 1


def test_operations_require_auth(client: TestClient):
    assert client.get("/api/operations").status_code == 401
