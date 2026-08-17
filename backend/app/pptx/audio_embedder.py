from pathlib import Path

from app.core.config import Settings
from app.core.errors import UserFacingError


class AudioEmbedder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def embed(self, pptx_path: Path, audio_files: dict[int, Path], output_path: Path) -> None:
        if self.settings.audio_embed_provider.lower() == "com":
            self._embed_with_powerpoint_com(pptx_path, audio_files, output_path)
        else:
            if pptx_path != output_path:
                output_path.write_bytes(pptx_path.read_bytes())

    def _embed_with_powerpoint_com(self, pptx_path: Path, audio_files: dict[int, Path], output_path: Path) -> None:
        try:
            import pythoncom
            import win32com.client
        except Exception as exc:
            raise UserFacingError("powerpoint_unavailable", "Microsoft PowerPoint 未安裝或無法啟動。") from exc

        app = None
        presentation = None
        try:
            pythoncom.CoInitialize()
            app = win32com.client.DispatchEx("PowerPoint.Application")
            app.Visible = True
            presentation = app.Presentations.Open(str(pptx_path.resolve()), WithWindow=False)
            for slide_number, audio_path in audio_files.items():
                slide = presentation.Slides(slide_number)
                self._remove_previous_narration(slide)
                shape = slide.Shapes.AddMediaObject2(
                    FileName=str(audio_path.resolve()),
                    LinkToFile=False,
                    SaveWithDocument=True,
                    Left=8,
                    Top=8,
                    Width=24,
                    Height=24,
                )
                shape.Name = f"TranslatedNarration_{slide_number:03d}"
                self._configure_playback(slide, shape)
            presentation.SaveAs(str(output_path.resolve()))
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError("audio_embed_failed", "音訊嵌入失敗。") from exc
        finally:
            if presentation is not None:
                try:
                    presentation.Close()
                except Exception:
                    pass
            if app is not None:
                try:
                    app.Quit()
                except Exception:
                    pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    @staticmethod
    def _remove_previous_narration(slide) -> None:
        for index in range(slide.Shapes.Count, 0, -1):
            shape = slide.Shapes(index)
            if str(shape.Name).startswith("TranslatedNarration_"):
                shape.Delete()

    @staticmethod
    def _configure_playback(slide, shape) -> None:
        try:
            play_settings = shape.AnimationSettings.PlaySettings
            play_settings.PlayOnEntry = True
            play_settings.HideWhileNotPlaying = True
            play_settings.LoopUntilStopped = False
            play_settings.PauseAnimation = False
            play_settings.StopAfterSlides = 1
            play_settings.RewindMovie = True
        except Exception:
            pass

        try:
            shape.MediaFormat.Volume = 0.8
        except Exception:
            pass

        # Modern PowerPoint often relies on a timeline media effect for
        # automatic playback. Keep the legacy PlaySettings above as a fallback.
        try:
            mso_anim_effect_media_play = 83
            mso_anim_trigger_with_previous = 2
            effect = slide.TimeLine.MainSequence.AddEffect(shape, mso_anim_effect_media_play)
            effect.Timing.TriggerType = mso_anim_trigger_with_previous
        except Exception:
            pass
