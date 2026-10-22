# PyInstaller executes this file with Analysis/PYZ/EXE/COLLECT and SPECPATH injected.
from pathlib import Path
import json

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    copy_metadata,
)

root = Path(SPECPATH).parents[1]
entry = root / "src/datelier/__main__.py"
data = collect_data_files("datelier")
data += collect_data_files("imgui_bundle", includes=["assets/**", "LICENSE"])
# Provenance reads distribution versions; code collection alone omits metadata.
data += copy_metadata("datelier", recursive=True)
analysis = Analysis(
    [str(entry)],
    pathex=[str(root / "src")],
    binaries=collect_dynamic_libs("imgui_bundle"),
    datas=data,
    hiddenimports=["sounddevice", "torch", "torch._subclasses.fake_tensor"],
    excludes=["pytest", "IPython", "matplotlib", "pandas", "tkinter"],
    hookspath=[str(root / "scripts/release/hooks")],
    runtime_hooks=[str(root / "scripts/release/runtime_hook.py")],
    # Numba's cached kernels need real Python source locations in the bundle.
    module_collection_mode={"umap": "py", "pynndescent": "py"},
)
# CFFI loads PortAudio by SONAME; no ELF extension references it for PyInstaller
# to infer this alias automatically.
portaudio_name = next(
    target
    for target, _, _ in analysis.binaries
    if Path(target).name.startswith("libportaudio.so.")
)
if portaudio_name != "libportaudio.so.2":
    analysis.binaries.append(("libportaudio.so.2", portaudio_name, "SYMLINK"))
(root / "build/frozen/native-inputs.json").write_text(
    json.dumps([source for _, source, _ in analysis.binaries])
)
pyz = PYZ(analysis.pure)
app = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="datelier",
    console=True,
    strip=False,
    upx=False,
)
# Only the entry script differs: both executables use the same frozen modules,
# runtime hooks, and libraries. The helper is removed when packaging the archive.
verification_scripts = [
    item for item in analysis.scripts if Path(item[1]).resolve() != entry.resolve()
]
verification_scripts.append(
    ("__main__", str(root / "scripts/release/frozen_probe.py"), "PYSOURCE")
)
probe = EXE(
    pyz,
    verification_scripts,
    [],
    exclude_binaries=True,
    name="datelier-verify",
    console=True,
    strip=False,
    upx=False,
)
COLLECT(
    app,
    probe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="datelier",
)
