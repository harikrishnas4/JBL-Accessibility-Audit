from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jbl_audit_api.core.config import Settings
from jbl_audit_api.db import models  # noqa: F401
from jbl_audit_api.db.base import Base
from jbl_audit_api.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "api-test.db"
    settings = Settings(
        app_name="JBL WCAG Audit API",
        app_env="test",
        api_host="127.0.0.1",
        api_port=8000,
        database_url=f"sqlite:///{database_path}",
        reports_root_dir=tmp_path / "reports",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(app.state.engine)
