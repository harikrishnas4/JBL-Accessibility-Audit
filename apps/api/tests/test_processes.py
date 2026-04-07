from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from jbl_audit_api.db.models import ProcessFlow, ProcessFlowStep


def build_run(client: TestClient) -> str:
    response = client.post(
        "/runs",
        json={
            "course_url_or_name": "https://courses.example.com/course/view.php?id=88",
            "auth_metadata": {"method": "session-state", "auth_context": "learner"},
        },
    )
    return response.json()["run_id"]


def build_asset(
    *,
    asset_id: str,
    asset_type: str,
    locator: str,
    source_system: str = "moodle",
    scope_status: str = "in_scope",
    scope_reason: str | None = None,
    layer: str = "course_module",
    shared_key: str | None = None,
    owner_team: str | None = None,
    auth_context: dict | None = None,
    handling_path: str = "mod/page",
    component_fingerprint: dict | None = None,
) -> dict:
    payload = {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "source_system": source_system,
        "locator": locator,
        "scope_status": scope_status,
        "layer": layer,
        "shared_key": shared_key,
        "owner_team": owner_team,
        "auth_context": auth_context or {"role": "learner"},
        "handling_path": handling_path,
        "component_fingerprint": component_fingerprint
        or {
            "stable_css_selector": f"a#{asset_id}",
            "template_id": "course-module-link",
            "bundle_name": "view.php",
            "controlled_dom_signature": f"sig-{asset_id}",
        },
        "updated_at": "2026-04-07T01:10:00Z",
    }
    if scope_reason is not None:
        payload["scope_reason"] = scope_reason
    return payload


def upsert_assets(client: TestClient, run_id: str, assets: list[dict]) -> None:
    response = client.post(
        "/assets/upsert",
        json={
            "run_id": run_id,
            "crawl_snapshot": {
                "entry_locator": "https://courses.example.com/course/view.php?id=88",
                "started_at": "2026-04-07T01:00:00Z",
                "completed_at": "2026-04-07T01:05:00Z",
                "visited_locators": ["https://courses.example.com/course/view.php?id=88"],
                "excluded_locators": [],
                "snapshot_metadata": {"asset_count": len(assets)},
            },
            "assets": assets,
        },
    )
    assert response.status_code == 201


def flow_by_type(flows: list[dict], flow_type: str) -> dict:
    for flow in flows:
        if flow["flow_type"] == flow_type:
            return flow
    raise AssertionError(f"missing flow_type={flow_type}")


def step_by_key(flow: dict, step_key: str) -> dict:
    for step in flow["steps"]:
        if step["step_key"] == step_key:
            return step
    raise AssertionError(f"missing step_key={step_key}")


def test_processes_upsert_builds_simple_course_flow(client: TestClient) -> None:
    run_id = build_run(client)
    upsert_assets(
        client,
        run_id,
        assets=[
            build_asset(
                asset_id="asset-page-10",
                asset_type="web_page",
                locator="https://courses.example.com/mod/page/view.php?id=10",
                shared_key="page-10",
                handling_path="mod/page",
            ),
        ],
    )

    response = client.post(
        "/processes/upsert",
        json={
            "run_id": run_id,
            "auth_context": {"role": "learner", "login_method": "username_password"},
            "crawl_graph": {
                "entry_locator": "https://courses.example.com/course/view.php?id=88",
                "nodes": [
                    {
                        "locator": "https://courses.example.com/login/index.php",
                        "page_type": "sign-in",
                        "title": "Login",
                    },
                    {
                        "locator": "https://courses.example.com/my/",
                        "page_type": "dashboard",
                        "title": "Dashboard",
                    },
                    {
                        "locator": "https://courses.example.com/course/view.php?id=88",
                        "page_type": "launch",
                        "title": "Course Home",
                    },
                    {
                        "locator": "https://courses.example.com/mod/page/view.php?id=10",
                        "asset_id": "asset-page-10",
                        "page_type": "content",
                        "title": "Lesson Page",
                    },
                ],
                "edges": [
                    {
                        "from_locator": "https://courses.example.com/login/index.php",
                        "to_locator": "https://courses.example.com/my/",
                        "transition_type": "navigate",
                    },
                    {
                        "from_locator": "https://courses.example.com/my/",
                        "to_locator": "https://courses.example.com/course/view.php?id=88",
                        "transition_type": "launch",
                    },
                    {
                        "from_locator": "https://courses.example.com/course/view.php?id=88",
                        "to_locator": "https://courses.example.com/mod/page/view.php?id=10",
                        "transition_type": "navigate",
                    },
                ],
            },
        },
    )

    assert response.status_code == 201
    flows = response.json()["flows"]
    assert len(flows) == 1
    flow = flow_by_type(flows, "learner_default")
    assert [step["step_key"] for step in flow["steps"]] == [
        "sign-in",
        "dashboard",
        "launch",
        "navigate",
        "attempt",
        "submit",
        "review",
    ]
    assert step_by_key(flow, "sign-in")["step_status"] == "present"
    assert step_by_key(flow, "dashboard")["step_status"] == "present"
    assert step_by_key(flow, "launch")["step_status"] == "present"
    assert step_by_key(flow, "navigate")["asset_id"] == "asset-page-10"
    assert step_by_key(flow, "attempt")["step_status"] == "missing"
    assert flow["flow_metadata"]["missing_steps"] == ["attempt", "submit", "review"]

    with client.app.state.session_factory() as session:
        persisted_flows = session.scalars(
            select(ProcessFlow).where(ProcessFlow.run_id == run_id),
        ).all()
        persisted_steps = session.scalars(
            select(ProcessFlowStep).where(ProcessFlowStep.run_id == run_id).order_by(ProcessFlowStep.step_order),
        ).all()

    assert len(persisted_flows) == 1
    assert len(persisted_steps) == 7


def test_processes_upsert_builds_quiz_flow(client: TestClient) -> None:
    run_id = build_run(client)
    upsert_assets(
        client,
        run_id,
        assets=[
            build_asset(
                asset_id="asset-quiz-20",
                asset_type="quiz_page",
                locator="https://courses.example.com/mod/quiz/view.php?id=20",
                shared_key="quiz-20",
                handling_path="mod/quiz",
            ),
        ],
    )

    response = client.post(
        "/processes/upsert",
        json={
            "run_id": run_id,
            "auth_context": {"role": "learner"},
            "crawl_graph": {
                "entry_locator": "https://courses.example.com/course/view.php?id=88",
                "nodes": [
                    {"locator": "https://courses.example.com/my/", "page_type": "dashboard"},
                    {"locator": "https://courses.example.com/course/view.php?id=88", "page_type": "launch"},
                    {
                        "locator": "https://courses.example.com/mod/quiz/view.php?id=20",
                        "asset_id": "asset-quiz-20",
                        "page_type": "quiz",
                        "title": "Quiz Launch",
                    },
                    {
                        "locator": "https://courses.example.com/mod/quiz/review.php?attempt=99",
                        "page_type": "review",
                        "title": "Review Results",
                    },
                ],
                "edges": [
                    {
                        "from_locator": "https://courses.example.com/course/view.php?id=88",
                        "to_locator": "https://courses.example.com/mod/quiz/view.php?id=20",
                        "transition_type": "navigate",
                    },
                    {
                        "from_locator": "https://courses.example.com/mod/quiz/view.php?id=20",
                        "to_locator": "https://courses.example.com/mod/quiz/review.php?attempt=99",
                        "transition_type": "submit",
                        "note": "Quiz submission complete.",
                    },
                ],
            },
        },
    )

    assert response.status_code == 201
    flows = response.json()["flows"]
    quiz_flow = flow_by_type(flows, "quiz_flow")
    assert step_by_key(quiz_flow, "launch")["asset_id"] == "asset-quiz-20"
    assert step_by_key(quiz_flow, "attempt")["step_status"] == "present"
    assert step_by_key(quiz_flow, "attempt")["asset_id"] == "asset-quiz-20"
    assert step_by_key(quiz_flow, "submit")["step_status"] == "present"
    assert step_by_key(quiz_flow, "submit")["note"] == "Quiz submission complete."
    assert step_by_key(quiz_flow, "review")["step_status"] == "present"
    assert step_by_key(quiz_flow, "review")["locator"] == "https://courses.example.com/mod/quiz/review.php?attempt=99"


def test_processes_upsert_builds_lti_flow_with_biodigital_note(client: TestClient) -> None:
    run_id = build_run(client)
    upsert_assets(
        client,
        run_id,
        assets=[
            build_asset(
                asset_id="asset-lti-30",
                asset_type="lti_launch",
                locator="https://courses.example.com/mod/lti/view.php?id=30",
                shared_key="lti-30",
                handling_path="mod/lti",
            ),
            build_asset(
                asset_id="asset-biodigital-1",
                asset_type="third_party_embed",
                locator="https://human.biodigital.com/widget?be=123",
                source_system="human.biodigital.com",
                shared_key="biodigital-1",
                handling_path="iframe:biodigital",
            ),
        ],
    )

    response = client.post(
        "/processes/upsert",
        json={
            "run_id": run_id,
            "auth_context": {"role": "learner"},
            "crawl_graph": {
                "entry_locator": "https://courses.example.com/course/view.php?id=88",
                "nodes": [
                    {"locator": "https://courses.example.com/my/", "page_type": "dashboard"},
                    {"locator": "https://courses.example.com/mod/lti/view.php?id=30", "page_type": "launch"},
                    {
                        "locator": "https://human.biodigital.com/widget?be=123",
                        "asset_id": "asset-biodigital-1",
                        "page_type": "content",
                    },
                ],
                "edges": [
                    {
                        "from_locator": "https://courses.example.com/mod/lti/view.php?id=30",
                        "to_locator": "https://human.biodigital.com/widget?be=123",
                        "transition_type": "navigate",
                    },
                ],
            },
        },
    )

    assert response.status_code == 201
    lti_flow = flow_by_type(response.json()["flows"], "lti_flow")
    assert step_by_key(lti_flow, "launch")["asset_id"] == "asset-lti-30"
    navigate_step = step_by_key(lti_flow, "navigate")
    assert navigate_step["asset_id"] == "asset-biodigital-1"
    assert "BioDigital" in navigate_step["note"]
    assert "cross-origin" in navigate_step["note"]


def test_processes_upsert_marks_missing_steps_without_failing(client: TestClient) -> None:
    run_id = build_run(client)
    upsert_assets(
        client,
        run_id,
        assets=[
            build_asset(
                asset_id="asset-page-11",
                asset_type="web_page",
                locator="https://courses.example.com/mod/page/view.php?id=11",
                shared_key="page-11",
                handling_path="mod/page",
            ),
        ],
    )

    response = client.post(
        "/processes/upsert",
        json={
            "run_id": run_id,
            "auth_context": {},
            "crawl_graph": {
                "entry_locator": "https://courses.example.com/course/view.php?id=88",
                "nodes": [
                    {
                        "locator": "https://courses.example.com/mod/page/view.php?id=11",
                        "asset_id": "asset-page-11",
                        "page_type": "content",
                    },
                ],
                "edges": [],
            },
        },
    )

    assert response.status_code == 201
    flow = flow_by_type(response.json()["flows"], "learner_default")
    assert step_by_key(flow, "sign-in")["step_status"] == "missing"
    assert step_by_key(flow, "dashboard")["step_status"] == "missing"
    assert step_by_key(flow, "attempt")["step_status"] == "missing"
    assert step_by_key(flow, "submit")["step_status"] == "missing"
    assert step_by_key(flow, "review")["step_status"] == "missing"
    assert flow["flow_metadata"]["missing_steps"] == ["sign-in", "dashboard", "attempt", "submit", "review"]
