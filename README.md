# Color Quantizer — PS1 Texture Tool

A lightweight desktop app for turning images into **PS1-style textures** for Blender. It reduces colors, emulates classic 15-bit color depth, applies ordered or error-diffusion dithering, and optionally downsizes with nearest-neighbor sampling. Settings are customizable, and batch processing is supported.

## Features

- Quantize to 2–256 colors with built-in presets: **PS1 Classic**, **PS1 Clean**, **PS1 Dithered**, **PS1 Extreme 4-bit**, and **Lo-Fi Modern**.
- Color depth: Off, 4-, 5-, 6-, or 8-bit per channel. The 5-bit option emulates PS1 15-bit color.
- Dithering: None, Bayer 2×2/4×4/8×8, and Floyd–Steinberg, with adjustable 0–200% strength.
- Resize using a maximum dimension, custom maximum, custom width × height, or exact stretch.
- Output as PNG, JPG, BMP, or TGA; JPG quality is configurable. PNG can optionally use indexed color.
- Edit palettes manually, preserve forced colors, and save/load palette or preset JSON files.
- Live before/after preview, batch processing, drag and drop, and a bilingual Indonesian/English UI.
- Lightweight preview processing; saving always uses the full-resolution source.

## Requirements

- Windows, macOS, or Linux with Python 3.10+ and Tk support.
- Dependencies are listed in `requirements.txt`.
- `tkinterdnd2` is optional; without it, use the **Open image** button instead of drag and drop.

## Run

On Windows, double-click `run.bat`. It checks for and installs the Python dependencies, then launches the app. You can also drop image files onto `run.bat`.

Or run manually:

```bash
python -m pip install -r requirements.txt
python color_quantizer.py
```

To open one or more images from the command line:

```bash
python color_quantizer.py path/to/image.png
```

## Usage

1. Open images with the button or drag and drop them into the app. Multiple files can be queued for batch processing.
2. Select a preset or customize the quantization, dithering, resize, and output options.
3. Choose **Process & save all** to process the queue, or **Save current result** for the selected image.
4. Select **Bahasa Indonesia** or **English** from the language selector in the header.

Output files are saved beside their input as `<name><suffix>.<extension>`. Existing output names are not overwritten; a number is appended instead.

## GitHub-ready project contents

```text
color_quantizer.py   Application source
requirements.txt     Python dependencies
run.bat              Windows launcher
build_exe.bat        PyInstaller build script
ColorQuantizer.spec  PyInstaller configuration
logo.jpg             App logo and window icon
fonts/               Bundled Barlow fonts and OFL license
demo/                Sample images
README.md            Project documentation
```

The `dist/` build output and generated files are intentionally not included in this source package. Build artifacts can be generated locally with `build_exe.bat` on Windows.

## Build a Windows executable

Install PyInstaller and run `build_exe.bat`. The default build uses folder mode for faster startup. Distribute the entire `dist/ColorQuantizer/` folder, not just the executable.

## Tests

Run the built-in self-test (it creates a temporary test directory):

```bash
python color_quantizer.py --selftest
```

## License

No project license has been added yet. Add a `LICENSE` file before publishing if you want to specify reuse terms. The bundled Barlow fonts have their own OFL license in `fonts/OFL.txt`.
