def _add_balance(client, association_id, name="Caisse", amount="50.00"):
    return client.post(
        "/api/balances_add",
        json={
            "name": name,
            "initialAmount": amount,
            "association_id": association_id,
        },
    )


def test_add_balance(auth):
    client, association_id = auth
    response = _add_balance(client, association_id)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Caisse"
    assert data["association_id"] == association_id


def test_add_balance_wrong_association(auth):
    client, _ = auth
    response = _add_balance(client, "someone-else-id")
    assert response.status_code == 403


def test_update_balance(auth):
    client, association_id = auth
    balance_id = _add_balance(client, association_id).json()["id"]
    response = client.put(
        f"/api/balances/{balance_id}",
        json={"name": "Renamed", "initialAmount": "75.00", "position": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Renamed"
    assert data["position"] == 3


def test_delete_empty_balance(auth):
    client, association_id = auth
    balance_id = _add_balance(client, association_id).json()["id"]
    assert client.delete(f"/api/balances/{balance_id}").status_code == 200


def test_cannot_delete_balance_with_operations(auth):
    client, association_id = auth
    balance_id = _add_balance(client, association_id).json()["id"]
    client.post(
        "/api/operations",
        json={
            "name": "op",
            "description": "d",
            "group": "g",
            "amount": "10.00",
            "type": "income",
            "date": "2026-01-01T00:00:00",
            "balance_id": balance_id,
        },
    )
    response = client.delete(f"/api/balances/{balance_id}")
    assert response.status_code == 400


def test_balance_isolation_between_associations(auth):
    client, association_id = auth
    # Balance owned by AuthAsso (created via the auth fixture).
    victim_balance = _add_balance(client, association_id, name="Victim").json()

    # Create and switch to a second association on the same client.
    client.post(
        "/api/signup",
        json={
            "name": "Intruder",
            "email": "intruder@example.com",
            "password": "password123",
            "balances": [],
        },
    )
    client.post("/api/login", json={"name": "Intruder", "password": "password123"})

    # The intruder must not read or delete another association's balance.
    assert (
        client.get(f"/api/balances/{victim_balance['id']}/operations").status_code
        == 403
    )
    assert client.delete(f"/api/balances/{victim_balance['id']}").status_code == 403


def test_reorder_balances(auth):
    client, association_id = auth
    b1 = _add_balance(client, association_id, name="B1").json()
    b2 = _add_balance(client, association_id, name="B2").json()
    response = client.put(
        "/api/balances/reorder",
        json={
            "balances": [
                {"id": b1["id"], "position": 1},
                {"id": b2["id"], "position": 0},
            ]
        },
    )
    assert response.status_code == 200

    # Positions must be persisted.
    me = client.get("/api/me").json()
    positions = {b["id"]: b["position"] for b in me["balances"]}
    assert positions[b1["id"]] == 1
    assert positions[b2["id"]] == 0
