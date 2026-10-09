# Installation and Troubleshooting

## Supported configuration

Windows 11 x64, a working webcam, and internet access for initial setup. Source execution and local builds require Python 3.10 x64 with Python Launcher and Tcl/Tk. End users of a built EXE do not need to install Python manually.

## Executable setup

Open `FaceLocker.exe`. The setup window remains visible while it prepares the runtime and launches the application. It reuses compatible Python 3.10 x64 or downloads the pinned official Python 3.10.11 x64 installer, verifies its SHA-256, and installs a private per-user runtime. It creates an isolated environment, installs dependencies, and downloads YuNet and SFace models. The private installation does not add Python to PATH or request an all-users install.

| Path under `%LOCALAPPDATA%\FaceLocker` | Purpose |
| --- | --- |
| `app/` | Deployed application payload |
| `.venv/` | Managed Python environment |
| `runtime/` | Private Python when needed |
| `models/` | ONNX model files |
| `data/state.json` | Enrollments, administrator, folders, and settings |
| `logs/setup.log` | Setup and runtime diagnostics |
| `setup-ready.json` | Installation readiness metadata |

Models are stored separately from the virtual environment. Healthy daily launches do not invoke package installation or download models. Repair or dependency changes may need internet. The Python fallback version is a pinned installer baseline, not a claim about the latest Python release.

## Source and build commands

Extract every repository file before running scripts; paths with spaces are supported. From the project root:

```bat
scripts\run.bat
scripts\build_exe.bat
```

The first command runs source mode. The second builds `dist\FaceLocker.exe` and logs to `logs\build.log`. The build console remains open so failures can be read. Do not move individual scripts out of their folders.

A GitHub build is available under **Actions > Build Windows EXE > Run workflow**. Download the artifact, extract it, and open the EXE on Windows.

## Upgrades and backups

Close FaceLocker before upgrading. Back up `%LOCALAPPDATA%\FaceLocker\data` and extract the complete new source into a separate directory. Source mode and EXE mode share this managed state; upgrades preserve it.

A fresh managed installation can copy adjacent `data/state.json` or legacy `data/people.json`. Existing managed data is never overwritten automatically. **Admin > Import previous database** accepts legacy `people.json`; a complete current-state transfer requires copying the data folder while the application is closed. Original migration files are preserved.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Build fails | Read `logs\build.log`; confirm Python 3.10 x64, Launcher, Tcl/Tk, and internet access. |
| Setup fails | Read `%LOCALAPPDATA%\FaceLocker\logs\setup.log`, address the reported download or installation error, and use Retry. |
| Process runs without a visible window | Try a second launch to restore the existing window. If an older release is stuck, end only the process whose command line identifies FaceLocker, then launch the updated version. |
| Runtime exits | Close FaceLocker and run `scripts\diagnose.bat`; inspect `%LOCALAPPDATA%\FaceLocker\logs\diagnostic.log`. |
| Webcam cannot open | Check Windows camera permission, close other camera applications, and verify the selected camera index. |
| Old camera cannot authorize a setting change | Close the app and correct `camera_index` in the managed `data\state.json`, then relaunch. |
| Hidden folder remains visible | Turn off Explorer **View > Show > Hidden items**. Hidden status does not deny access. |
| Some folders fail in a batch | Read the per-folder report and verify Windows permissions. Successful changes remain applied. |

The updated launcher waits for a mapped, viewable application window before reporting readiness. Startup times out after 45 seconds and terminates only its owned child process before offering a retry. The main UI does not withdraw itself before entering the Tk event loop. Native Windows focus and EXE behavior should still be verified on the target machine.
