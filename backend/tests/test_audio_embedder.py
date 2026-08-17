from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import UserFacingError
from app.pptx.audio_embedder import AudioEmbedder


def test_powerpoint_com_error_is_user_facing_and_closes(mocker, tmp_path: Path) -> None:
    win32com = mocker.Mock()
    win32com.client = mocker.Mock()
    mocker.patch.dict("sys.modules", {"pythoncom": mocker.Mock(), "win32com": win32com, "win32com.client": win32com.client})
    import win32com.client

    app = mocker.Mock()
    presentation = mocker.Mock()
    app.Presentations.Open.side_effect = RuntimeError("boom")
    win32com.client.DispatchEx.return_value = app

    embedder = AudioEmbedder(Settings(audio_embed_provider="com"))
    with pytest.raises(UserFacingError) as exc:
        embedder.embed(tmp_path / "in.pptx", {}, tmp_path / "out.pptx")
    assert exc.value.code == "audio_embed_failed"
    app.Quit.assert_called_once()
    presentation.Close.assert_not_called()
