"""Python/Linux codec, block-decoding and PortAudio feasibility evidence."""

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import cast

import numpy as np
import scipy
import soundfile as sf
from numpy.typing import NDArray


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, object] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "soundfile": sf.__version__,
        "libsndfile": sf.__libsndfile_version__,
        "scipy": scipy.__version__,
    }
    codecs: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="datelier-audio-probe-") as temporary:
        root = Path(temporary)
        rate = 24000
        tone = 0.25 * np.sin(2 * np.pi * 440 * np.arange(rate) / rate)
        samples = np.stack((tone, tone), axis=1)
        for name, subtype in (
            ("WAV", "PCM_16"),
            ("FLAC", "PCM_16"),
            ("OGG", "VORBIS"),
            ("MP3", "MPEG_LAYER_III"),
        ):
            path = root / ("tone." + name.lower())
            if name == "MP3":
                # Generate a reference input independently of libsndfile's
                # encoder. FFmpeg is a fixture tool, not an application decoder.
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-y",
                        "-i",
                        str(root / "tone.wav"),
                        "-codec:a",
                        "libmp3lame",
                        "-b:a",
                        "128k",
                        str(path),
                    ],
                    check=True,
                    timeout=15,
                )
            else:
                sf.write(path, samples, rate, format=name, subtype=subtype)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            started = perf_counter()
            info = sf.info(path)
            header_seconds = perf_counter() - started
            assert (info.frames, info.channels, info.samplerate) == (rate, 2, rate)
            frames = peak_block_bytes = 0
            square_sum = 0.0
            started = perf_counter()
            with sf.SoundFile(path) as stream:
                for raw in stream.blocks(
                    blocksize=4096, dtype="float64", always_2d=True
                ):
                    block = cast(NDArray[np.float64], raw)
                    frames += len(block)
                    peak_block_bytes = max(peak_block_bytes, block.nbytes)
                    square_sum += float(np.square(block).sum())
            rms = (square_sum / (frames * 2)) ** 0.5
            assert frames == rate and abs(rms - 0.25 / 2**0.5) < 0.015
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
            codecs.append(
                {
                    "format": name,
                    "subtype": info.subtype,
                    "frames": frames,
                    "rate": info.samplerate,
                    "channels": info.channels,
                    "rms": rms,
                    "header_seconds": header_seconds,
                    "decode_seconds": perf_counter() - started,
                    "peak_block_bytes": peak_block_bytes,
                    "source_preserved": True,
                }
            )
    report["codecs"] = codecs
    try:
        import sounddevice as sd

        report["sounddevice"] = sd.__version__
        report["portaudio"] = list(sd.get_portaudio_version())
        report["devices"] = [dict(device) for device in sd.query_devices()]
        report["default_device"] = list(sd.default.device)
        report["playback_verified"] = False
    except (OSError, RuntimeError) as error:
        report["device_error"] = str(error)
        report["playback_verified"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
