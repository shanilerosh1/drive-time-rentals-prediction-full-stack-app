def test_registration_is_normalised_and_unique(client, admin_headers):
    first = client.post(
        "/api/v1/vehicles",
        json={"registration": " cba 9999 ", "make": "Honda", "model": "Fit"},
        headers=admin_headers,
    )
    assert first.status_code == 201
    assert first.json()["registration"] == "CBA-9999"

    duplicate = client.post(
        "/api/v1/vehicles",
        json={"registration": "CBA-9999", "make": "Honda", "model": "Fit"},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409


def test_search_filters_the_fleet(client, admin_headers, vehicle):
    client.post(
        "/api/v1/vehicles",
        json={"registration": "XYZ-1111", "make": "Nissan", "model": "Leaf"},
        headers=admin_headers,
    )
    response = client.get("/api/v1/vehicles", params={"search": "Nissan"}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["make"] == "Nissan"
