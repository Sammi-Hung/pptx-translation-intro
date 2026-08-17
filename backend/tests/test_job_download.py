from datetime import datetime, timedelta, timezone

import pytest

from app.api.routes import download_job
from app.core.config import Settings
from app.models.job import JobState
from app.services.job_store import JobStore


def test_unfinished_job_cannot_download(tmp_path) -> None:
    store = JobStore(Settings(storage_root=tmp_path))
    status = store.create_job("Training.pptx", "zh-TW", "en-US")
    with pytest.raises(Exception):
        download_job(status.job_id, store)


def test_expired_job_cannot_download(tmp_path) -> None:
    store = JobStore(Settings(storage_root=tmp_path))
    status = store.create_job("Training.pptx", "zh-TW", "en-US")
    status.state = JobState.completed
    status.output_validated = True
    status.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    store.save(status)
    with pytest.raises(Exception):
        download_job(status.job_id, store)

