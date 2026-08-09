import { app } from "../../scripts/app.js";

const downloads = [
  {
    folder: "diffusion_models",
    hint: "Pick one FLUX.2 model",
    files: [
      ["BF16 — best quality, 20+ GB VRAM", "https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/resolve/92196c8e11f7b6cf2b7493e037d8c5345c559216/flux-2-klein-9b.safetensors"],
      ["FP8 — 16–20 GB VRAM", "https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/902d9d510b51533e07729f19211414a3648b77d2/flux-2-klein-9b-fp8.safetensors"],
      ["GGUF Q4_K_M — 8–10 GB VRAM", "https://huggingface.co/drends/FLUX.2-klein-9B-GGUF/resolve/9d468c2918205cc55ebd7a09802dc64c225fb2a6/flux-2-klein-9b-Q4_K_M.gguf"],
      ["GGUF Q5_K_M — 10–14 GB VRAM", "https://huggingface.co/drends/FLUX.2-klein-9B-GGUF/resolve/9d468c2918205cc55ebd7a09802dc64c225fb2a6/flux-2-klein-9b-Q5_K_M.gguf"],
      ["GGUF Q6_K — 12–16 GB VRAM", "https://huggingface.co/drends/FLUX.2-klein-9B-GGUF/resolve/9d468c2918205cc55ebd7a09802dc64c225fb2a6/flux-2-klein-9b-Q6_K.gguf"],
      ["GGUF Q8_0 — 16+ GB VRAM", "https://huggingface.co/drends/FLUX.2-klein-9B-GGUF/resolve/9d468c2918205cc55ebd7a09802dc64c225fb2a6/flux-2-klein-9b-Q8_0.gguf"],
    ],
  },
  {
    folder: "text_encoders",
    files: [["Qwen3-8B-Q8_0.gguf", "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/6cfbfc7d8ab95bf485c79fcc40be60930d5b4c8c/Qwen3-8B-Q8_0.gguf"]],
  },
  {
    folder: "vae",
    files: [["flux2-vae.safetensors", "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/vae/flux2-vae.safetensors"]],
  },
  {
    folder: "loras",
    files: [
      ["HOI4 portrait LoRA — step 2500", "https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/resolve/001ab9fe6a795124432287125fb28c2b99b74f57/hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors"],
      ["Adonis Base", "https://huggingface.co/n8te0/adonis_flux2klein/resolve/515ecf66717d14309a055811b3d478cdfa59bbda/adonis_base.safetensors"],
      ["Adonis Refine", "https://huggingface.co/n8te0/adonis_flux2klein/resolve/515ecf66717d14309a055811b3d478cdfa59bbda/adonis_refine.safetensors"],
      ["Adonis Post", "https://huggingface.co/n8te0/adonis_flux2klein/resolve/515ecf66717d14309a055811b3d478cdfa59bbda/adonis_post.safetensors"],
    ],
  },
  {
    folder: "upscale_models",
    files: [["RealESRGAN_x2plus.pth", "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth"]],
  },
  {
    folder: "background_removal",
    files: [["birefnet.safetensors", "https://huggingface.co/Comfy-Org/BiRefNet/resolve/8fdc9d315889de96cc0c6269eeecd333e2727889/background_removal/birefnet.safetensors"]],
  },
  {
    folder: "detection",
    files: [
      ["mediapipe_face_fp32.safetensors", "https://huggingface.co/Comfy-Org/mediapipe/resolve/b98d050e8bf406f14f063bdba697e5b5391bbbf5/detection/mediapipe_face_fp32.safetensors"],
      ["face_detection_yunet_2023mar.onnx", "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"],
    ],
  },
];

function makeSetupCard() {
  const card = document.createElement("div");
  card.className = "hoi4-setup-guide";
  card.style.cssText = [
    "box-sizing:border-box",
    "height:100%",
    "overflow:hidden",
    "padding:18px 20px",
    "border:1px solid #8a684c",
    "border-radius:8px",
    "background:#3f2f24",
    "color:#f4e7d3",
    "font:17px/1.25 system-ui,sans-serif",
  ].join(";");

  const intro = document.createElement("div");
  intro.innerHTML = "<strong style='font-size:22px'>Put these in ComfyUI/models</strong><br><span style='color:#d9c3a8'>Choose one FLUX.2 model. Grab everything else.</span>";
  card.append(intro);

  const root = document.createElement("div");
  root.textContent = "📂 ComfyUI / 📂 models";
  root.style.cssText = "margin:14px 0 8px;font-weight:700;color:#ffd38f";
  card.append(root);

  for (const group of downloads) {
    const section = document.createElement("section");
    section.style.margin = "8px 0 0 18px";

    const heading = document.createElement("div");
    heading.textContent = `└─ 📂 ${group.folder}${group.hint ? ` — ${group.hint}` : ""}`;
    heading.style.cssText = "font-weight:700;color:#f4d6aa;margin-bottom:4px";
    section.append(heading);

    for (const [label, url] of group.files) {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `↳ ⬇️ ${label}`;
      link.title = url;
      link.style.cssText = "display:block;margin:2px 0 2px 22px;color:#9fd5ff;text-decoration:underline;text-underline-offset:2px";
      link.addEventListener("pointerdown", (event) => event.stopPropagation());
      link.addEventListener("click", (event) => event.stopPropagation());
      section.append(link);
    }
    card.append(section);
  }

  const footer = document.createElement("div");
  footer.textContent = "Restart ComfyUI after adding the files.";
  footer.style.cssText = "margin-top:12px;color:#d9c3a8";
  card.append(footer);
  card.addEventListener("pointerdown", (event) => event.stopPropagation());
  return card;
}

app.registerExtension({
  name: "hoi4_portraits.setup_guide",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "Hoi4SetupGuide") return;
    const previous = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      previous?.apply(this, arguments);
      this.addDOMWidget("setup_guide", "div", makeSetupCard(), {
        serialize: false,
        hideOnZoom: false,
      });
    };
  },
});
