# GitHub Repository Setup

## Suggested repository metadata

**Repository name:** `facelocker`

**Project title:** FaceLocker — Local Biometric Verification for Windows Folder Visibility Control

**Description:** Windows 11 desktop application for local face-verified folder visibility management, with batch operations, administrator enrollment, inline webcam verification, and managed Python 3.10 setup.

**Topics:**

```text
python windows11 desktop-application computer-vision opencv face-recognition
face-detection yunet sface onnx customtkinter biometric-verification
folder-management pyinstaller
```

**Developer:** Pooya Haji Sadeghi

**Technical keywords:** local inference, face embeddings, cosine similarity, biometric verification, administrator enrollment, batch folder operations, Win32 file attributes, managed runtime provisioning, single-instance coordination, startup readiness, atomic JSON persistence.

## Upload the complete project

1. Extract the project archive.
2. Create an empty GitHub repository named `facelocker`. Do not initialize a second README or license.
3. Upload the contents of the extracted `FaceLocker_GitHub_Ready` folder to the repository root. `README.md`, `src`, `scripts`, `requirements`, `tests`, `docs`, and `.github` belong at the root.
4. Include `.gitignore` and `.gitattributes`. Do not upload the ZIP as the only repository file.
5. Add the description and topics above in the repository's About settings.
6. Open the README to confirm images and the Mermaid workflow render.
7. Use **Actions > Build Windows EXE > Run workflow** to build an executable. Download and test it on Windows 11 before distributing it.

Git handles hidden repository configuration files more reliably than selecting folders in a browser. From PowerShell in the extracted project directory:

```powershell
git init
git add .
git status
git commit -m "Initial release of FaceLocker"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/facelocker.git
git push -u origin main
```

Replace `YOUR_GITHUB_USERNAME` with your actual account. The commands are provided for you to execute; this package does not create or publish a repository.

## Included and excluded files

The repository includes source, documentation, tests, build automation, UI previews, and the three final project posters. It excludes personal enrollment databases, runtime environments, downloaded models, logs, build intermediates, and compiled output. Existing tracked files are not removed by `.gitignore`; review `git status` before committing any changes from an existing working copy.

## Release packaging

Publish `dist\FaceLocker.exe` as an asset of a GitHub release after testing it. The launcher needs internet for first setup and manages dependencies locally. Do not describe it as a fully offline first-run installer. Keep the source license with distributions and review upstream dependency/model licenses.
