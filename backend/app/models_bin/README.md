# Bundled model files

## `face_detection_yunet_2023mar.onnx`

YuNet face detector, used by `app/image_processing/sample_validation.py` to refuse photos of
people before any analysis runs.

- Source: OpenCV Zoo — https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- Licence: MIT (OpenCV Zoo model licence for YuNet)
- Size: 232,589 bytes
- SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`

The hash is pinned in code; a file that doesn't match is refused (the gate then falls back to
the scikit-image LBP face cascade and logs an error).
