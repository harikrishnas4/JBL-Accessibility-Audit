from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from jbl_audit_api.core.config import Settings
from jbl_audit_api.repositories.assets import AssetRepository
from jbl_audit_api.repositories.auth_profiles import AuthProfileRepository
from jbl_audit_api.repositories.classifications import AssetClassificationRepository
from jbl_audit_api.repositories.defects import DefectRepository
from jbl_audit_api.repositories.findings import FindingRepository
from jbl_audit_api.repositories.orchestration import OrchestrationRepository
from jbl_audit_api.repositories.processes import ProcessRepository
from jbl_audit_api.repositories.reports import ReportRepository
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.repositories.schemas import SchemaRegistryRepository
from jbl_audit_api.repositories.third_party_evidence import ThirdPartyEvidenceRepository
from jbl_audit_api.services.assets import AssetService
from jbl_audit_api.services.auth_profiles import AuthProfileService
from jbl_audit_api.services.classifications import AssetClassificationService
from jbl_audit_api.services.findings import FindingService
from jbl_audit_api.services.normalization import NormalizationService
from jbl_audit_api.services.orchestration import OrchestrationService
from jbl_audit_api.services.orchestration_dispatcher import LocalInProcessDispatcher, LocalTaskDispatcher
from jbl_audit_api.services.orchestration_execution import (
    DeterministicNoopTier1BatchExecutor,
    FindingResultSink,
    FindingServiceResultSink,
    LocalBrowserWorkerBatchExecutor,
    Tier1BatchExecutor,
)
from jbl_audit_api.services.processes import ProcessService
from jbl_audit_api.services.reporting import LocalReportStorageAdapter, ReportingService
from jbl_audit_api.services.runs import RunService
from jbl_audit_api.services.schemas import SchemaRegistryService


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_run_repository(session: Session = Depends(get_db_session)) -> RunRepository:
    return RunRepository(session)


def get_orchestration_repository(
    session: Session = Depends(get_db_session),
) -> OrchestrationRepository:
    return OrchestrationRepository(session)


def get_asset_repository(session: Session = Depends(get_db_session)) -> AssetRepository:
    return AssetRepository(session)


def get_asset_classification_repository(
    session: Session = Depends(get_db_session),
) -> AssetClassificationRepository:
    return AssetClassificationRepository(session)


def get_third_party_evidence_repository(
    session: Session = Depends(get_db_session),
) -> ThirdPartyEvidenceRepository:
    return ThirdPartyEvidenceRepository(session)


def get_asset_classification_service(
    repository: AssetClassificationRepository = Depends(get_asset_classification_repository),
    evidence_repository: ThirdPartyEvidenceRepository = Depends(get_third_party_evidence_repository),
) -> AssetClassificationService:
    return AssetClassificationService(repository, evidence_repository)


def get_finding_repository(session: Session = Depends(get_db_session)) -> FindingRepository:
    return FindingRepository(session)


def get_defect_repository(session: Session = Depends(get_db_session)) -> DefectRepository:
    return DefectRepository(session)


def get_report_repository(session: Session = Depends(get_db_session)) -> ReportRepository:
    return ReportRepository(session)


def get_reporting_service(
    settings: Settings = Depends(get_app_settings),
    repository: ReportRepository = Depends(get_report_repository),
) -> ReportingService:
    return ReportingService(repository, LocalReportStorageAdapter(settings.reports_root_dir))


def get_normalization_service(
    repository: DefectRepository = Depends(get_defect_repository),
    run_repository: RunRepository = Depends(get_run_repository),
    report_service: ReportingService = Depends(get_reporting_service),
) -> NormalizationService:
    return NormalizationService(repository, run_repository, report_service=report_service)


def get_finding_service(
    repository: FindingRepository = Depends(get_finding_repository),
    run_repository: RunRepository = Depends(get_run_repository),
    normalization_service: NormalizationService = Depends(get_normalization_service),
) -> FindingService:
    return FindingService(repository, run_repository, normalization_service)


def get_tier1_batch_executor(
    settings: Settings = Depends(get_app_settings),
) -> Tier1BatchExecutor:
    if settings.app_env == "test":
        return DeterministicNoopTier1BatchExecutor()
    return LocalBrowserWorkerBatchExecutor(settings)


def get_finding_result_sink(
    finding_service: FindingService = Depends(get_finding_service),
) -> FindingResultSink:
    return FindingServiceResultSink(finding_service)


def get_local_task_dispatcher(
    executor: Tier1BatchExecutor = Depends(get_tier1_batch_executor),
    result_sink: FindingResultSink = Depends(get_finding_result_sink),
) -> LocalTaskDispatcher:
    return LocalInProcessDispatcher(executor, result_sink)


def get_orchestration_service(
    repository: OrchestrationRepository = Depends(get_orchestration_repository),
    dispatcher: LocalTaskDispatcher = Depends(get_local_task_dispatcher),
) -> OrchestrationService:
    return OrchestrationService(repository, dispatcher=dispatcher)


def get_run_service(
    repository: RunRepository = Depends(get_run_repository),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> RunService:
    return RunService(repository, orchestration_service)


def get_process_repository(session: Session = Depends(get_db_session)) -> ProcessRepository:
    return ProcessRepository(session)


def get_process_service(repository: ProcessRepository = Depends(get_process_repository)) -> ProcessService:
    return ProcessService(repository)


def get_asset_service(
    repository: AssetRepository = Depends(get_asset_repository),
    run_repository: RunRepository = Depends(get_run_repository),
    classification_service: AssetClassificationService = Depends(get_asset_classification_service),
    normalization_service: NormalizationService = Depends(get_normalization_service),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> AssetService:
    return AssetService(
        repository,
        run_repository,
        classification_service,
        normalization_service,
        orchestration_service,
    )


def get_auth_profile_repository(
    session: Session = Depends(get_db_session),
) -> AuthProfileRepository:
    return AuthProfileRepository(session)


def get_auth_profile_service(
    repository: AuthProfileRepository = Depends(get_auth_profile_repository),
    run_repository: RunRepository = Depends(get_run_repository),
) -> AuthProfileService:
    return AuthProfileService(repository, run_repository)


def get_schema_registry_repository(
    session: Session = Depends(get_db_session),
) -> SchemaRegistryRepository:
    return SchemaRegistryRepository(session)


def get_schema_registry_service(
    repository: SchemaRegistryRepository = Depends(get_schema_registry_repository),
) -> SchemaRegistryService:
    return SchemaRegistryService(repository)
