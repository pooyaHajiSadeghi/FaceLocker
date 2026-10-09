"""One shared CPU pipeline for enrollment, preview and verification."""
from pathlib import Path
import os
import urllib.request
import cv2
from database import unit

MODELS = {'face_detection_yunet_2023mar.onnx': ('face_detection_yunet', 200_000),
          'face_recognition_sface_2021dec.onnx': ('face_recognition_sface', 30_000_000)}

def download_models(directory):
    directory = Path(directory)
    directory.mkdir(exist_ok=True)
    for name, (folder, size) in MODELS.items():
        target = directory / name
        if target.exists() and target.stat().st_size > size:
            try:
                if folder=='face_detection_yunet':
                    cv2.FaceDetectorYN.create(str(target),'',(640,480))
                else:
                    cv2.FaceRecognizerSF.create(str(target),'')
                continue
            except cv2.error:
                # Keep the bad model for diagnosis, then replace only this download.
                os.replace(target,target.with_suffix('.onnx.invalid'))
        temporary = target.with_suffix('.part')
        url = f'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/{folder}/{name}'
        print('Downloading', name, flush=True)
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if temporary.stat().st_size < size:
                raise RuntimeError('Incomplete model download.')
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    Pipeline(directory)
    print('Models ready.')

class Pipeline:
    def __init__(self, directory):
        directory = Path(directory)
        self.capture = None
        self.detector = cv2.FaceDetectorYN.create(str(directory/'face_detection_yunet_2023mar.onnx'), '', (640,480), 0.9, 0.3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(str(directory/'face_recognition_sface_2021dec.onnx'), '')

    def start(self, index):
        self.stop()
        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
            capture = cv2.VideoCapture(index, backend)
            if capture.isOpened():
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                ok, _ = capture.read()
                if ok:
                    self.capture = capture
                    return
            capture.release()
        raise RuntimeError('Webcam unavailable. Close other camera apps and check Windows camera permissions.')

    def stop(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def read(self):
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError('Webcam disconnected.')
        frame = cv2.resize(frame, (640,480))
        self.detector.setInputSize((640,480))
        _, faces = self.detector.detect(frame)
        results = []
        for face in ([] if faces is None else faces):
            box = tuple(int(v) for v in face[:4])
            feature = None
            if min(box[2:]) >= 80:
                feature = unit(self.recognizer.feature(self.recognizer.alignCrop(frame, face)))
            results.append((box, feature))
        return frame, results
