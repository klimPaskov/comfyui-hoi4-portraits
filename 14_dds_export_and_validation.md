# DDS Export and Validation

## Gate

DDS conversion is forbidden before the selected candidate has independent PASS for identity, style, masks, and provenance.

## Final PNG contract

- width 156
- height 210
- lossless PNG
- sRGB or the verified project color space
- no unintended transparency
- no channel swap
- native-size inspection saved
- 4x nearest-neighbor inspection saved

## Current project precedent captured from uploaded sources

The uploaded Chaos Redux asset skill describes an uncompressed 32-bit BGRA style DDS contract:

- magic: `DDS `
- header size: 124
- total header bytes: 128 including magic
- pixel format size: 32
- pixel format flags: 65
- FourCC: 0
- RGB bit count: 32
- red mask: `0x00FF0000`
- green mask: `0x0000FF00`
- blue mask: `0x000000FF`
- alpha mask: `0xFF000000`
- caps texture: `0x1000`
- one image level unless a live precedent proves a different mipmap policy

For 156 by 210 uncompressed 4-byte pixels, expected file size is:

`128 + 156 * 210 * 4 = 131168 bytes`

This is a planning precedent, not final proof. The implementation must inspect the current Chaos Redux converter and current vanilla portrait DDS files before locking it.

## Standalone converter

Implement:

- a Python library
- a CLI under `scripts/convert/`
- unit tests with known-good byte fixtures
- a decoder for round-trip verification

The converter reads the final PNG, validates dimensions and mode, applies the exact verified channel ordering, writes the legacy DDS header and pixels, closes and reopens the file, then validates it.

Do not depend on Photoshop, GIMP, or manual export.

## Validation checks

### Header

- magic bytes
- header sizes
- flags
- width and height
- pitch or linear size according to precedent
- pixel format flags
- bit count
- channel masks
- caps
- mipmap count
- no unexpected DX10 header

### Pixel data

- expected file size
- successful decode through the project decoder
- successful decode through an independent library when available
- exact dimensions
- no all-black or all-transparent image
- channel sanity using known color patches
- alpha behavior matches precedent
- decoded RGB pixels equal the final PNG within the exact channel and alpha conversion rule

### Visual

Create a sheet showing:

- final PNG at native size
- decoded DDS at native size
- absolute pixel difference
- 4x nearest-neighbor versions

Required result is pixel equality after accounting for the defined channel representation. Any unexplained pixel difference fails.

## Chaos Redux route

When the live repository is available:

1. inspect `.agents/skills/chaos-redux-event-assets/tools/convert_to_dds.py`
2. inspect its tests and validation rules
3. inspect at least three current vanilla or live project portrait DDS headers
4. compare output against the standalone converter
5. reuse the repository converter when it meets this contract
6. keep the standalone validator as an independent oracle

## Generic route

Package the converter in the standalone project. Generic integrations call it through a stable CLI and receive JSON output with paths, dimensions, header fields, pixel comparison result, and SHA-256.

## Failure behavior

A DDS failure returns exit code 50. The accepted candidate remains in `candidates/` for diagnosis, but `final_png` and `final_dds` in the job output stay null until the complete finalization stage succeeds atomically.
