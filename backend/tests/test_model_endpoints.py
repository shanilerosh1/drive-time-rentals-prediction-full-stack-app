from app.core.damage_classes import DAMAGE_CLASSES, DEFAULT_THRESHOLDS


def test_health_is_open(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_model_endpoint_warns_when_no_weights_are_loaded(client):
    body = client.get("/api/v1/model").json()
    assert body["backend"] == "mock"
    assert body["is_real"] is False
    assert "must not be used as evidence" in body["warning"]


def test_damage_classes_expose_the_notebook_thresholds(client):
    classes = client.get("/api/v1/damage-classes").json()["classes"]
    assert [c["name"] for c in classes] == list(DAMAGE_CLASSES)
    for entry in classes:
        assert entry["default_threshold"] == DEFAULT_THRESHOLDS[entry["name"]]
        assert entry["colour"].startswith("#")


def test_dashboard_stats_shape(client, admin_headers):
    body = client.get("/api/v1/dashboard/stats", headers=admin_headers).json()
    assert body["total_vehicles"] == 0
    assert body["backend"] == "mock"
    assert body["is_real_model"] is False
    assert body["recent_inspections"] == []


def test_evaluation_endpoint_is_honest_when_no_report_exists(client, admin_headers, tmp_path):
    """A missing report must 404 with guidance, never fabricate metrics."""
    from app.core.config import settings

    report = settings.CLASSIFIER_WEIGHTS.parent / "evaluation.json"
    backup = report.read_bytes() if report.exists() else None
    if report.exists():
        report.unlink()
    try:
        response = client.get("/api/v1/model/evaluation", headers=admin_headers)
        assert response.status_code == 404
        assert "training/evaluate.py" in response.json()["detail"]
    finally:
        if backup is not None:
            report.write_bytes(backup)


def test_evaluation_endpoint_serves_a_report_when_present(client, admin_headers):
    import json

    from app.core.config import settings

    report = settings.CLASSIFIER_WEIGHTS.parent / "evaluation.json"
    existed = report.exists()
    backup = report.read_bytes() if existed else None
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        "split": "test", "images": 2, "backend": "classifier",
        "model_name": "efficientnet_b3", "model_version": "1",
        "per_class": {}, "macro": {}, "micro": {},
        "exact_match_ratio": 0.5, "any_damage_accuracy": 1.0,
        "examples": [{"file_name": "a.jpg"}, {"file_name": "b.jpg"}],
    }))
    try:
        body = client.get("/api/v1/model/evaluation", headers=admin_headers).json()
        assert body["images"] == 2
        assert body["example_count"] == 2
    finally:
        if backup is not None:
            report.write_bytes(backup)
        else:
            report.unlink(missing_ok=True)
