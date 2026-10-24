"""Optimus voice-generation tool adapter."""


def create_optimus_voice_track(
    text: str,
    voice: str = "af_nicole",
    speed: float = 0.92,
    pitch: int = 0,
    index_rate: float = 0.75,
) -> str:
    """Create a Kokoro source WAV and an Optimus RVC-converted WAV track."""
    try:
        from The_Voice.optimus_pipeline import (
            create_optimus_voice_track as create_track,
        )

        track = create_track(
            text,
            voice=voice,
            speed=speed,
            pitch=pitch,
            index_rate=index_rate,
        )
        return (
            "Created Optimus voice track.\n"
            f"Kokoro source WAV: {track['source_wav']}\n"
            f"Optimus RVC WAV: {track['optimus_wav']}\n"
            f"Settings: voice={track['voice']}, speed={track['speed']}, "
            f"pitch={track['pitch']}, index_rate={track['index_rate']}"
        )
    except Exception as error:  # noqa: BLE001 - tool errors are returned for model recovery
        return f"Could not create Optimus voice track: {type(error).__name__}: {error}"
