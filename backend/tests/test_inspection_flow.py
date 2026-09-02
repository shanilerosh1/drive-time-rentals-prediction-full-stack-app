"""End-to-end: create -> upload -> analyse -> report -> compare."""
from tests.conftest import make_image


def _create_inspection(client, headers, vehicle, kind, rental_ref="R-1001"):
    response = client.post(
        "/api/v1/inspections",
        json={
            "vehicle_id": vehicle["id"],
            "inspection_type": kind,
            "rental_ref": rental_ref,
            "odometer_km": 42000,
            "location": "Colombo return bay",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client, headers, inspection_id, colour=(120, 130, 140), angle="front"):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/images",
        files=[("files", ("front.jpg", make_image(colour), "image/jpeg"))],
        data={"capture_angle": angle, "analyse": "true"},
        headers=headers,
    )


def test_full_inspection_lifecycle(client, admin_headers, vehicle):
    inspection = _create_inspection(client, admin_headers, vehicle, "pre_rental")
    assert inspection["status"] == "draft"

    upload = _upload(client, admin_headers, inspection["id"])
    assert upload.status_code == 201, upload.text
    images = upload.json()
    assert len(images) == 1
    assert images[0]["status"] == "analysed"
    assert len(images[0]["detections"]) == 6  # one row per damage class
    assert len(images[0]["sha256"]) == 64

    detail = client.get(f"/api/v1/inspections/{inspection['id']}", headers=admin_headers).json()
    assert detail["status"] == "completed"
    assert detail["image_count"] == 1
    assert detail["completed_at"] is not None

    file_response = client.get(f"/api/v1/images/{images[0]['id']}/file", headers=admin_headers)
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == "image/jpeg"

    thumb = client.get(f"/api/v1/images/{images[0]['id']}/thumbnail", headers=admin_headers)
    assert thumb.status_code == 200

    report = client.get(f"/api/v1/inspections/{inspection['id']}/report", headers=admin_headers)
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content.startswith(b"%PDF")


def test_rejects_a_non_image_upload(client, admin_headers, vehicle):
    inspection = _create_inspection(client, admin_headers, vehicle, "pre_rental")
    response = client.post(
        f"/api/v1/inspections/{inspection['id']}/images",
        files=[("files", ("notes.txt", b"this is not an image", "text/plain"))],
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "not a readable image" in response.json()["detail"].lower()


def test_analysis_is_idempotent_unless_forced(client, admin_headers, vehicle):
    inspection = _create_inspection(client, admin_headers, vehicle, "pre_rental")
    _upload(client, admin_headers, inspection["id"])

    again = client.post(
        f"/api/v1/inspections/{inspection['id']}/analyse", json={}, headers=admin_headers
    ).json()
    assert again["analysed"] == 0
    assert again["skipped"] == 1

    forced = client.post(
        f"/api/v1/inspections/{inspection['id']}/analyse",
        json={"force": True},
        headers=admin_headers,
    ).json()
    assert forced["analysed"] == 1

    # Re-analysis must replace findings, never accumulate a second set.
    detail = client.get(f"/api/v1/inspections/{inspection['id']}", headers=admin_headers).json()
    assert len(detail["images"][0]["detections"]) == 6


def test_uploading_to_a_completed_inspection_reopens_it(client, admin_headers, vehicle):
    inspection = _create_inspection(client, admin_headers, vehicle, "pre_rental")
    _upload(client, admin_headers, inspection["id"])

    second = client.post(
        f"/api/v1/inspections/{inspection['id']}/images",
        files=[("files", ("rear.jpg", make_image((10, 20, 30)), "image/jpeg"))],
        data={"capture_angle": "rear", "analyse": "false"},
        headers=admin_headers,
    )
    assert second.status_code == 201
    detail = client.get(f"/api/v1/inspections/{inspection['id']}", headers=admin_headers).json()
    assert detail["status"] == "draft"
    assert detail["completed_at"] is None


def test_mock_predictor_is_deterministic(client, admin_headers, vehicle):
    """The same bytes must score identically, or comparison would be noise."""
    first = _create_inspection(client, admin_headers, vehicle, "pre_rental", "R-A")
    second = _create_inspection(client, admin_headers, vehicle, "post_rental", "R-A")

    a = _upload(client, admin_headers, first["id"], colour=(77, 88, 99)).json()[0]
    b = _upload(client, admin_headers, second["id"], colour=(77, 88, 99)).json()[0]

    scores_a = {d["class_name"]: d["confidence"] for d in a["detections"]}
    scores_b = {d["class_name"]: d["confidence"] for d in b["detections"]}
    assert scores_a == scores_b


def test_comparison_flags_new_damage(client, admin_headers, vehicle):
    pre = _create_inspection(client, admin_headers, vehicle, "pre_rental", "R-2002")
    post = _create_inspection(client, admin_headers, vehicle, "post_rental", "R-2002")

    # Different bytes -> different mock scores -> a non-trivial delta.
    _upload(client, admin_headers, pre["id"], colour=(200, 30, 30))
    _upload(client, admin_headers, post["id"], colour=(30, 200, 30))

    response = client.get(
        "/api/v1/comparisons",
        params={"vehicle_id": vehicle["id"], "rental_ref": "R-2002"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pre_inspection"]["id"] == pre["id"]
    assert body["post_inspection"]["id"] == post["id"]
    assert body["is_complete"] is True
    # Mock output is not evidence, and the payload must say so.
    assert body["uses_real_model"] is False

    outcomes = {row["class_name"]: row["outcome"] for row in body["rows"]}
    for class_name, outcome in outcomes.items():
        assert outcome in {"new", "pre_existing", "resolved"}
    assert set(body["new_damage_classes"]) == {
        name for name, outcome in outcomes.items() if outcome == "new"
    }


def test_comparison_without_a_baseline_explains_itself(client, admin_headers, vehicle):
    post = _create_inspection(client, admin_headers, vehicle, "post_rental", "R-3003")
    _upload(client, admin_headers, post["id"])

    body = client.get(
        "/api/v1/comparisons",
        params={"vehicle_id": vehicle["id"], "rental_ref": "R-3003"},
        headers=admin_headers,
    ).json()
    assert body["pre_inspection"] is None
    assert body["is_complete"] is False
    assert "no baseline" in body["note"].lower()


def test_comparison_report_is_a_pdf(client, admin_headers, vehicle):
    pre = _create_inspection(client, admin_headers, vehicle, "pre_rental", "R-4004")
    post = _create_inspection(client, admin_headers, vehicle, "post_rental", "R-4004")
    _upload(client, admin_headers, pre["id"], colour=(9, 9, 9))
    _upload(client, admin_headers, post["id"], colour=(240, 240, 240))

    response = client.get(
        "/api/v1/comparisons/report",
        params={"vehicle_id": vehicle["id"], "rental_ref": "R-4004"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_inspector_cannot_edit_another_inspectors_record(client, admin_headers, vehicle):
    inspection = _create_inspection(client, admin_headers, vehicle, "pre_rental")

    client.post(
        "/api/v1/users",
        json={
            "email": "other@example.com",
            "full_name": "Other Inspector",
            "role": "inspector",
            "password": "OtherPass123!",
        },
        headers=admin_headers,
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "OtherPass123!"},
    ).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}

    assert client.get(f"/api/v1/inspections/{inspection['id']}", headers=other).status_code == 200
    assert (
        client.patch(
            f"/api/v1/inspections/{inspection['id']}", json={"notes": "x"}, headers=other
        ).status_code
        == 403
    )
