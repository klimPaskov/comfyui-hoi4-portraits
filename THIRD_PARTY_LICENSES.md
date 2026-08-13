# Third-party models and software

The MIT license in this repository applies only to project-owned material. It does not relicense the software and model files below. Before downloading, hosting, or using them, read the current upstream terms for your use case.

| Component | Upstream | Notes |
| --- | --- | --- |
| ComfyUI | [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | GPL-3.0 source project; not bundled here. The Windows wizard can download its official portable package after explicit confirmation. |
| 7-Zip command-line extractor | [7-zip.org](https://www.7-zip.org/) | LGPL/BSD/unRAR terms maintained upstream; downloaded temporarily by the Windows wizard to unpack the official ComfyUI portable archive, then removed. |
| ComfyUI-GGUF | [city96/ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | Node extension installed from a pinned revision when the GGUF variant is selected; not bundled here. |
| gguf text loader | [calcuis/gguf](https://github.com/calcuis/gguf) | Provides the exact `ClipLoaderGGUF` implementation serialized by the Adonis workflow. |
| RES4LYF | [ClownsharkBatwing/RES4LYF](https://github.com/ClownsharkBatwing/RES4LYF) | Provides the Base → Post restoration sampling used by Adonis. |
| Scale Image to Total Pixels Advanced | [BigStationW/ComfyUi-Scale-Image-to-Total-Pixels-Advanced](https://github.com/BigStationW/ComfyUi-Scale-Image-to-Total-Pixels-Advanced) | Provides the exact 1.7 MP, multiple-of-16 preprocessing node used by Adonis. |
| FLUX.2 Klein 9B distilled | [black-forest-labs/FLUX.2-klein-9B](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B), [FLUX.2-klein-9b-fp8](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8), [drends/FLUX.2-klein-9B-GGUF](https://huggingface.co/drends/FLUX.2-klein-9B-GGUF) | Gated full/FP8 model (accept the agreement); GGUF is not gated. Follow each model repository's license. |
| Qwen 3 8B Q8 GGUF encoder | [Qwen/Qwen3-8B-GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF) | Apache-2.0; the workflow pins `Qwen3-8B-Q8_0.gguf`. |
| FLUX.2 VAE | [Comfy-Org/flux2-klein-9B](https://huggingface.co/Comfy-Org/flux2-klein-9B) | Follow the source model card and file-specific upstream terms. |
| RealESRGAN x2plus | [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | Model and code terms are maintained upstream. |
| Adonis Base, Refine, and Post LoKrs | [n8te0/adonis_flux2klein](https://huggingface.co/n8te0/adonis_flux2klein) | Restoration adapters from the current upstream Base + Post workflow; Refine remains the supported alternative first pass. |
| HOI4 portrait LoRA | [Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora) | MIT; the project publishes this adapter. |
| BiRefNet | [Comfy-Org/BiRefNet](https://huggingface.co/Comfy-Org/BiRefNet) | Follow the model repository and original BiRefNet terms. |
| MediaPipe face detection | [Comfy-Org/mediapipe](https://huggingface.co/Comfy-Org/mediapipe) | Apache-2.0. |
| OpenCV and YuNet | [opencv/opencv](https://github.com/opencv/opencv), [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo) | Apache-2.0 software and model. |

Exact source revisions, filenames, and byte sizes are pinned in [`models.json`](models.json). No third-party weights are committed to this repository or bundled in its workflow release ZIP.

Hearts of Iron IV and related marks and game assets belong to Paradox Interactive. This independent community project is not affiliated with or endorsed by Paradox Interactive.
