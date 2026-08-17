from datetime import datetime, timezone
import shutil

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import Settings, get_settings
from app.core.errors import UserFacingError
from app.models.job import JobState, JobStatus
from app.services.job_store import JobStore
from app.services.processor import PresentationJobProcessor
from app.services.translation import get_translation_options, resolve_translation_profile
from app.services.tts import get_voice_availability
from app.services.validators import validate_languages, validate_upload_metadata

router = APIRouter()


def get_store(settings: Settings = Depends(get_settings)) -> JobStore:
    return JobStore(settings)


@router.get("/tts/voices/{language}")
def get_tts_voice(language: str, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    availability = get_voice_availability(settings, language)
    return {
        "provider": availability.provider,
        "language": availability.language,
        "available": availability.available,
        "voice_name": availability.voice_name,
        "message": availability.message,
    }


@router.get("/translation/options")
def get_translation_model_options(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {"options": get_translation_options(settings)}


@router.post("/jobs", response_model=JobStatus)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
    translation_profile: str = Form("local-primary"),
    settings: Settings = Depends(get_settings),
    store: JobStore = Depends(get_store),
) -> JobStatus:
    size = int(file.size or 0)
    try:
        validate_languages(source_language, target_language)
        validate_upload_metadata(file.filename or "", size, settings)
        translation_settings = resolve_translation_profile(settings, translation_profile)
        voice_status = get_voice_availability(settings, target_language)
        if not voice_status.available:
            raise UserFacingError("tts_voice_missing", voice_status.message)
    except UserFacingError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc

    status = store.create_job(
        file.filename or "presentation.pptx",
        source_language,
        target_language,
        translation_profile=translation_profile,
        translation_provider=translation_settings.translation_provider,
        translation_model=translation_settings.translation_model,
    )
    paths = store.paths(status.job_id)
    with paths.upload.open("wb") as destination:
        shutil.copyfileobj(file.file, destination)

    processor = PresentationJobProcessor(settings, store)
    background_tasks.add_task(processor.run, status.job_id)
    return status


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str, store: JobStore = Depends(get_store)) -> JobStatus:
    status = store.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "找不到這個工作，請重新上傳。"})
    if _is_expired_for_user(status):
        raise HTTPException(status_code=410, detail={"code": "expired", "message": "檔案已過期，請重新上傳。"})
    return status


@router.post("/jobs/{job_id}/cancel", response_model=JobStatus)
def cancel_job(job_id: str, store: JobStore = Depends(get_store)) -> JobStatus:
    status = store.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "找不到這個工作，請重新上傳。"})
    if status.state not in {JobState.pending, JobState.running}:
        return status
    return store.request_cancel(job_id)


@router.get("/jobs/{job_id}/download")
def download_job(job_id: str, store: JobStore = Depends(get_store)):
    status = store.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "找不到這個工作，請重新上傳。"})
    if status.state != JobState.completed:
        raise HTTPException(status_code=409, detail={"code": "not_ready", "message": "工作尚未完成，無法下載。"})
    if status.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail={"code": "expired", "message": "檔案已過期，請重新上傳。"})
    if not status.output_validated:
        raise HTTPException(status_code=409, detail={"code": "not_validated", "message": "輸出簡報尚未通過驗證。"})
    paths = store.paths(job_id)
    if not paths.output.exists():
        raise HTTPException(status_code=404, detail={"code": "missing_output", "message": "找不到輸出檔案。"})
    return FileResponse(
        path=paths.output,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=status.output_filename or "translated.pptx",
    )


def _is_expired_for_user(status: JobStatus) -> bool:
    if status.state in {JobState.pending, JobState.running}:
        return False
    return status.expires_at <= datetime.now(timezone.utc)
