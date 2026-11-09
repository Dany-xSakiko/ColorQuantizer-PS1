#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Color Quantizer - PS1 Texture Tool
==================================

A desktop GUI for converting images into PS1-style textures with limited
palettes, selectable per-channel color depth, Bayer/Floyd-Steinberg dithering,
and nearest-neighbor resizing. Supports customizable presets, palette editing,
forced colors, batch processing, PNG/JPG/BMP/TGA output, and Indonesian/English
UI labels.

Usage:
    python color_quantizer.py                 # open the GUI
    python color_quantizer.py image.png       # open the GUI and load an image
    python color_quantizer.py --selftest      # run the test suite

Requirements: Python 3.10+, Pillow, numpy, and optional tkinterdnd2 for drag
and drop support.
"""

import os
import re
import sys
import json
import math
import threading
import traceback

import numpy as np
from PIL import Image, ImageDraw, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except Exception:  # pragma: no cover - drag-drop opsional
    _HAS_DND = False
    TkinterDnD = None
    DND_FILES = None

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga", ".tif", ".tiff", ".webp"}
MAX_UNIQUE_FOR_PALETTE = 150_000  # subsample kalau unique colors kebanyakan (cepat & cukup)

# ---- Sakiko Noir design tokens (terinspirasi sakiko.my.id) ----------------
# "High-Contrast Monochrome Noir - Industrial Grotesk": zero gradients,
# zero shadows at rest, zero thin rules. Palette: dark zinc layers + white ink.
C = {
    "bg":        "#09090b",  # --bg
    "surface":   "#131316",  # --surface (card)
    "raised":    "#1c1c21",  # --surface-raised (control bg)
    "highlight": "#282830",  # --surface-highlight (hover)
    "ink":       "#ffffff",  # --ink        (primary text)
    "muted":     "#d4d4d8",  # --muted      (secondary text)
    "dim":       "#b4b4bb",  # --dim        (disabled/hint)
    "accent":    "#ffffff",  # --accent     (primary button bg)
    "accent_ink": "#09090b",  # --accent-ink
}

# Font: "Barlow Condensed Black" buat display, "Barlow" buat body.
# Fallback ke Segoe UI kalau font nggak ada. Di-resolve di apply_style().
_DISPLAY_FONT = ("Segoe UI", 20, "bold")
_SECTION_FONT = ("Segoe UI", 9, "bold")
_BODY_FONT = ("Segoe UI", 9)
_UI_FONT = ("Segoe UI", 9)
_MONO_FONT = ("Consolas", 7)

_ttk_style = None  # cache instance

# UI translations are keyed by the Indonesian source strings so settings and
# processing values remain language-independent.
_UI_EN = {
    "GAMBAR": "IMAGE", "Buka gambar...": "Open image...",
    "...atau drag & drop gambar ke window ini": "...or drag & drop images here",
    "...atau pakai tombol 'Buka gambar' (install tkinterdnd2 untuk drag-drop)": "...or use Open image (install tkinterdnd2 for drag & drop)",
    "Lepaskan untuk load gambar!": "Drop to load images!", "Bersihkan list": "Clear list",
    "PRESET (satu klik)": "PRESETS (one click)", "Terapkan": "Apply",
    "Simpan preset...": "Save preset...", "Muat preset...": "Load preset...",
    "PENGATURAN KUANTISASI": "QUANTIZATION SETTINGS", "Jumlah warna:": "Colors:",
    "Color depth:": "Color depth:", "Dithering:": "Dithering:", "Strength:": "Strength:",
    "Resize (sebelum kuantisasi):": "Resize (before quantization):",
    "Output indexed PNG (mode P)": "Indexed PNG output (P mode)", "OUTPUT": "OUTPUT",
    "Suffix:": "Suffix:", "Format:": "Format:", "Kualitas JPG:": "JPEG quality:",
    "(lossy - tinggi = file besar)": "(lossy - higher = larger file)",
    "Nama file: <nama><suffix>.<ext>": "Filename: <name><suffix>.<ext>",
    "Proses & simpan semua (0)": "Process & save all (0)", "Simpan hasil ini...": "Save current result...",
    "PALETTE": "PALETTE", "Simpan palette": "Save palette", "Muat palette": "Load palette",
    "Pakai palette otomatis": "Use automatic palette", "Mode edit palette (klik = ganti warna)": "Edit palette mode (click to change colors)",
    "Tambah warna...": "Add color...", "Warna wajib...": "Forced colors...",
    "ORIGINAL": "ORIGINAL", "HASIL KUANTISASI": "QUANTIZED RESULT",
    "PALETTE (klik swatch = copy hex / ganti warna di mode edit)": "PALETTE (click swatch to copy hex / edit color)",
    "Copy semua hex": "Copy all hex", "Palette: otomatis (dari gambar)": "Palette: automatic (from image)",
    "Belum ada gambar": "No image loaded", "Siap. Buka gambar atau drag & drop ke window ini.": "Ready. Open or drag & drop images into this window.",
    "None (bersih)": "None (clean)", "Original (tanpa resize)": "Original (no resize)",
    "Max 512 (jaga rasio)": "Max 512 (preserve aspect ratio)", "Max 256 (jaga rasio)": "Max 256 (preserve aspect ratio)",
    "Max 128 (jaga rasio)": "Max 128 (preserve aspect ratio)", "Max 64 (jaga rasio)": "Max 64 (preserve aspect ratio)",
    "Custom: max N...": "Custom: max N...", "Custom: W x H...": "Custom: W x H...",
    "Exact 256x256 (stretch)": "Exact 256x256 (stretch)", "Exact 128x128 (stretch)": "Exact 128x128 (stretch)",
    "Exact 64x64 (stretch)": "Exact 64x64 (stretch)",
    "Bayer 2x2 (ordered)": "Bayer 2x2 (ordered)", "Bayer 4x4 (ordered)": "Bayer 4x4 (ordered)",
    "Bayer 8x8 (ordered)": "Bayer 8x8 (ordered)", "Floyd-Steinberg (error diffusion)": "Floyd-Steinberg (error diffusion)",
    "Off (24-bit)": "Off (24-bit)", "4-bit/ch (12-bit)": "4-bit/channel (12-bit)",
    "5-bit/ch (15-bit PS1)": "5-bit/channel (15-bit PS1)", "6-bit/ch (18-bit)": "6-bit/channel (18-bit)",
    "8-bit/ch (24-bit)": "8-bit/channel (24-bit)",
    "Buka gambar": "Open image", "Pilih gambar": "Select images",
    "Semua file": "All files", "Simpan preset": "Save preset",
    "Nama preset:": "Preset name:", "Muat preset JSON": "Load preset JSON",
    "JSON preset": "Preset JSON", "JSON palette": "Palette JSON",
    "Simpan palette": "Save palette", "Muat palette JSON": "Load palette JSON",
    "Ganti warna": "Change color", "Tambah warna ke palette": "Add color to palette",
    "Warna wajib (selalu dipertahankan)": "Forced color (always preserved)",
    "Custom resize": "Custom resize", "Maksimum sisi terpanjang (px):": "Maximum longest side (px):",
    "Ukuran WxH (contoh 96x128):": "Size WxH (e.g. 96x128):",
    "PS1 Classic": "PS1 Classic", "PS1 Clean": "PS1 Clean",
    "PS1 Dithered": "PS1 Dithered", "PS1 Extreme 4-bit": "PS1 Extreme 4-bit",
    "Lo-Fi Modern": "Lo-Fi Modern",
    "Proses & simpan semua": "Process & save all", "Simpan hasil ini...": "Save current result...",
    "Kuantisasi": "Quantization", "Kuantisasi selesai": "Quantization complete",
    "Palette termuat": "Palette loaded", "Palette dibersihkan.": "Palette cleared.",
    "Minimal palette harus ada 1 warna.": "The palette must contain at least one color.",
    "Mode edit palette ON - klik swatch untuk ganti warna, klik kanan untuk hapus.": "Palette edit mode ON - click a swatch to change it, right-click to remove it.",
    "Mode edit palette OFF - klik swatch untuk copy hex.": "Palette edit mode OFF - click a swatch to copy its hex value.",
    "Belum ada palette untuk disimpan.": "There is no palette to save.",
    "Belum ada gambar untuk disimpan.": "There is no image to save.",
    "Belum ada gambar di list.": "There are no images in the list.",
    "Sibuk - tunggu proses sekarang selesai dulu.": "Busy - wait for the current process to finish.",
    "Output indexed": "Indexed output",
    "PALETTE (klik swatch = copy hex / ganti warna di mode edit)": "PALETTE (click a swatch to copy hex / edit color)",
    "Palette: otomatis (dari gambar)": "Palette: automatic (from image)",
    "Mode edit palette (klik = ganti warna)": "Edit palette mode (click to change color)",
    "Resize (sebelum kuantisasi):": "Resize (before quantization):",
    "Pakai palette otomatis": "Use automatic palette",
    "Preset (satu klik)": "Presets (one click)",
    "...atau pakai tombol 'Buka gambar' (install tkinterdnd2 untuk drag-drop)": "...or use Open image (install tkinterdnd2 for drag and drop)",
    "Mode edit palette ON - klik swatch untuk ganti warna, klik kanan untuk hapus.": "Palette edit mode ON - click a swatch to change it, right-click to remove it.",
}


def _resource_dir():
    """Folder resource (fonts/) - jalan di source maupun EXE PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "fonts")


def _register_bundled_fonts():
    """Daftarkan Barlow/Barlow Condensed lokal ke proses ini saja (FR_PRIVATE).

    Nggak install ke sistem, nggak butuh admin. Return True kalau minimal
    satu font berhasil dimuat.
    """
    if sys.platform != "win32":
        return False
    folder = _resource_dir()
    if not os.path.isdir(folder):
        return False
    loaded = False
    try:
        import ctypes
        FR_PRIVATE = 0x10
        for name in sorted(os.listdir(folder)):
            if not name.lower().endswith((".ttf", ".otf")):
                continue
            try:
                if ctypes.windll.gdi32.AddFontResourceExW(
                        os.path.join(folder, name), FR_PRIVATE, 0):
                    loaded = True
            except Exception:  # pragma: no cover
                pass
    except Exception:  # pragma: no cover
        return False
    return loaded

# v2: live preview diproses pada salinan yang lebih kecil -> UI tetap responsif
# walau gambar input 4K. Saat SIMPAN, selalu full-res.
PREVIEW_CAP = 640        # px, sisi terpanjang, untuk preview normal
PREVIEW_CAP_FS = 512     # Floyd-Steinberg sequential -> preview sedikit lebih kecil

DITHER_OPTIONS = [
    ("none", "None (bersih)"),
    ("bayer2", "Bayer 2x2 (ordered)"),
    ("bayer4", "Bayer 4x4 (ordered)"),
    ("bayer8", "Bayer 8x8 (ordered)"),
    ("fs", "Floyd-Steinberg (error diffusion)"),
]

BITS_OPTIONS = [
    (0, "Off (24-bit)"),
    (4, "4-bit/ch (12-bit)"),
    (5, "5-bit/ch (15-bit PS1)"),
    (6, "6-bit/ch (18-bit)"),
    (8, "8-bit/ch (24-bit)"),
]

RESIZE_OPTIONS = [
    ("none", "Original (tanpa resize)"),
    ("max512", "Max 512 (jaga rasio)"),
    ("max256", "Max 256 (jaga rasio)"),
    ("max128", "Max 128 (jaga rasio)"),
    ("max64", "Max 64 (jaga rasio)"),
    ("cmax", "Custom: max N..."),
    ("cwh", "Custom: W x H..."),
    ("exact256", "Exact 256x256 (stretch)"),
    ("exact128", "Exact 128x128 (stretch)"),
    ("exact64", "Exact 64x64 (stretch)"),
]

RESIZE_MAP = {
    "none": None,
    "max512": ("max", 512),
    "max256": ("max", 256),
    "max128": ("max", 128),
    "max64": ("max", 64),
    "exact256": (256, 256),
    "exact128": (128, 128),
    "exact64": (64, 64),
}

FORMAT_OPTIONS = ["PNG", "JPG", "BMP", "TGA"]

BUILTIN_PRESETS = [
    ("PS1 Classic", dict(colors=16, bits=5, dither="bayer4", dither_strength=1.0,
                         resize="max128", indexed=False, suffix="_ps1", format="PNG", quality=90)),
    ("PS1 Clean", dict(colors=32, bits=5, dither="none", dither_strength=1.0,
                       resize="none", indexed=False, suffix="_ps1", format="PNG", quality=90)),
    ("PS1 Dithered", dict(colors=64, bits=5, dither="fs", dither_strength=1.0,
                          resize="max256", indexed=False, suffix="_ps1", format="PNG", quality=90)),
    ("PS1 Extreme 4-bit", dict(colors=16, bits=4, dither="bayer8", dither_strength=1.2,
                               resize="max64", indexed=True, suffix="_ps1", format="PNG", quality=90)),
    ("Lo-Fi Modern", dict(colors=128, bits=0, dither="none", dither_strength=1.0,
                          resize="max512", indexed=False, suffix="_lofi", format="PNG", quality=90)),
]


# ---------------------------------------------------------------------------
# Core: palette building + quantization
# ---------------------------------------------------------------------------

def snap_bits(arr, bits):
    """Snap warna float (0-255) ke grid N-bit per channel. bits=0/8 -> identity."""
    if not bits or bits >= 8:
        return arr
    levels = float((1 << int(bits)) - 1)
    return np.round(arr * (levels / 255.0)) * (255.0 / levels)


def _bayer_matrix(n):
    cache = _bayer_matrix._cache
    if n in cache:
        return cache[n]
    if n == 1:
        m = np.zeros((1, 1), np.float32)
    elif n == 2:
        m = np.array([[0, 2], [3, 1]], np.float32)
    else:
        h = _bayer_matrix(n // 2) * 4.0
        m = np.block([[h, h + 2], [h + 3, h + 1]])
    m = (m / float(n * n)).astype(np.float32)
    cache[n] = m
    return m


_bayer_matrix._cache = {}


def nearest_indices(colors, palette, chunk=65536):
    """Index palette terdekat untuk tiap warna. colors: (N,3) float, palette: (K,3) float."""
    colors = np.ascontiguousarray(colors, dtype=np.float32)
    palette = np.ascontiguousarray(palette, dtype=np.float32)
    p2 = (palette ** 2).sum(1)
    pT = palette.T
    n = len(colors)
    out = np.empty(n, np.int32)
    for i in range(0, n, chunk):
        c = colors[i:i + chunk]
        d = (c ** 2).sum(1)[:, None] - 2.0 * (c @ pT) + p2[None, :]
        out[i:i + chunk] = d.argmin(1)
    return out


def median_cut_palette(colors, counts, n_colors):
    """Median-cut weighted by pixel counts. colors: (M,3) float, counts: (M,) float."""
    m = len(colors)
    boxes = [np.arange(m)]
    while len(boxes) < n_colors:
        scored = []
        for i, idx in enumerate(boxes):
            if len(idx) < 2:
                continue
            c = colors[idx]
            rng = c.max(0) - c.min(0)
            score = float(counts[idx].sum()) * (float(rng.sum()) + 1.0)
            scored.append((score, i))
        if not scored:
            break
        scored.sort(reverse=True)
        split_done = False
        for _score, i in scored:
            idx = boxes[i]
            c = colors[idx]
            rng = c.max(0) - c.min(0)
            nz = np.nonzero(rng > 0)[0]
            if len(nz) == 0:
                continue
            ch = int(nz[int(np.argmax(rng[nz]))])
            order = np.argsort(c[:, ch], kind="stable")
            sidx = idx[order]
            w = counts[sidx].astype(np.float64)
            cum = np.cumsum(w)
            pos = int(np.searchsorted(cum, cum[-1] * 0.5))
            pos = max(1, min(pos, len(sidx) - 1))
            boxes[i] = sidx[:pos]
            boxes.append(sidx[pos:])
            split_done = True
            break
        if not split_done:
            break
    palette = np.empty((len(boxes), 3), np.float32)
    for i, idx in enumerate(boxes):
        w = counts[idx].astype(np.float64)
        palette[i] = (colors[idx] * w[:, None]).sum(0) / max(w.sum(), 1e-9)
    return palette


def kmeans_refine(colors, counts, palette, iters=25, tol=0.5):
    """Lloyd iterations (weighted) untuk merapikan palette hasil median-cut."""
    k = len(palette)
    if k < 2 or len(colors) == 0:
        return palette
    for _ in range(iters):
        assign = nearest_indices(colors, palette)
        wsum = np.bincount(assign, weights=counts, minlength=k)
        csum = np.zeros((k, 3), np.float64)
        for ch in range(3):
            csum[:, ch] = np.bincount(assign, weights=counts * colors[:, ch], minlength=k)
        nz = wsum > 0
        new_p = palette.astype(np.float64).copy()
        new_p[nz] = csum[nz] / wsum[nz, None]
        shift = float(np.abs(new_p - palette).max()) if len(new_p) else 0.0
        palette = new_p.astype(np.float32)
        if shift < tol:
            break
    return palette


def floyd_steinberg(rgb, palette, strength=1.0):
    """Floyd-Steinberg. rgb: (H,W,3) float32 -> idx (H,W) int32."""
    h, w, _ = rgb.shape
    pT = np.ascontiguousarray(palette, dtype=np.float32).T
    p2 = (np.asarray(palette, dtype=np.float32) ** 2).sum(1)
    err = np.zeros((h + 1, w + 2, 3), np.float32)
    idx = np.empty((h, w), np.int32)
    for y in range(h):
        erow = err[y]
        nrow = err[y + 1]
        for x in range(w):
            v = rgb[y, x] + erow[x + 1]
            d = p2 - 2.0 * (v @ pT)
            k = int(d.argmin())
            idx[y, x] = k
            e = (v - palette[k]) * strength
            if x + 1 < w:
                erow[x + 2] += e * (7.0 / 16.0)
            nrow[x] += e * (3.0 / 16.0)
            nrow[x + 1] += e * (5.0 / 16.0)
            if x + 1 < w:
                nrow[x + 2] += e * (1.0 / 16.0)
    return idx


def _apply_resize(img, mode):
    if not mode:
        return img
    w, h = img.size
    if mode[0] == "max":
        n = int(mode[1])
        if max(w, h) <= n:
            return img
        scale = n / float(max(w, h))
        return img.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.NEAREST)
    return img.resize((int(mode[0]), int(mode[1])), Image.NEAREST)


def process_image(img, settings, palette_override=None, kmeans_iters=25):
    """
    Kuantisasi satu gambar.

    settings: dict dengan keys
        colors          : int, jumlah warna target (2-256)
        bits            : int, bit per channel (0/8 = off, 4/5/6 = turunin depth)
        dither          : 'none' | 'bayer2' | 'bayer4' | 'bayer8' | 'fs'
        dither_strength : float, multiplier amplitudo dither (0-2)
        resize          : None | ('max', n) | (w, h)
        indexed         : bool, output PNG mode P (kalau tidak ada alpha)
        forced_colors   : list[(r,g,b)] warna yang selalu dipertahankan

    palette_override: np.ndarray (K,3) kalau user muat/edit palette manual.

    Return: (out_image: PIL.Image, palette: list[(r,g,b)], stats: dict)
    """
    if img is None:
        raise ValueError("gambar belum di-load")

    img = _apply_resize(img, settings.get("resize"))
    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    base = img.convert("RGBA") if has_alpha else img.convert("RGB")
    arr = np.asarray(base)
    h, w = arr.shape[:2]
    rgb = arr[..., :3]
    alpha = arr[..., 3] if has_alpha else None
    bits = int(settings.get("bits", 0) or 0)

    flat = rgb.reshape(-1, 3)
    uniq, inverse, counts = np.unique(flat, axis=0, return_inverse=True, return_counts=True)
    inverse = np.asarray(inverse).reshape(-1)
    counts = counts.astype(np.float64)
    uniq_f = uniq.astype(np.float32)

    # --- palette -----------------------------------------------------------
    if palette_override is not None:
        palette = np.asarray(palette_override, dtype=np.float32)
        if bits:
            palette = snap_bits(palette, bits)
    else:
        if len(uniq) > MAX_UNIQUE_FOR_PALETTE:
            rng = np.random.default_rng(0)
            p = counts / counts.sum()
            sel = rng.choice(len(uniq), size=MAX_UNIQUE_FOR_PALETTE, replace=False, p=p)
            pal_colors, pal_counts = uniq_f[sel], counts[sel]
        else:
            pal_colors, pal_counts = uniq_f, counts
        n_colors = max(1, min(int(settings.get("colors", 32)), len(pal_colors)))
        palette = median_cut_palette(pal_colors, pal_counts, n_colors)
        palette = kmeans_refine(pal_colors, pal_counts, palette, iters=kmeans_iters)
        if bits:
            palette = snap_bits(palette, bits)

    # --- warna wajib (selalu dipertahankan) --------------------------------
    forced = settings.get("forced_colors") or []
    forced_set = set()
    if forced:
        extra = []
        existing = set(tuple(int(v) for v in p)
                       for p in np.clip(np.round(palette), 0, 255).tolist())
        for c in forced:
            cs = np.asarray(c, dtype=np.float32)
            if bits:
                cs = snap_bits(cs, bits)
            cs = tuple(int(np.clip(round(float(v)), 0, 255)) for v in cs)
            forced_set.add(cs)
            if cs not in existing:
                existing.add(cs)
                extra.append(cs)
        if extra:
            palette = np.vstack([palette, np.asarray(extra, dtype=np.float32)])

    # --- mapping -----------------------------------------------------------
    dither = settings.get("dither", "none")
    strength = float(settings.get("dither_strength", 1.0) or 0.0)
    if dither == "none":
        uidx = nearest_indices(uniq_f, palette)
        idx = uidx[inverse].reshape(h, w)
    elif dither in ("bayer2", "bayer4", "bayer8"):
        n = int(dither[-1])
        bm = _bayer_matrix(n)
        levels = max(2, int(round(len(palette) ** (1.0 / 3.0))))
        amp = (255.0 / levels) * strength
        yy, xx = np.mgrid[0:h, 0:w]
        thr = (bm[yy % n, xx % n] - 0.5) * amp
        pert = np.clip(rgb.astype(np.float32) + thr[..., None], 0.0, 255.0)
        idx = nearest_indices(pert.reshape(-1, 3), palette).reshape(h, w)
    elif dither == "fs":
        idx = floyd_steinberg(rgb.astype(np.float32), palette, strength)
    else:
        raise ValueError("dither mode tidak dikenal: %r" % dither)

    # --- prune warna yang tidak terpakai (warna wajib tetap dipertahankan) --
    used = np.bincount(idx.reshape(-1), minlength=len(palette)) > 0
    if forced_set:
        pal_int = [tuple(int(v) for v in p)
                   for p in np.clip(np.round(palette), 0, 255).tolist()]
        forced_mask = np.array([p in forced_set for p in pal_int], dtype=bool)
        keep = used | forced_mask
    else:
        keep = used
    palette_used = palette[keep]
    remap = np.cumsum(keep) - 1
    idx = remap[idx]

    pal_u8 = np.clip(np.round(palette_used), 0, 255).astype(np.uint8)
    fmt = (settings.get("format") or "PNG").upper()
    if settings.get("indexed") and fmt == "PNG" and not has_alpha:
        out = Image.fromarray(idx.astype(np.uint8), mode="P")
        out.putpalette(pal_u8.reshape(-1).tolist())
    else:
        rgb_out = pal_u8[idx]
        if has_alpha:
            out = Image.fromarray(np.dstack([rgb_out, alpha]), mode="RGBA")
        else:
            out = Image.fromarray(rgb_out, mode="RGB")

    stats = {
        "in_size": img.size,
        "out_size": (w, h),
        "unique_in": int(len(uniq)),
        "colors_used": int(len(pal_u8)),
        "forced_kept": int(forced_mask.sum()) if forced_set else 0,
        "has_alpha": bool(has_alpha),
    }
    return out, [tuple(int(v) for v in c) for c in pal_u8], stats


def export_palette_png(path, palette, cols=16, sw=40, sh=40):
    rows = max(1, math.ceil(len(palette) / cols))
    sheet = Image.new("RGB", (cols * sw, rows * sh), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (r, g, b) in enumerate(palette):
        x = (i % cols) * sw
        y = (i // cols) * sh
        d.rectangle([x, y, x + sw - 1, y + sh - 1], fill=(r, g, b))
    sheet.save(path)


def settings_signature(settings):
    """Signature ringan dari settings - dipakai buat skip reprocess kalau
    tidak ada yang berubah (cache)."""
    keys = ("colors", "bits", "dither", "dither_strength", "resize",
            "indexed", "format", "quality")
    sig = tuple((k, settings.get(k)) for k in keys)
    fc = tuple(tuple(c) for c in (settings.get("forced_colors") or ()))
    return sig + (fc,)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def _fonts_available():
    """Set nama family font yang aktif (butuh root Tk sudah ada)."""
    try:
        from tkinter import font as tkfont
        return set(tkfont.families())
    except Exception:  # pragma: no cover
        return set()


# Daftarkan font bundled saat modul di-load, sebelum Tk dibuat.
_BUNDLED_FONTS_LOADED = _register_bundled_fonts()


def apply_style(root, style):
    """Terapkan tema monochrome noir (sakiko.my.id) ke semua widget ttk.

    Sekali jalan per proses; aman untuk selftest (root di-withdraw)."""
    if root.tk.call("tk", "windowingsystem") == "aqua":
        return  # macOS: biarkan tema native
    fams = _fonts_available()

    def pick(size, *names, weight="normal"):
        for n in names:
            if n in fams:
                return (n, size, weight) if weight != "normal" else (n, size)
        return ("Segoe UI", max(8, size - 2)) if weight == "normal" else \
               ("Segoe UI", max(8, size - 3), "bold")

    global _DISPLAY_FONT, _SECTION_FONT, _BODY_FONT, _UI_FONT
    _DISPLAY_FONT = pick(22, "Barlow Condensed Black", "Barlow Condensed", weight="bold")
    _SECTION_FONT = pick(11, "Barlow Condensed", "Barlow", weight="bold")
    _BODY_FONT = pick(10, "Barlow", "Segoe UI")
    _UI_FONT = pick(10, "Barlow Medium", "Barlow", "Segoe UI")
    font_display = _SECTION_FONT
    root.configure(bg=C["bg"])
    if root.winfo_toplevel() is root and hasattr(root, "option_add"):
        root.option_add("*font", _UI_FONT)

    def tset(k, **kw):
        try:
            style.configure(k, **kw)
        except tk.TclError:  # pragma: no cover - style nggak ada di tema
            pass

    # -- root-ish widgets --
    tset("TFrame", background=C["bg"])
    tset("TLabel", background=C["bg"], foreground=C["ink"],
         font=_UI_FONT, padding=2)
    tset("TLabelframe", background=C["bg"], bordercolor=C["raised"])
    tset("TLabelframe.Label", background=C["bg"], foreground=C["muted"])

    # -- buttons: secondary = surface-raised, hover -> highlight, active = ink --
    tset("TButton", background=C["raised"], foreground=C["ink"], bordercolor=C["highlight"],
         focusthickness=0, focuscolor=C["ink"], padding=(14, 7), font=_UI_FONT)
    tset("TButton.hover", background=C["highlight"], foreground=C["ink"])
    tset("TButton.pressed", background=C["ink"], foreground=C["accent_ink"])

    # -- primary / accent button (class "Accent.TButton") --
    tset("Accent.TButton", background=C["ink"], foreground=C["accent_ink"],
         bordercolor=C["ink"], focusthickness=0, focuscolor=C["ink"],
         padding=(14, 7), font=_UI_FONT)
    tset("Accent.TButton.hover", background=C["muted"], foreground=C["accent_ink"])
    tset("Accent.TButton.pressed", background=C["dim"], foreground=C["accent_ink"])

    # -- entry / spinbox / combobox --
    tset("TEntry", fieldbackground=C["surface"], foreground=C["ink"],
         insertcolor=C["ink"], bordercolor=C["highlight"], lightcolor=C["highlight"],
         darkcolor=C["highlight"], padding=4)
    tset("TSpinbox", fieldbackground=C["surface"], foreground=C["ink"],
         background=C["raised"], bordercolor=C["highlight"], arrowcolor=C["ink"],
         insertcolor=C["ink"], padding=3)
    tset("TCombobox", fieldbackground=C["surface"], background=C["raised"],
         foreground=C["ink"], arrowcolor=C["ink"], bordercolor=C["highlight"],
         lightcolor=C["highlight"], darkcolor=C["highlight"], padding=4)
    tset("TCombobox.field", background=C["surface"], foreground=C["ink"])
    tset("TCombobox.downarrow", background=C["surface"], bordercolor=C["highlight"])
    tset("TCombobox.dropdown", background=C["surface"], foreground=C["ink"],
         bordercolor=C["highlight"])
    # clam: state readonly pakai `background` sebagai isian field -> map ke gelap
    style.map("TCombobox",
              fieldbackground=[("readonly", C["surface"]), ("disabled", C["surface"])],
              background=[("readonly", C["surface"]), ("active", C["highlight"])],
              foreground=[("readonly", C["ink"]), ("disabled", C["dim"])],
              arrowcolor=[("readonly", C["ink"])],
              selectbackground=[("readonly", C["surface"])],
              selectforeground=[("readonly", C["ink"])])

    # -- checkbutton / radiobutton --
    tset("TCheckbutton", background=C["bg"], foreground=C["ink"], font=_UI_FONT)
    tset("TCheckbutton.indicator", background=C["surface"], bordercolor=C["muted"])
    tset("TRadiobutton", background=C["bg"], foreground=C["ink"], font=_UI_FONT)
    tset("TRadiobutton.indicator", background=C["surface"], bordercolor=C["muted"])

    # -- scrollbar: block-style (chunky, geometric) --
    tset("Vertical.TScrollbar", background=C["raised"], troughcolor=C["bg"],
         bordercolor=C["bg"], arrowcolor=C["muted"], relief="flat",
         lightcolor=C["raised"], darkcolor=C["raised"])
    style.map("Vertical.TScrollbar",
              background=[("active", C["highlight"]), ("pressed", C["ink"])])
    tset("Horizontal.TScrollbar", background=C["raised"], troughcolor=C["bg"],
         bordercolor=C["bg"], arrowcolor=C["muted"], relief="flat",
         lightcolor=C["raised"], darkcolor=C["raised"])
    style.map("Horizontal.TScrollbar",
              background=[("active", C["highlight"]), ("pressed", C["ink"])])

    # -- separator: tebal (anti thin-rules) --
    tset("TSeparator", background=C["raised"])

    # -- scale (strength slider): clam pakai `background` utk trough, `troughcolor` utk thumb --
    tset("Horizontal.TScale", background=C["raised"], troughcolor=C["ink"],
         bordercolor=C["bg"], lightcolor=C["raised"], darkcolor=C["raised"])
    style.map("Horizontal.TScale",
              background=[("disabled", C["surface"])],
              troughcolor=[("disabled", C["dim"]), ("active", C["ink"])])

    # -- section header: Barlow Condensed 900 uppercase --
    style.configure("Section.TLabel", font=font_display, foreground=C["ink"],
                    background=C["bg"])

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Color Quantizer - PS1 Texture Tool")
        self.root.geometry("1220x800")
        self.root.minsize(1020, 680)

        self.files = []
        self.current = None
        self.orig_image = None
        self.result_image = None
        self.palette = []
        self.loaded_palette = None
        self.forced_colors = []
        self.custom_max = 96
        self.custom_wh = "96x96"
        self.custom_presets = {}
        self.language = "id"
        self._translated_widgets = []

        self._busy = False
        self._dirty = False
        self._after_id = None
        self._last_sig = None

        self.colors_var = tk.IntVar(value=32)
        self.bits_var = tk.StringVar(value="5-bit/ch (15-bit PS1)")
        self.dither_var = tk.StringVar(value="None (bersih)")
        self.strength_var = tk.DoubleVar(value=1.0)
        self.strength_lbl_var = tk.StringVar(value="100%")
        self.resize_var = tk.StringVar(value="Original (tanpa resize)")
        self.indexed_var = tk.BooleanVar(value=False)
        self.suffix_var = tk.StringVar(value="_ps1")
        self.format_var = tk.StringVar(value="PNG")
        self.quality_var = tk.IntVar(value=90)
        self.edit_pal_var = tk.BooleanVar(value=False)
        self.preset_var = tk.StringVar(value="PS1 Classic")
        self.palette_src_var = tk.StringVar(value="Palette: otomatis (dari gambar)")
        self.orig_info_var = tk.StringVar(value="Belum ada gambar")
        self.status_var = tk.StringVar(value="Siap. Buka gambar atau drag & drop ke window ini.")
        self.language_var = tk.StringVar(value="Bahasa Indonesia")

        self._dither_labels = {lbl: k for k, lbl in DITHER_OPTIONS}
        self._bits_labels = {lbl: k for k, lbl in BITS_OPTIONS}
        self._resize_labels = {lbl: k for k, lbl in RESIZE_OPTIONS}
        self._dither_labels_inv = {k: lbl for k, lbl in DITHER_OPTIONS}
        self._bits_labels_inv = {k: lbl for k, lbl in BITS_OPTIONS}
        self._resize_labels_inv = {k: lbl for k, lbl in RESIZE_OPTIONS}

        self._build_ui()
        self._register_dnd()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover
            pass
        global _ttk_style
        _ttk_style = style
        apply_style(self.root, style)

        # -- masthead (echo wordmark sakiko.my.id) --
        mast = tk.Frame(self.root, bg=C["bg"])
        mast.pack(side="top", fill="x", padx=16, pady=(12, 0))
        _brand = tk.Frame(mast, bg=C["bg"])
        _brand.pack(side="top", anchor="w")

        # logo icon (kiri wordmark) - jalan di source maupun EXE frozen
        self._logo_img = None
        _logo_path = os.path.join(
            getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
            "logo.jpg")
        if os.path.isfile(_logo_path):
            try:
                _logo = Image.open(_logo_path).convert("RGB")
                _logo.thumbnail((44, 44), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(_logo)
            except Exception:
                self._logo_img = None
        if self._logo_img is not None:
            tk.Label(_brand, image=self._logo_img, bg=C["bg"],
                     borderwidth=0, highlightthickness=0).pack(
                         side="left", anchor="w", padx=(0, 10))
            try:  # bonus: icon window/taskbar pakai logo yang sama
                self.root.iconphoto(True, self._logo_img)
            except Exception:
                pass

        _txt = tk.Frame(_brand, bg=C["bg"])
        _txt.pack(side="left", anchor="w")
        tk.Label(_txt, text="COLOR QUANTIZER", bg=C["bg"], fg=C["ink"],
                 font=_DISPLAY_FONT).pack(anchor="w")
        tk.Label(_txt, text="PS1 TEXTURE TOOL  /  PALETTE  /  DITHERING",
                 bg=C["bg"], fg=C["dim"], font=_MONO_FONT).pack(anchor="w", pady=(0, 8))
        self.language_box = ttk.Combobox(
            mast, state="readonly", width=18, textvariable=self.language_var,
            values=("Bahasa Indonesia", "English"))
        self.language_box.pack(side="right", anchor="n", pady=(2, 0))
        self.language_box.bind("<<ComboboxSelected>>", self._on_language_changed)

        main = ttk.Frame(style.root if hasattr(style, "root") else self.root, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0, minsize=340)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_left(main)
        self._build_right(main)
        self._capture_translatable_widgets(self.root)

        bar = ttk.Label(self.root, textvariable=self.status_var, anchor="w",
                        background=C["surface"], foreground=C["dim"],
                        font=_UI_FONT, padding=(12, 6))
        bar.pack(side="bottom", fill="x")

    def _capture_translatable_widgets(self, parent):
        for widget in parent.winfo_children():
            try:
                text = widget.cget("text")
                if text:
                    self._translated_widgets.append((widget, text))
            except (tk.TclError, TypeError):
                pass
            self._capture_translatable_widgets(widget)

    def _on_language_changed(self, _event=None):
        self.language = "en" if self.language_var.get() == "English" else "id"
        for widget, original in self._translated_widgets:
            try:
                # Don't overwrite labels controlled by live StringVars.
                if str(widget.cget("textvariable")):
                    continue
                widget.configure(text=_UI_EN.get(original, original) if self.language == "en" else original)
            except (tk.TclError, TypeError):
                pass
        self.root.title("Color Quantizer - PS1 Texture Tool")
        self._refresh_language_values()
        self._refresh_dynamic_text()
        self._update_counts()
        self._refresh_language_specific_widgets()
        self._set_status("Ready. Open or drag & drop images into this window." if self.language == "en"
                         else "Siap. Buka gambar atau drag & drop ke window ini.")

    def _refresh_language_values(self):
        def current_key(value, labels, inverse):
            return labels.get(value, next((k for k, v in inverse.items()
                                           if _UI_EN.get(v, v) == value), None))
        def display(key, inverse):
            base = inverse[key]
            return _UI_EN.get(base, base) if self.language == "en" else base
        for var, labels, inverse, box in (
                (self.bits_var, self._bits_labels, self._bits_labels_inv, self.bits_box),
                (self.dither_var, self._dither_labels, self._dither_labels_inv, self.dither_box),
                (self.resize_var, self._resize_labels, self._resize_labels_inv, self.resize_box)):
            key = current_key(var.get(), labels, inverse)
            if key is not None:
                var.set(display(key, inverse))
            box.configure(values=[display(k, inverse) for k in inverse])

    def _refresh_dynamic_text(self):
        preset_values = [(_UI_EN.get(n, n) if self.language == "en" else n)
                         for n, _settings in BUILTIN_PRESETS]
        preset_values.extend(self.custom_presets.keys())
        self.preset_box.configure(values=preset_values)
        current_preset = self.preset_var.get()
        self.preset_var.set(_UI_EN.get(current_preset, current_preset)
                            if self.language == "en" else
                            next((n for n, _s in BUILTIN_PRESETS
                                  if _UI_EN.get(n, n) == current_preset), current_preset))
        if self.language == "en":
            if self.current is None:
                self.orig_info_var.set("No image loaded")
            self.palette_src_var.set(self._palette_source_text())
        else:
            if self.current is None:
                self.orig_info_var.set("Belum ada gambar")
            self.palette_src_var.set(self._palette_source_text())

    def _refresh_language_specific_widgets(self):
        for widget, original in self._translated_widgets:
            try:
                if str(widget.cget("textvariable")):
                    continue
                current = str(widget.cget("text"))
                if current.startswith("Proses & simpan semua (") or current.startswith("Process & save all ("):
                    self._update_counts()
                elif original == "Resize (sebelum kuantisasi):":
                    widget.configure(text=self._t(original))
            except (tk.TclError, TypeError):
                pass

    def _palette_source_text(self):
        if self.loaded_palette is None:
            base = "Palette: automatic (from image)" if self.language == "en" else "Palette: otomatis (dari gambar)"
        else:
            n = len(self.palette)
            base = ("Palette: manual (%d colors)" % n if self.language == "en"
                    else "Palette: manual (%d warna)" % n)
        if self.forced_colors:
            base += (" + %d forced colors" if self.language == "en" else " + %d warna wajib") % len(self.forced_colors)
        return base

    def _t(self, text):
        return _UI_EN.get(text, text) if self.language == "en" else text

    def _build_left(self, parent):
        outer = ttk.Frame(parent)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0, width=340,
                           bg=C["bg"])
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        left = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        left.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=left, anchor="nw")
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        left.bind("<MouseWheel>",
                  lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # -- section helper --
        def section(title):
            ttk.Label(left, text=self._t(title), style="Section.TLabel").pack(anchor="w", pady=(16, 4))

        def sep():
            ttk.Separator(left).pack(fill="x", pady=12)

        # -- gambar --
        section("GAMBAR")
        ttk.Button(left, text="Buka gambar...", command=self.open_files,
                   style="Accent.TButton").pack(fill="x")
        self.drop_hint = ttk.Label(left, text=self._t("...atau drag & drop gambar ke window ini"),
                                   foreground=C["dim"], font=_BODY_FONT, wraplength=300)
        self.drop_hint.pack(anchor="w", pady=(4, 2))

        lb_frame = ttk.Frame(left)
        lb_frame.pack(fill="x", pady=(6, 2))
        self.listbox = tk.Listbox(lb_frame, height=5, exportselection=False,
                                  bg=C["surface"], fg=C["ink"],
                                  selectbackground=C["highlight"],
                                  selectforeground=C["ink"],
                                  highlightbackground=C["raised"],
                                  highlightcolor=C["ink"],
                                  highlightthickness=1,
                                  borderwidth=0,
                                  activestyle="none",
                                  font=_BODY_FONT)
        sb2 = ttk.Scrollbar(lb_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb2.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.on_select_file)

        ttk.Button(left, text="Bersihkan list", command=self.clear_files).pack(fill="x")

        sep()

        # -- preset --
        section("PRESET (satu klik)")
        prow = ttk.Frame(left)
        prow.pack(fill="x", pady=(4, 0))
        self.preset_box = ttk.Combobox(prow, state="readonly",
                                       textvariable=self.preset_var,
                                       values=[n for n, _s in BUILTIN_PRESETS])
        self.preset_box.pack(side="left", fill="x", expand=True)
        self.preset_box.bind("<<ComboboxSelected>>", self._on_preset_selected)
        ttk.Button(prow, text="Terapkan", command=self._apply_current_preset,
                   width=8).pack(side="right", padx=(4, 0))
        prow2 = ttk.Frame(left)
        prow2.pack(fill="x", pady=(4, 0))
        ttk.Button(prow2, text="Simpan preset...", command=self.save_preset).pack(
            side="left", expand=True, fill="x")
        ttk.Button(prow2, text="Muat preset...", command=self.load_preset).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

        sep()

        # -- kuantisasi --
        section("PENGATURAN KUANTISASI")

        row = ttk.Frame(left)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text=self._t("Jumlah warna:")).pack(side="left")
        self.colors_spin = ttk.Spinbox(row, from_=2, to=256, width=6,
                                       textvariable=self.colors_var,
                                       command=self.schedule_process)
        self.colors_spin.pack(side="right")
        self.colors_spin.bind("<Return>", lambda e: self.schedule_process(0))
        self.colors_spin.bind("<FocusOut>", lambda e: self.schedule_process(0))

        preset = ttk.Frame(left)
        preset.pack(fill="x", pady=(2, 0))
        for v in (16, 32, 64, 128, 256):
            ttk.Button(preset, text=str(v), width=4,
                       command=lambda vv=v: self._set_colors(vv)).pack(side="left", padx=(0, 2))

        ttk.Label(left, text=self._t("Color depth:")).pack(anchor="w", pady=(10, 0))
        self.bits_box = ttk.Combobox(left, state="readonly",
                                     values=[lbl for _k, lbl in BITS_OPTIONS],
                                     textvariable=self.bits_var)
        self.bits_box.pack(fill="x")
        self.bits_box.bind("<<ComboboxSelected>>", lambda e: self.schedule_process(0))

        ttk.Label(left, text=self._t("Dithering:")).pack(anchor="w", pady=(10, 0))
        self.dither_box = ttk.Combobox(left, state="readonly",
                                       values=[lbl for _k, lbl in DITHER_OPTIONS],
                                       textvariable=self.dither_var)
        self.dither_box.pack(fill="x")
        self.dither_box.bind("<<ComboboxSelected>>", self._on_dither_changed)

        srow = ttk.Frame(left)
        srow.pack(fill="x", pady=(6, 0))
        ttk.Label(srow, text=self._t("Strength:")).pack(side="left")
        self.strength_scale = ttk.Scale(srow, from_=0.0, to=2.0,
                                        variable=self.strength_var,
                                        command=self._on_strength)
        self.strength_scale.pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Label(srow, textvariable=self.strength_lbl_var, width=5).pack(side="right")

        ttk.Label(left, text=self._t("Resize (sebelum kuantisasi):")).pack(anchor="w", pady=(10, 0))
        self.resize_box = ttk.Combobox(left, state="readonly",
                                       values=[lbl for _k, lbl in RESIZE_OPTIONS],
                                       textvariable=self.resize_var)
        self.resize_box.pack(fill="x")
        self.resize_box.bind("<<ComboboxSelected>>", self._on_resize_changed)

        ttk.Checkbutton(left, text="Output indexed PNG (mode P)",
                        variable=self.indexed_var,
                        command=self.schedule_process).pack(anchor="w", pady=(10, 0))

        sep()

        # -- output --
        section("OUTPUT")
        orow = ttk.Frame(left)
        orow.pack(fill="x", pady=(4, 0))
        ttk.Label(orow, text="Suffix:").pack(side="left")
        ttk.Entry(orow, textvariable=self.suffix_var, width=10).pack(side="left", padx=(4, 8))
        ttk.Label(orow, text="Format:").pack(side="left")
        self.format_box = ttk.Combobox(orow, state="readonly", width=6,
                                       values=FORMAT_OPTIONS,
                                       textvariable=self.format_var)
        self.format_box.pack(side="right")
        self.format_box.bind("<<ComboboxSelected>>", self._on_format_changed)
        qrow = ttk.Frame(left)
        qrow.pack(fill="x", pady=(4, 0))
        ttk.Label(qrow, text="Kualitas JPG:").pack(side="left")
        self.quality_spin = ttk.Spinbox(qrow, from_=1, to=100, width=5,
                                        textvariable=self.quality_var,
                                        command=self.schedule_process)
        self.quality_spin.pack(side="left", padx=(4, 8))
        self.quality_spin.bind("<Return>", lambda e: self.schedule_process(0))
        self.quality_spin.bind("<FocusOut>", lambda e: self.schedule_process(0))
        ttk.Label(qrow, text="(lossy - tinggi = file besar)",
                  foreground=C["dim"]).pack(side="left")
        ttk.Label(left, text="Nama file: <nama><suffix>.<ext>",
                  foreground=C["dim"]).pack(anchor="w", pady=(2, 0))

        self.btn_all = ttk.Button(left, text="Proses & simpan semua (0)",
                                  command=self.process_all, style="Accent.TButton")
        self.btn_all.pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Simpan hasil ini...", command=self.save_current).pack(
            fill="x", pady=(4, 0))

        sep()

        # -- palette --
        section("PALETTE")
        prow = ttk.Frame(left)
        prow.pack(fill="x", pady=(4, 0))
        ttk.Button(prow, text="Simpan palette", command=self.export_palette).pack(
            side="left", expand=True, fill="x")
        ttk.Button(prow, text="Muat palette", command=self.load_palette).pack(
            side="left", expand=True, fill="x", padx=(4, 0))
        ttk.Button(left, text="Pakai palette otomatis", command=self.clear_loaded_palette).pack(
            fill="x", pady=(4, 0))
        ttk.Checkbutton(left, text="Mode edit palette (klik = ganti warna)",
                        variable=self.edit_pal_var,
                        command=self._sync_edit_mode).pack(anchor="w", pady=(6, 0))
        erow = ttk.Frame(left)
        erow.pack(fill="x", pady=(4, 0))
        ttk.Button(erow, text="Tambah warna...", command=self.add_palette_color).pack(
            side="left", expand=True, fill="x")
        ttk.Button(erow, text="Warna wajib...", command=self.add_forced_color).pack(
            side="left", expand=True, fill="x", padx=(4, 0))
        ttk.Label(left, textvariable=self.palette_src_var, foreground=C["dim"],
                  wraplength=300, font=_BODY_FONT).pack(anchor="w", pady=(2, 0))
        self._sync_edit_mode()
        self._sync_quality_state()

    def _build_right(self, parent):
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.rowconfigure(4, weight=1)
        right.columnconfigure(0, weight=1)
        right.columnconfigure(1, weight=1)

        ttk.Label(right, text="ORIGINAL", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(right, text="HASIL KUANTISASI", style="Section.TLabel").grid(row=0, column=1, sticky="w", pady=(0, 6))
        self.before_lbl = tk.Label(right, anchor="center", bg=C["surface"])
        self.after_lbl = tk.Label(right, anchor="center", bg=C["surface"])
        self.before_lbl.grid(row=1, column=0, sticky="nsew", padx=(0, 2))
        self.after_lbl.grid(row=1, column=1, sticky="nsew", padx=(2, 0))

        info = ttk.Frame(right)
        info.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(info, textvariable=self.orig_info_var).pack(side="left")

        head = ttk.Frame(right)
        head.grid(row=3, column=0, columnspan=2, sticky="new", pady=(12, 0))
        ttk.Label(head, text="PALETTE (klik swatch = copy hex / ganti warna di mode edit)",
                  style="Section.TLabel").pack(side="left")
        ttk.Button(head, text="Copy semua hex", command=self.copy_all_hex).pack(side="right")

        pc = ttk.Frame(right)
        pc.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        self.pal_canvas = tk.Canvas(pc, borderwidth=0, highlightthickness=0, height=190,
                                    bg=C["bg"])
        sb = ttk.Scrollbar(pc, orient="vertical", command=self.pal_canvas.yview)
        self.pal_canvas.configure(yscrollcommand=sb.set)
        self.pal_frame = ttk.Frame(self.pal_canvas)
        self.pal_frame.bind(
            "<Configure>",
            lambda e: self.pal_canvas.configure(scrollregion=self.pal_canvas.bbox("all")),
        )
        self.pal_canvas.create_window((0, 0), window=self.pal_frame, anchor="nw")
        self.pal_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.pal_canvas.bind("<MouseWheel>",
                             lambda e: self.pal_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    # -- drag & drop --------------------------------------------------------

    def _register_dnd(self):
        if not _HAS_DND:
            self.drop_hint.configure(
                text="...atau pakai tombol 'Buka gambar' (install tkinterdnd2 untuk drag-drop)")
            return
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            self.root.dnd_bind("<<DropLeave>>", self._on_drop_leave)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
        except Exception as exc:  # pragma: no cover
            self.drop_hint.configure(text="Drag-drop gagal init: %s" % exc)

    def _on_drop_enter(self, event):
        text = "Drop to load images!" if self.language == "en" else "Lepaskan untuk load gambar!"
        self.drop_hint.configure(text=text, foreground="#0a7")

    def _on_drop_leave(self, event):
        self.drop_hint.configure(text=self._t("...atau drag & drop gambar ke window ini"), foreground="#666")

    def _on_drop(self, event):
        self.drop_hint.configure(text=self._t("...atau drag & drop gambar ke window ini"), foreground="#666")
        try:
            paths = self.root.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        self.add_files([p for p in paths if os.path.splitext(p)[1].lower() in IMAGE_EXTS])

    # -- file handling ------------------------------------------------------

    def add_files(self, paths):
        new = [p for p in paths if p not in self.files]
        if not new:
            return
        first = self.current is None
        self.files.extend(new)
        self._refresh_list()
        if first and self.files:
            self.current = 0
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(0)
            self._load_current()
            self.schedule_process(0)
        self._update_counts()

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for p in self.files:
            self.listbox.insert("end", os.path.basename(p))

    def _update_counts(self):
        label = "Process & save all" if self.language == "en" else "Proses & simpan semua"
        self.btn_all.configure(text="%s (%d)" % (label, len(self.files)))

    def _refresh_language_specific_widgets(self):
        # Update live text-variable labels which are intentionally excluded
        # from the static label registry.
        for w in self._walk_widgets(self.root):
            try:
                text = str(w.cget("text"))
                if text in ("Resize (sebelum kuantisasi):", "Resize (before quantization):"):
                    w.configure(text="Resize (before quantization):" if self.language == "en"
                                else "Resize (sebelum kuantisasi):")
            except (tk.TclError, TypeError):
                pass

    @staticmethod
    def _walk_widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from App._walk_widgets(child)

    def clear_files(self):
        self.files = []
        self.current = None
        self.orig_image = None
        self.result_image = None
        self.palette = []
        self._last_sig = None
        self._refresh_list()
        self._update_counts()
        self._render_palette()
        self._clear_previews()
        self.orig_info_var.set("No image loaded" if self.language == "en" else "Belum ada gambar")
        self._set_status("List dibersihkan.")

    def on_select_file(self, _event):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.current = sel[0]
        self._load_current()
        self.schedule_process(0)

    def _load_current(self):
        if self.current is None or not (0 <= self.current < len(self.files)):
            return
        p = self.files[self.current]
        try:
            img = Image.open(p)
            img.load()
            self.orig_image = img
            self.orig_info_var.set(
                "%s  |  %dx%d  |  mode %s" % (os.path.basename(p), img.size[0], img.size[1], img.mode))
        except Exception as exc:
            self.orig_image = None
            self.orig_info_var.set("Gagal load: %s" % exc)
            self._set_status("Gagal membuka %s: %s" % (p, exc))

    def open_files(self):
        paths = filedialog.askopenfilenames(
            title="Select images" if self.language == "en" else "Pilih gambar",
            filetypes=[("Images" if self.language == "en" else "Gambar", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.tga;*.tif;*.tiff;*.webp"),
                       ("All files" if self.language == "en" else "Semua file", "*.*")])
        if paths:
            self.add_files(list(paths))

    # -- settings -----------------------------------------------------------

    def get_settings(self):
        key = self._resize_labels.get(self.resize_var.get())
        if key is None:
            key = next((k for k, label in self._resize_labels_inv.items()
                        if _UI_EN.get(label, label) == self.resize_var.get()), "none")
        if key == "cmax":
            mode = ("max", int(self.custom_max))
        elif key == "cwh":
            m = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", self.custom_wh or "")
            mode = (int(m.group(1)), int(m.group(2))) if m else None
        else:
            mode = RESIZE_MAP.get(key)
        return {
            "colors": int(self.colors_var.get()),
            "bits": self._option_key(self.bits_var.get(), self._bits_labels, self._bits_labels_inv, 0),
            "dither": self._option_key(self.dither_var.get(), self._dither_labels, self._dither_labels_inv, "none"),
            "dither_strength": float(self.strength_var.get()),
            "resize": mode,
            "resize_key": key,
            "indexed": bool(self.indexed_var.get()),
            "suffix": self.suffix_var.get() or "_ps1",
            "format": self.format_var.get() or "PNG",
            "quality": int(self.quality_var.get()),
            "forced_colors": [tuple(c) for c in self.forced_colors],
        }

    @staticmethod
    def _option_key(value, labels, inverse, default):
        key = labels.get(value)
        if key is not None:
            return key
        return next((k for k, label in inverse.items() if _UI_EN.get(label, label) == value), default)

    def _set_colors(self, v):
        self.colors_var.set(v)
        self.schedule_process(0)

    def _on_dither_changed(self, _event=None):
        self._sync_strength_state()
        self.schedule_process(0)

    def _on_resize_changed(self, _event=None):
        key = self._option_key(self.resize_var.get(), self._resize_labels,
                               self._resize_labels_inv, "none")
        if key == "cmax":
            v = simpledialog.askinteger("Custom resize", "Maksimum sisi terpanjang (px):",
                                        initialvalue=self.custom_max, minvalue=1,
                                        maxvalue=8192, parent=self.root)
            if v:
                self.custom_max = int(v)
        elif key == "cwh":
            s = simpledialog.askstring("Custom resize", "Ukuran WxH (contoh 96x128):",
                                       initialvalue=self.custom_wh, parent=self.root)
            if s and s.strip():
                self.custom_wh = s.strip()
        self.schedule_process(0)

    def _on_strength(self, _v=None):
        self.strength_lbl_var.set("%d%%" % round(float(self.strength_var.get()) * 100))
        self.schedule_process(60)

    def _on_format_changed(self, _event=None):
        self._sync_quality_state()
        self.schedule_process(0)

    def _sync_quality_state(self):
        lossy = (self.format_var.get() or "").upper() in ("JPG", "JPEG")
        self.quality_spin.configure(state="normal" if lossy else "disabled")

    def _sync_strength_state(self):
        d = self._option_key(self.dither_var.get(), self._dither_labels,
                              self._dither_labels_inv, "none")
        self.strength_scale.configure(state="disabled" if d == "none" else "normal")

    # -- presets ------------------------------------------------------------

    def _all_presets(self):
        d = {n: s for n, s in BUILTIN_PRESETS}
        d.update(self.custom_presets)
        return d

    def _on_preset_selected(self, _event=None):
        self._apply_current_preset()

    def _apply_current_preset(self):
        name = self.preset_var.get()
        if self.language == "en":
            name = next((source for source, translated in _UI_EN.items()
                         if translated == name and source in
                         [pname for pname, _settings in BUILTIN_PRESETS]), name)
        s = self._all_presets().get(name)
        if not s:
            return
        self.apply_preset(s)
        self._set_status("Preset '%s' diterapkan." % name)

    def apply_preset(self, s):
        self.colors_var.set(int(s.get("colors", 32)))
        bits = int(s.get("bits", 0) or 0)
        self.bits_var.set(dict((k, lbl) for k, lbl in BITS_OPTIONS).get(bits, "Off (24-bit)"))
        dither = s.get("dither", "none")
        self.dither_var.set(dict((k, lbl) for k, lbl in DITHER_OPTIONS).get(dither, "None (bersih)"))
        self.strength_var.set(float(s.get("dither_strength", 1.0)))
        self._on_strength()
        rkey = s.get("resize", "none")
        self.resize_var.set(dict((k, lbl) for k, lbl in RESIZE_OPTIONS).get(rkey, "Original (tanpa resize)"))
        self.indexed_var.set(bool(s.get("indexed", False)))
        self.suffix_var.set(s.get("suffix", "_ps1") or "_ps1")
        self.format_var.set(s.get("format", "PNG") or "PNG")
        self.quality_var.set(int(s.get("quality", 90)))
        self._sync_strength_state()
        self._sync_quality_state()
        self._refresh_language_values()
        self.schedule_process(0)

    def save_preset(self):
        title = "Save preset" if self.language == "en" else "Simpan preset"
        prompt = "Preset name:" if self.language == "en" else "Nama preset:"
        name = simpledialog.askstring(title, prompt, parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        path = filedialog.asksaveasfilename(
            title=title, initialfile=re.sub(r"[^\w\-]+", "_", name) + ".json",
            defaultextension=".json", filetypes=[("Preset JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"name": name, "settings": self.get_settings()}, f, indent=1)
            self.custom_presets[name] = self.get_settings()
            self._refresh_preset_values()
            self.preset_var.set(name)
            self._set_status("Preset '%s' disimpan: %s" % (name, path))
        except Exception as exc:
            messagebox.showerror("Gagal simpan preset", str(exc))

    def load_preset(self):
        path = filedialog.askopenfilename(title="Load preset JSON" if self.language == "en" else "Muat preset JSON",
                                          filetypes=[("Preset JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = str(data.get("name") or os.path.splitext(os.path.basename(path))[0])
            s = data["settings"]
            if "colors" not in s:
                raise ValueError("file preset tidak valid (tidak ada key 'colors')")
            self.custom_presets[name] = s
            self._refresh_preset_values()
            self.preset_var.set(name)
            self.apply_preset(s)
            self._set_status("Preset '%s' dimuat dari %s" % (name, path))
        except Exception as exc:
            messagebox.showerror("Gagal muat preset", str(exc))

    def _refresh_preset_values(self):
        values = [n for n, _s in BUILTIN_PRESETS] + list(self.custom_presets)
        self.preset_box.configure(values=values)

    # -- processing ---------------------------------------------------------

    def schedule_process(self, delay=120):
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.root.after(delay, self._kick)

    def _kick(self):
        self._after_id = None
        if self.current is None or self.orig_image is None:
            return
        if self._busy:
            self._dirty = True
            return
        settings = self.get_settings()
        pal = self.loaded_palette
        pal_bytes = pal.tobytes() if pal is not None else None
        sig = (self.files[self.current], id(self.orig_image),
               settings_signature(settings), pal_bytes)
        if sig == self._last_sig:
            return  # nggak ada yang berubah -> skip reprocess (hemat CPU)
        self._last_sig = sig
        self._busy = True

        # v2: preview proses salinan lebih kecil kalau gambar besar
        cap = PREVIEW_CAP_FS if settings.get("dither") == "fs" else PREVIEW_CAP
        pimg, capped = self._preview_image(self.orig_image, cap)
        iters = 8 if capped else 25
        self._set_status("Processing...")

        def work():
            try:
                out, palette, stats = process_image(pimg, settings, pal,
                                                    kmeans_iters=iters)
                payload = (out, palette, stats, None, capped)
            except Exception:
                payload = (None, None, None, traceback.format_exc(), capped)
            self.root.after(0, self._on_processed, payload)

        threading.Thread(target=work, daemon=True).start()

    def _preview_image(self, img, cap):
        """Kembalikan (image, capped). Kalau sisi terpanjang > cap, proses
        salinan nearest-neighbor yang lebih kecil - live preview tetap responsif."""
        w, h = img.size
        if max(w, h) <= cap:
            return img, False
        scale = cap / float(max(w, h))
        small = img.resize((max(1, int(round(w * scale))),
                            max(1, int(round(h * scale)))), Image.NEAREST)
        return small, True

    def _on_processed(self, payload):
        out, palette, stats, err, capped = payload
        self._busy = False
        if err is not None:
            self._set_status("Error: " + err.strip().splitlines()[-1])
        else:
            self.result_image = out
            if palette != self.palette:
                self.palette = palette
                self._render_palette()
            self._render_preview()
            msg = "%s -> %dx%d, %d warna (dari %d warna asli)" % (
                os.path.basename(self.files[self.current]),
                stats["out_size"][0], stats["out_size"][1],
                stats["colors_used"], stats["unique_in"])
            if capped:
                msg += " | preview @ %dpx - simpan = full-res" % max(stats["out_size"])
            if stats["forced_kept"]:
                msg += " | %d warna wajib dipertahankan" % stats["forced_kept"]
            if stats["has_alpha"]:
                msg += " | alpha dipertahankan"
            self._set_status(msg)
        if self._dirty:
            self._dirty = False
            self._kick()

    # -- preview ------------------------------------------------------------

    def _fit(self, img, box=440):
        im = img.copy()
        im.thumbnail((box, box), Image.NEAREST)
        return im

    def _render_preview(self):
        for widget, img in ((self.before_lbl, self.orig_image), (self.after_lbl, self.result_image)):
            if img is None:
                continue
            ph = ImageTk.PhotoImage(self._fit(img))
            widget.configure(image=ph)
            widget.image = ph

    def _clear_previews(self):
        for widget in (self.before_lbl, self.after_lbl):
            widget.configure(image="")
            widget.image = None

    def _render_palette(self):
        for w in self.pal_frame.winfo_children():
            w.destroy()
        cols = 8
        for i, (r, g, b) in enumerate(self.palette):
            hexs = "#%02x%02x%02x" % (r, g, b)
            forced = (r, g, b) in self.forced_colors
            border = "#ffffff" if forced else C["raised"]
            cell = tk.Frame(self.pal_frame, bg=hexs, width=62, height=38,
                            highlightthickness=1,
                            highlightbackground=border)
            cell.grid(row=i // cols, column=i % cols, padx=2, pady=2)
            cell.pack_propagate(False)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            fg = "#111" if lum > 140 else "#eee"
            tk.Label(cell, text=hexs, bg=hexs, fg=fg,
                     font=_MONO_FONT).place(relx=0.5, rely=0.5, anchor="center")
            cell.bind("<Button-1>", lambda e, i=i: self._on_swatch_click(i))
            cell.bind("<Button-3>", lambda e, i=i: self._on_swatch_right(i))
        self.pal_canvas.configure(scrollregion=self.pal_canvas.bbox("all"))

    def _on_swatch_click(self, i):
        if not (0 <= i < len(self.palette)):
            return
        if not self.edit_pal_var.get():
            self.copy_hex(self.palette[i])
            return
        init = "#%02x%02x%02x" % self.palette[i]
        res = colorchooser.askcolor(color=init, title="Ganti warna #%d" % i,
                                    parent=self.root)
        if res and res[1]:
            new = tuple(int(round(v)) for v in res[0])
            pal = list(self.palette)
            pal[i] = new
            if new in self.forced_colors and self.palette[i] in self.forced_colors:
                self.forced_colors.remove(self.palette[i])
                self.forced_colors.append(new)
            self._set_palette_manual(pal)

    def _on_swatch_right(self, i):
        if not self.edit_pal_var.get() or not (0 <= i < len(self.palette)):
            return
        if len(self.palette) <= 1:
            self._set_status("Minimal palette harus ada 1 warna.")
            return
        old = self.palette[i]
        pal = list(self.palette)
        del pal[i]
        if old in self.forced_colors:
            self.forced_colors.remove(old)
        self._set_palette_manual(pal)
        self._set_status("Warna #%02x%02x%02x dihapus dari palette." % old)

    def _set_palette_manual(self, pal_list):
        self.loaded_palette = np.asarray(pal_list, dtype=np.float32)
        src = "Palette: manual (%d warna)" % len(pal_list)
        if self.forced_colors:
            src += " + %d warna wajib" % len(self.forced_colors)
        self.palette_src_var.set(src)
        self._sync_palette_state()
        self.schedule_process(0)

    def add_palette_color(self):
        res = colorchooser.askcolor(title="Tambah warna ke palette", parent=self.root)
        if res and res[1]:
            new = tuple(int(round(v)) for v in res[0])
            self._set_palette_manual(list(self.palette) + [new])
            self._set_status("#%02x%02x%02x ditambahkan ke palette." % new)

    def add_forced_color(self):
        res = colorchooser.askcolor(title="Warna wajib (selalu dipertahankan)",
                                    parent=self.root)
        if res and res[1]:
            new = tuple(int(round(v)) for v in res[0])
            if new not in self.forced_colors:
                self.forced_colors.append(new)
            src = "Palette: %s" % ("manual (%d warna)" % len(self.palette)
                                   if self.loaded_palette is not None else "otomatis (dari gambar)")
            src += " + %d warna wajib" % len(self.forced_colors)
            self.palette_src_var.set(src)
            self.schedule_process(0)
            self._set_status("#%02x%02x%02x jadi warna wajib - selalu ada di output." % new)

    def copy_hex(self, c):
        hexs = "#%02x%02x%02x" % c
        self.root.clipboard_clear()
        self.root.clipboard_append(hexs)
        self._set_status("%s di-copy ke clipboard" % hexs)

    def copy_all_hex(self):
        if not self.palette:
            return
        txt = "\n".join("#%02x%02x%02x" % c for c in self.palette)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self._set_status("%d hex di-copy ke clipboard" % len(self.palette))

    def _sync_edit_mode(self):
        on = self.edit_pal_var.get()
        if self.language == "en":
            self._set_status("Palette edit mode ON - click a swatch to change its color; right-click to remove it."
                             if on else "Palette edit mode OFF - click a swatch to copy its hex value.")
        else:
            self._set_status("Mode edit palette ON - klik swatch untuk ganti warna, klik kanan untuk hapus."
                             if on else "Mode edit palette OFF - klik swatch untuk copy hex.")

    def _set_status(self, text):
        if self.language == "en":
            text = _UI_EN.get(text, text)
            replacements = (
                ("Preset '", "Preset '"),
                (" diterapkan.", " applied."),
                (" disimpan:", " saved:"),
                (" dimuat dari ", " loaded from "),
                ("Disimpan:", "Saved:"),
                ("Gagal simpan:", "Save failed:"),
                ("Gagal membuka", "Failed to open"),
                ("Belum ada gambar", "No image loaded"),
                ("List dibersihkan.", "File list cleared."),
                ("Palette termuat", "Palette loaded"),
                ("warna wajib dipertahankan", "forced colors preserved"),
                ("alpha dipertahankan", "alpha preserved"),
                ("Proses full-res & simpan...", "Processing full resolution and saving..."),
                ("Batch processing", "Batch processing"),
                (" di-copy ke clipboard", " copied to clipboard"),
                ("ditambahkan ke palette", "added to palette"),
                ("jadi warna wajib - selalu ada di output", "set as forced color - always included in output"),
                ("dihapus dari palette", "removed from palette"),
                (" warna wajib", " forced colors"),
                ("warna ini.", " colors."),
            )
            for source, target in replacements:
                text = text.replace(source, target)
        self.status_var.set(text)

    # -- save ---------------------------------------------------------------

    def _output_path(self, src, suffix=None, fmt=None):
        base, _ext = os.path.splitext(src)
        suffix = self.suffix_var.get() if suffix is None else suffix
        suffix = suffix or "_ps1"
        fmt = (self.format_var.get() if fmt is None else fmt) or "PNG"
        ext = "." + fmt.lower()
        cand = base + suffix + ext
        n = 1
        while os.path.exists(cand):
            cand = "%s%s_%d%s" % (base, suffix, n, ext)
            n += 1
        return cand

    def _save_result(self, img, path, fmt=None, quality=None):
        """Simpan hasil; return catatan tambahan (mis. alpha dibuang)."""
        fmt = (fmt or self.format_var.get() or "PNG").upper()
        note = ""
        if fmt in ("JPG", "JPEG"):
            fmt = "JPEG"
            if img.mode == "RGBA":
                img = img.convert("RGB")
                note = " (alpha dibuang - JPG tidak dukung transparansi)"
            elif img.mode == "P":
                img = img.convert("RGB")
                note = " (palette di-flatten - JPG tidak dukung indexed)"
        elif fmt == "BMP" and img.mode == "RGBA":
            img = img.convert("RGB")
            note = " (alpha dibuang - BMP tidak dukung transparansi)"
        if fmt == "JPEG":
            q = int(self.quality_var.get() if quality is None else quality)
            img.save(path, format=fmt, quality=q, optimize=True, subsampling=0)
        else:
            img.save(path, format=fmt)
        return note

    def save_current(self):
        if self.current is None or self.orig_image is None:
            self._set_status("Belum ada gambar untuk disimpan.")
            return
        if self._busy:
            self._set_status("Sibuk - tunggu proses sekarang selesai dulu.")
            return
        settings = self.get_settings()
        img = self.orig_image
        pal = self.loaded_palette
        out_path = self._output_path(self.files[self.current])
        fmt = settings["format"]
        quality = settings["quality"]
        self._set_status("Proses full-res & simpan...")

        def work():
            try:
                out, _pl, _st = process_image(img, settings, pal)
                note = self._save_result(out, out_path, fmt=fmt, quality=quality)
                self.root.after(0, self._set_status, "Disimpan: %s%s" % (out_path, note))
            except Exception as exc:
                self.root.after(0, self._set_status, "Gagal simpan: %s" % exc)

        threading.Thread(target=work, daemon=True).start()

    def process_all(self):
        if not self.files:
            self._set_status("Belum ada gambar di list.")
            return
        if self._busy:
            self._set_status("Sibuk - tunggu proses sekarang selesai dulu.")
            return
        self._busy = True
        settings = self.get_settings()
        pal = self.loaded_palette
        fmt = settings["format"]
        quality = settings["quality"]
        suffix = settings["suffix"]
        # snapshot path output di main thread (akses var tkinter aman)
        jobs = [(p, self._output_path(p, suffix=suffix, fmt=fmt)) for p in self.files]

        def work():
            ok, fail = 0, []
            for i, (p, outp) in enumerate(jobs, 1):
                try:
                    img = Image.open(p)
                    img.load()
                    out, _pl, st = process_image(img, settings, pal)
                    note = self._save_result(out, outp, fmt=fmt, quality=quality)
                    ok += 1
                    msg = "[%d/%d] %s -> %s (%d warna)%s" % (
                        i, len(jobs), os.path.basename(p), os.path.basename(outp),
                        st["colors_used"], note)
                except Exception as exc:
                    fail.append((p, str(exc)))
                    msg = "[%d/%d] %s GAGAL: %s" % (i, len(jobs), os.path.basename(p), exc)
                self.root.after(0, self._set_status, msg)

            def done():
                self._busy = False
                tail = "Batch selesai: %d OK" % ok
                if fail:
                    tail += ", %d gagal (pertama: %s)" % (len(fail), fail[0][0])
                self._set_status(tail)
                self.schedule_process(0)

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()
        self._set_status("Batch processing %d file (full-res)..." % len(jobs))

    # -- palette IO ---------------------------------------------------------

    def export_palette(self):
        if not self.palette:
            self._set_status("Belum ada palette untuk disimpan.")
            return
        src = self.files[self.current] if self.current is not None else None
        init = (os.path.splitext(os.path.basename(src))[0] + "_palette") if src else "palette"
        path = filedialog.asksaveasfilename(
            title="Simpan palette", initialfile=init, defaultextension=".json",
            filetypes=[("JSON palette", "*.json")])
        if not path:
            return
        base, _ext = os.path.splitext(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "name": os.path.basename(base),
                    "colors": [list(c) for c in self.palette],
                    "forced_colors": [list(c) for c in self.forced_colors],
                    "bits": self._bits_labels.get(self.bits_var.get(), 0),
                }, f, indent=1)
            export_palette_png(base + ".png", self.palette)
            with open(base + ".hex.txt", "w", encoding="utf-8") as f:
                for i, c in enumerate(self.palette):
                    f.write("%3d  #%02x%02x%02x  rgb(%d,%d,%d)\n" % (
                        i, c[0], c[1], c[2], c[0], c[1], c[2]))
            self._set_status("Palette disimpan: %s (+ .png, .hex.txt)" % os.path.basename(path))
        except Exception as exc:
            messagebox.showerror("Gagal simpan palette", str(exc))

    def load_palette(self):
        path = filedialog.askopenfilename(title="Muat palette JSON",
                                          filetypes=[("JSON palette", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cols = [tuple(int(v) for v in c) for c in data["colors"]]
            if not (1 <= len(cols) <= 4096):
                raise ValueError("jumlah palette tidak valid: %d" % len(cols))
            for c in cols:
                if len(c) != 3 or not all(0 <= v <= 255 for v in c):
                    raise ValueError("warna tidak valid: %r" % (c,))
            self.loaded_palette = np.asarray(cols, np.float32)
            self.forced_colors = [tuple(int(v) for v in c)
                                  for c in data.get("forced_colors", [])]
            src = "Palette termuat: %d warna (%s)" % (len(cols), os.path.basename(path))
            if self.forced_colors:
                src += " + %d warna wajib" % len(self.forced_colors)
            self.palette_src_var.set(src)
            self._sync_palette_state()
            self.schedule_process(0)
            self._set_status("Palette termuat - semua gambar akan di-map ke %d warna ini." % len(cols))
        except Exception as exc:
            messagebox.showerror("Gagal muat palette", str(exc))

    def clear_loaded_palette(self):
        if self.loaded_palette is None and not self.forced_colors:
            return
        self.loaded_palette = None
        self.forced_colors = []
        self.palette_src_var.set("Palette: otomatis (dari gambar)")
        self._sync_palette_state()
        self.schedule_process(0)

    def _sync_palette_state(self):
        locked = self.loaded_palette is not None
        self.colors_spin.configure(state="disabled" if locked else "normal")


# ---------------------------------------------------------------------------
# Self-test (headless-ish: window di-withdraw, pipeline dijalankan penuh)
# ---------------------------------------------------------------------------

def _make_test_image(w=160, h=120):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = 110 + 90 * np.sin(xx / 23.0) * np.cos(yy / 31.0)
    g = 90 + 80 * np.cos((xx + yy) / 41.0)
    b = 150 + 70 * np.sin(yy / 17.0)
    img = np.dstack([r, g, b]).astype(np.uint8)
    d = ImageDraw.Draw(Image.fromarray(img))
    d.ellipse([30, 20, 90, 80], fill=(230, 60, 40))
    d.rectangle([100, 60, 150, 110], fill=(40, 200, 120))
    return Image.fromarray(img)


def selftest():
    root_cls = TkinterDnD.Tk if _HAS_DND else tk.Tk
    root = root_cls()
    root.withdraw()
    app = App(root)
    checks = []

    def check(name, cond, extra=""):
        checks.append((name, bool(cond), extra))
        print(("PASS" if cond else "FAIL"), "-", name, extra)

    img = _make_test_image()

    # 1. basic quantization
    s = {"colors": 32, "bits": 5, "dither": "none", "dither_strength": 1.0,
         "resize": None, "indexed": False, "forced_colors": []}
    out, pal, st = process_image(img, s)
    check("basic: palette <= 32", len(pal) <= 32, "(%d warna)" % len(pal))
    check("basic: size preserved", out.size == img.size)
    check("basic: 5-bit grid", all(
        abs(v - round(v * 31.0 / 255.0) * (255.0 / 31.0)) <= 0.51
        for c in pal for v in c))
    arr = np.asarray(out)
    check("basic: output hanya berisi warna palette",
          set(map(tuple, np.unique(arr.reshape(-1, 3), axis=0).tolist())) <= set(pal))

    # 2. bit depth options
    for bits, levels in ((4, 15), (6, 63), (0, 255)):
        _o, p_b, _st = process_image(img, dict(s, bits=bits))
        ok = all(abs(v - round(v * levels / 255.0) * (255.0 / levels)) <= 0.51
                 for c in p_b for v in c)
        check("bits=%d snap ke %d level" % (bits, levels + 1), ok)

    # 3. resize + bayer
    out2, pal2, st2 = process_image(img, dict(s, resize=("max", 64), dither="bayer4", colors=16))
    check("resize max 64", max(out2.size) == 64, str(out2.size))
    check("bayer4: palette <= 16", len(pal2) <= 16, "(%d warna)" % len(pal2))

    # 4. bayer2 + strength 0 == none
    out_none, _pn, _sn = process_image(img, s)
    out_b0, _pb, _sb = process_image(img, dict(s, dither="bayer2", dither_strength=0.0))
    check("bayer2 strength 0 == none",
          np.array_equal(np.asarray(out_none), np.asarray(out_b0)))
    out_b1, _pb1, _sb1 = process_image(img, dict(s, dither="bayer2", dither_strength=1.0))
    check("bayer2 strength 1 beda dari none",
          not np.array_equal(np.asarray(out_none), np.asarray(out_b1)))

    # 5. floyd-steinberg + strength
    out3, pal3, _ = process_image(img, dict(s, dither="fs", colors=24))
    check("fs: palette <= 24", len(pal3) <= 24, "(%d warna)" % len(pal3))
    check("fs: size preserved", out3.size == img.size)
    out_fs0, _pf0, _sf0 = process_image(img, dict(s, dither="fs", dither_strength=0.0))
    check("fs strength 0 == none (tanpa difusi)",
          np.array_equal(np.asarray(out_none), np.asarray(out_fs0)))

    # 6. palette override
    override = np.asarray([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)], np.float32)
    out4, pal4, _ = process_image(img, dict(s, colors=200), override)
    check("override: palette tepat 4", len(pal4) == 4, "(%d warna)" % len(pal4))
    check("override: output hanya 4 warna",
          len(np.unique(np.asarray(out4).reshape(-1, 3), axis=0)) <= 4)

    # 7. forced colors (di-snap ke grid bit aktif, itu memang perilaku yang benar)
    forced = [(255, 0, 128), (12, 34, 56)]
    forced_snapped = [tuple(int(np.clip(round(float(v)), 0, 255)) for v in snap_bits(np.asarray(c, np.float32), 5))
                      for c in forced]
    out5, pal5, st5 = process_image(img, dict(s, colors=8, forced_colors=forced))
    check("forced: warna wajib (snapped) ada di palette",
          all(c in pal5 for c in forced_snapped),
          "(%s)" % [c for c in forced_snapped if c in pal5])
    check("forced: stats forced_kept", st5["forced_kept"] >= 1, "(%d)" % st5["forced_kept"])

    # 8. indexed PNG
    out6, pal6, _ = process_image(img, dict(s, indexed=True, colors=16))
    check("indexed: mode P", out6.mode == "P")
    check("indexed: palette terpasang", len(out6.getpalette()) // 3 >= len(pal6))

    # 9. alpha preserved
    rgba = img.convert("RGBA")
    a = np.array(rgba)
    a[..., 3] = (np.arange(a.shape[0] * a.shape[1]).reshape(a.shape[:2]) % 256).astype(np.uint8)
    rgba = Image.fromarray(a, "RGBA")
    out7, _pl7, st7 = process_image(rgba, s)
    check("alpha: mode RGBA", out7.mode == "RGBA")
    check("alpha: alpha identik", np.array_equal(np.asarray(out7)[..., 3], a[..., 3]))

    # 10. palette JSON roundtrip + forced
    import tempfile
    tmp = tempfile.mkdtemp(prefix="cq_selftest_")
    pjson = os.path.join(tmp, "pal.json")
    with open(pjson, "w", encoding="utf-8") as f:
        json.dump({"name": "t", "colors": [list(c) for c in pal],
                   "forced_colors": [list(c) for c in forced]}, f)
    with open(pjson, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    check("palette json roundtrip",
          [tuple(c) for c in loaded["colors"]] == pal and
          [tuple(c) for c in loaded["forced_colors"]] == [tuple(c) for c in forced])
    ppng = os.path.join(tmp, "pal.png")
    export_palette_png(ppng, pal)
    check("palette png exported", os.path.getsize(ppng) > 100)

    # 11. output path: custom suffix + format
    app.suffix_var.set("_low")
    app.format_var.set("BMP")
    p1 = app._output_path(os.path.join(tmp, "tex.png"))
    check("output path custom suffix/format", p1.endswith("_low.bmp"), os.path.basename(p1))
    app.suffix_var.set("_ps1")
    app.format_var.set("PNG")
    p1b = app._output_path(os.path.join(tmp, "tex.png"))
    open(p1b, "wb").close()
    p2 = app._output_path(os.path.join(tmp, "tex.png"))
    check("output path collision", p1b != p2 and not os.path.exists(p2), os.path.basename(p2))

    # 12. custom resize parsing lewat get_settings
    app.resize_var.set("Custom: W x H...")
    app.custom_wh = "40x30"
    gs = app.get_settings()
    check("custom WxH resize", gs["resize"] == (40, 30), str(gs["resize"]))
    app.resize_var.set("Custom: max N...")
    app.custom_max = 77
    check("custom max N resize", app.get_settings()["resize"] == ("max", 77))
    app.resize_var.set("Original (tanpa resize)")
    check("resize none", app.get_settings()["resize"] is None)

    # 13. preset apply + roundtrip
    pname, preset = BUILTIN_PRESETS[0]
    app.apply_preset(preset)
    gs2 = app.get_settings()
    check("preset apply: settings cocok",
          gs2["colors"] == preset["colors"] and gs2["bits"] == preset["bits"]
          and gs2["dither"] == preset["dither"] and gs2["resize_key"] == preset["resize"]
          and gs2["suffix"] == preset["suffix"] and gs2["format"] == preset["format"])
    ppreset = os.path.join(tmp, "preset.json")
    with open(ppreset, "w", encoding="utf-8") as f:
        json.dump({"name": "X", "settings": app.get_settings()}, f)
    with open(ppreset, "r", encoding="utf-8") as f:
        s_loaded = json.load(f)["settings"]
    check("preset json roundtrip", json.loads(json.dumps(gs2)) == s_loaded)
    app.apply_preset(BUILTIN_PRESETS[1][1])
    check("preset apply kedua (PS1 Clean)", app.get_settings()["colors"] == 32)

    # 14. palette edit manual -> override (warna yang nggak kepakai di-prune otomatis)
    app._set_palette_manual([(10, 20, 30), (200, 100, 50), (0, 0, 0)])
    out8, pal8, _ = process_image(img, app.get_settings(), app.loaded_palette)
    check("manual palette: <= 3 warna", len(pal8) <= 3, "(%d)" % len(pal8))
    check("manual palette: output hanya warna palette",
          set(map(tuple, np.unique(np.asarray(out8).reshape(-1, 3), axis=0).tolist())) <= set(pal8))
    app.clear_loaded_palette()
    check("clear palette -> auto", app.loaded_palette is None)

    # 15. forced color lewat app
    app.forced_colors = [(255, 255, 0)]
    out9, pal9, st9 = process_image(img, app.get_settings(), None)
    check("app forced color kepakai", (255, 255, 0) in pal9 or
          tuple(int(np.clip(round(float(v)), 0, 255)) for v in
                snap_bits(np.asarray((255, 255, 0), np.float32), 5)) in pal9)
    app.forced_colors = []

    # 16. mono image
    mono = Image.new("RGB", (20, 20), (10, 20, 30))
    out10, pal10, _ = process_image(mono, s)
    a10 = np.asarray(out10)
    check("mono image", len(pal10) == 1 and bool((a10 == a10[0, 0]).all()),
          "(%d warna, output konstan %s)" % (len(pal10), tuple(a10[0, 0])))

    # 18. JPG output + quality + format handling
    app.format_var.set("JPG")
    app.quality_var.set(55)
    jpg_path = app._output_path(os.path.join(tmp, "tex.png"))
    check("output path jpg", jpg_path.endswith("_ps1.jpg"), os.path.basename(jpg_path))
    note = app._save_result(out, jpg_path)
    check("jpg save RGB", os.path.exists(jpg_path) and os.path.getsize(jpg_path) > 100, note)
    with Image.open(jpg_path) as im:
        check("jpg valid RGB", im.format == "JPEG" and im.mode == "RGB")
    note2 = app._save_result(out7, jpg_path)  # RGBA
    check("jpg: alpha dibuang", "alpha dibuang" in note2, note2)
    with Image.open(jpg_path) as im2:
        check("jpg: rgba->rgb", im2.mode == "RGB")
    note3 = app._save_result(out6, jpg_path)  # P mode
    check("jpg: palette di-flatten", "flatten" in note3, note3)
    out_i2, _pi2, _si2 = process_image(img, dict(s, format="JPG", indexed=True))
    check("indexed diabaikan untuk JPG", out_i2.mode != "P", out_i2.mode)
    app.quality_var.set(95)
    app._save_result(out, jpg_path)
    check("jpg quality 95 OK", os.path.getsize(jpg_path) > 100)
    app.format_var.set("PNG")
    app.quality_var.set(90)
    app._sync_quality_state()
    check("quality spin disabled di PNG", str(app.quality_spin.cget("state")) == "disabled")
    app.format_var.set("JPG")
    app._sync_quality_state()
    check("quality spin aktif di JPG", str(app.quality_spin.cget("state")) == "normal")
    app.format_var.set("BMP")
    bmp_path = app._output_path(os.path.join(tmp, "tex.png"))
    note5 = app._save_result(out7, bmp_path)
    check("bmp: alpha dibuang", "alpha dibuang" in note5 and bmp_path.endswith(".bmp"))
    app.format_var.set("PNG")
    app._sync_quality_state()
    app.apply_preset(BUILTIN_PRESETS[0][1])
    check("preset quality default 90", int(app.quality_var.get()) == 90)

    # 19. v2: settings_signature cache + preview cap + kmeans_iters
    sig1 = settings_signature(s)
    check("settings_signature deterministik", sig1 == settings_signature(dict(s)))
    check("settings_signature beda kalau colors beda",
          settings_signature(dict(s, colors=64)) != sig1)
    check("settings_signature beda kalau forced beda",
          settings_signature(dict(s, forced_colors=[(1, 2, 3)])) != sig1)
    big = _make_test_image(1024, 768)
    small, capped = app._preview_image(big, 640)
    check("preview cap: gambar besar dipersempit",
          capped and max(small.size) == 640, str(small.size))
    small2, capped2 = app._preview_image(_make_test_image(100, 80), 640)
    check("preview cap: gambar kecil nggak diubah",
          not capped2 and small2.size == (100, 80))
    o_a, p_a, _ = process_image(img, s, None, kmeans_iters=2)
    o_b, p_b, _ = process_image(img, s, None, kmeans_iters=25)
    check("kmeans_iters param jalan", len(p_a) >= 1 and len(p_b) >= 1,
          "(%d vs %d warna)" % (len(p_a), len(p_b)))
    # save path: suffix/format bisa di-pass eksplisit (thread-safe)
    p_expl = app._output_path(os.path.join(tmp, "tex.png"), suffix="_v2", fmt="JPG")
    check("output path eksplisit", p_expl.endswith("_v2.jpg"), os.path.basename(p_expl))

    # 17. UI + DnD
    check("UI built", app.listbox is not None and app.pal_canvas is not None
          and app.preset_box is not None and app.strength_scale is not None)
    check("DnD registered", _HAS_DND and hasattr(root, "drop_target_register"))

    # 17b. Style noir (sakiko.my.id): font bundled ter-resolve + token warna
    try:
        from tkinter import font as tkfont
        fams = set(tkfont.families())
    except Exception:  # pragma: no cover
        fams = set()
    if _BUNDLED_FONTS_LOADED:
        check("font Barlow bundled ter-load",
              "Barlow" in fams and "Barlow Condensed" in fams,
              "families: %s" % sorted(f for f in fams if "Barlow" in f))
        check("font display pakai Barlow Condensed",
              _DISPLAY_FONT[0].startswith("Barlow"), str(_DISPLAY_FONT))
    else:
        check("font Barlow bundled ter-load (folder fonts/ tidak ada - fallback)",
              True, "fallback: %s" % (_DISPLAY_FONT,))
    check("token warna noir lengkap",
          C["bg"] == "#09090b" and C["surface"] == "#131316"
          and C["raised"] == "#1c1c21" and C["ink"] == "#ffffff")
    def _walk(w):
        yield w
        for c in w.winfo_children():
            yield from _walk(c)

    check("masthead wordmark ada",
          any(isinstance(w, tk.Label) and w.cget("text") == "COLOR QUANTIZER"
              for w in _walk(root)))
    check("masthead logo terpasang",
          getattr(app, "_logo_img", None) is not None
          and any(isinstance(w, tk.Label) and w.cget("image") != ""
                  for w in _walk(root)),
          "logo.jpg: %s" % os.path.join(
              getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
              "logo.jpg"))

    # Language toggle changes presentation only, never the actual settings.
    app.apply_preset(BUILTIN_PRESETS[0][1])
    settings_before_language = app.get_settings().copy()
    app.language_var.set("English")
    app._on_language_changed()
    english_open_button = any(isinstance(w, ttk.Button) and w.cget("text") == "Open image..."
                              for w in _walk(root))
    check("English UI toggle preserves settings",
          app.language == "en" and app.get_settings() == settings_before_language
          and english_open_button)
    app.language_var.set("Bahasa Indonesia")
    app._on_language_changed()
    indonesian_open_button = any(isinstance(w, ttk.Button) and w.cget("text") == "Buka gambar..."
                                 for w in _walk(root))
    check("Indonesian UI toggle restores options",
          app.language == "id" and app.get_settings() == settings_before_language
          and indonesian_open_button)

    root.destroy()
    failed = [c for c in checks if not c[1]]
    print("\n%d/%d checks passed" % (len(checks) - len(failed), len(checks)))
    if failed:
        for name, _ok, extra in failed:
            print("  FAILED:", name, extra)
        sys.exit(1)
    print("SELFTEST OK")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    root = TkinterDnD.Tk() if _HAS_DND else tk.Tk()
    app = App(root)

    argv_imgs = [a for a in sys.argv[1:]
                 if os.path.splitext(a)[1].lower() in IMAGE_EXTS and os.path.isfile(a)]
    if argv_imgs:
        app.add_files(argv_imgs)

    root.mainloop()


if __name__ == "__main__":
    main()
