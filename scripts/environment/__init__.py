"""Real host capability probes, separate from injected native test devices.

Run ``uv run python -m scripts.environment.audio_codecs`` for codec fixtures,
audio_playback for a real output device, or scripts.environment.checkpoints
under ``uv run --extra checkpoints`` for the optional CPU runtime.
The codec probe needs FFmpeg for an independent MP3 fixture; real playback needs
Linux PortAudio and a usable output. Probes report capabilities without installing
system libraries or changing system output. Human hearing remains a separate
deferred check.
"""
