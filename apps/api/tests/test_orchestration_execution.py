from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jbl_audit_api.core.config import Settings
from jbl_audit_api.services.orchestration_execution import LocalBrowserWorkerBatchExecutor


def test_local_browser_worker_executor_disables_subprocess_timeout_when_configured_non_positive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    entrypoint = tmp_path / "run-tier1-batch.js"
    entrypoint.write_text("console.log('{}')", encoding="utf-8")

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        evidence_root_dir=tmp_path / "evidence",
        reports_root_dir=tmp_path / "reports",
        browser_worker_dir=tmp_path,
        browser_worker_entrypoint=entrypoint,
        browser_worker_timeout_seconds=0,
    )
    executor = LocalBrowserWorkerBatchExecutor(settings)
    captured: dict[str, object] = {}

    def fake_subprocess_run(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return SimpleNamespace(returncode=0, stdout='{"asset_results":[],"failures":[],"summary":{}}', stderr="")

    monkeypatch.setattr("jbl_audit_api.services.orchestration_execution.subprocess.run", fake_subprocess_run)

    batch = SimpleNamespace(task_contract={"assets": []}, viewport_matrix=())
    executor.execute_batch("run-1", batch)

    assert captured["timeout"] is None
