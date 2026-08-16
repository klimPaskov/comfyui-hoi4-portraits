# Output layout reference

All workflows write a full-resolution portrait, a game-size PNG, and a HOI4-ready DDS. Image-based workflows keep the input filename stem, while text-to-image uses `text_to_image`.

## RunPod folders

Batch inputs go in `/workspace/hoi4-portrait-runpod/input/`. Outputs use this structure:

```text
/workspace/hoi4-portrait-runpod/output/1024x1365/ — master PNGs
/workspace/hoi4-portrait-runpod/output/1024x1365/processed/ — prepared source PNGs
/workspace/hoi4-portrait-runpod/output/1024x1365/restored/ — restored source PNGs
/workspace/hoi4-portrait-runpod/output/1024x1365/<batch_name>/ — batch master PNGs
/workspace/hoi4-portrait-runpod/output/1024x1365/<batch_name>/processed/ — batch prepared PNGs
/workspace/hoi4-portrait-runpod/output/1024x1365/<batch_name>/restored/ — batch restored PNGs
/workspace/hoi4-portrait-runpod/output/156x210/ — game-size PNGs
/workspace/hoi4-portrait-runpod/output/156x210/dds/ — HOI4-ready DDS files
/workspace/hoi4-portrait-runpod/output/156x210/<batch_name>/ — batch game-size PNGs
/workspace/hoi4-portrait-runpod/output/156x210/<batch_name>/dds/ — batch HOI4-ready DDS files
```

Windows uses the input and output folders selected during installation. Manual and Comfy Cloud installations use the same subfolders under `ComfyUI/output/hoi4_portraits/`.

## Names and sizes

Source candidates append `_1`, `_2`, and `_3` to the input stem. Batch outputs use the selected `<batch_name>`; if it is blank, the workflow chooses the next free name: `batch_1`, `batch_2`, and so on. Text-to-image outputs use the stable `text_to_image` prefix. Numbered counters prevent repeated runs from overwriting existing portraits.

Master portraits are 1024×1365. Game portraits are 156×210 and use center cropping with Lanczos resampling; portraits are never stretched. Prepared and restored source images are saved separately in the 1024×1365 folders.

## DDS export

The DDS saver writes uncompressed 32-bit BGRA data with alpha in the A8R8G8B8/B8G8R8A8-style layout used by HOI4 portraits. Queueing a workflow executes every connected save branch automatically.
