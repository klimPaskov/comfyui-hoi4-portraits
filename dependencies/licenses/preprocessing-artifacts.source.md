# Preprocessing artifact verification record

Verification date: 2026-07-26. The entries below are pinned to primary project sources or the project authors' model repositories. No artifact was copied into this repository during verification.

| Dependency | Exact artifact | Revision | Size | SHA-256 | Primary source |
| --- | --- | --- | ---: | --- | --- |
| BiRefNet | `model.safetensors` | `e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4` | 444,473,596 | `9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154` | [ZhengPeng7/BiRefNet](https://huggingface.co/ZhengPeng7/BiRefNet) |
| DDColor | `pytorch_model.bin` | `060f67494e31883a4b13cb27f889f3154847ada4` | 911,914,869 | `d81711971ec59200da26d5e8a1afae8dd3778d495ea8ad7a7dadc769f403f7e7` | [piddnad/ddcolor_modelscope](https://huggingface.co/piddnad/ddcolor_modelscope) |
| YuNet | `face_detection_yunet_2023mar.onnx` | `47534e27c9851bb1128ccc0102f1145e27f23f98` | 232,589 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | [OpenCV Zoo model tree](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet) |
| MediaPipe Face Landmarker | `face_landmarker.task` | `float16/1`, generation `1683136941916318` | 3,758,596 | `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` | [Google-hosted official asset](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task) |
| SFace | `face_recognition_sface_2021dec.onnx` | `47534e27c9851bb1128ccc0102f1145e27f23f98` | 38,696,353 | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` | [OpenCV Zoo model tree](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface) |

The lock is still runtime-blocked until every mandatory file is restored to its exact `destination_path` and verified again locally. The optional Real-ESRGAN branch remains explicitly unselected; it is not used by the conservative default route.

BiRefNet license note: the pinned GitHub source is recorded as Apache-2.0 in the project lock, while the pinned Hugging Face snapshot exposes MIT metadata. This discrepancy is intentionally unresolved and remains a license gate; the trusted runtime-code files (`config.json`, `BiRefNet_config.py`, and `birefnet.py`) are separately pinned and checksum-verified when installed.
