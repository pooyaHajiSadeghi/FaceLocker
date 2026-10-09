# Architecture and Verification

## Runtime boundaries

The packaged executable is a windowed setup launcher. It deploys Python application modules as a payload and runs them through a managed Python 3.10 x64 environment. OpenCV and NumPy are installed into that environment during setup rather than bundled into the launcher executable.

`bootstrap.py` fingerprints the payload, provisions or reuses the runtime, deploys modules, and validates models. `launcher.py` presents progress and errors. `runtime_entry.py` starts the application with unbuffered diagnostics and fault reporting. `window_lifecycle.py` acknowledges readiness only after the application window is viewable. Single-instance coordination is implemented in `instance.py`.

## Recognition pipeline

1. Capture frames using the selected webcam; Windows capture attempts DirectShow before MSMF.
2. Detect faces with YuNet through OpenCV `FaceDetectorYN`.
3. Reject faces whose smaller bounding-box dimension is below 80 pixels for recognition.
4. Align and crop each face with SFace `FaceRecognizerSF.alignCrop`.
5. Extract and normalize a 128-dimensional feature vector.
6. Compare cosine scores against stored samples, average up to three best scores per identity, and select the highest-ranked identity.
7. Reject the result if it is below the configured threshold or insufficiently separated from the runner-up.

Default threshold: 0.45. Default ambiguity margin: 0.05. Default enrollment count: 10 samples. Scores measure similarity and must not be presented as identity probabilities.

## Authorization and folder execution

A folder operation captures an immutable job list before verification. Approval requires exactly one face recognized as the configured administrator across eight consecutive accepted observations spanning at least 1.2 seconds. A failed observation resets progress; the session expires after 30 seconds.

The approval is consumable once and bound to the captured operation. Entering Admin does not bypass fresh verification for hide/unhide batches. Cancellation and pre-approval failures do not execute jobs.

Execution revalidates paths and uses Win32 directory attributes. It preserves unrelated attribute bits and updates only Hidden. Per-folder errors are reported independently; the batch has no rollback transaction. Conflicting hide-parent/unhide-child requests and protected or redirected paths are rejected.

## Persistence

Versioned JSON stores normalized enrollment vectors, owner, folder paths, camera and matching configuration, and theme. State writes use temporary files and atomic replacement. This protects against incomplete writes; it does not encrypt the database. Legacy formats can be migrated or imported.

## Operational limits

There is one authorized administrator at a time, although multiple identities can be enrolled and labeled. Multiple faces cannot approve a protected operation. There is no liveness detector. An attacker with access to local state can alter it, and Windows users can reveal Hidden folders independently of FaceLocker. Slow processors and remote folders may cause UI delays because inference and attribute reads run on the UI thread.

## Model provenance

Model identifiers and download URLs are defined in `src/vision.py` and originate from the OpenCV Zoo YuNet and SFace model directories. Model setup uses download completion, size checks, and OpenCV loading checks; model downloads are not protected by a pinned model SHA-256. The fallback Python installer separately uses a pinned SHA-256. Third-party model and package licenses remain applicable.
