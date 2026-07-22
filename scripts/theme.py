"""Derive a full light/dark CSS token set from a single accent hex color.

stdlib-only (colorsys) — no design-tool dependency. Neutrals get a slight
hue bias toward the accent so they read as chosen rather than default grey.
"""
import colorsys

DEFAULT_ACCENT = "#2F6FED"


def _hex_to_rgb01(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return r, g, b


def _rgb01_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def _shade(hex_color, target_lightness, blend=0.6, saturation_factor=1.0):
    """Blend this color's lightness toward a target, keeping its hue.

    Blending toward an absolute target (rather than multiplying the existing
    lightness) gives predictable results regardless of how light or dark the
    input accent color already is.
    """
    r, g, b = _hex_to_rgb01(hex_color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.0, min(1.0, l + (target_lightness - l) * blend))
    s = max(0.0, min(1.0, s * saturation_factor))
    return _rgb01_to_hex(colorsys.hls_to_rgb(h, l, s))


def _hue_of(hex_color):
    r, g, b = _hex_to_rgb01(hex_color)
    h, _, _ = colorsys.rgb_to_hls(r, g, b)
    return h


def _neutral(hue, lightness, saturation=0.04):
    return _rgb01_to_hex(colorsys.hls_to_rgb(hue, lightness, saturation))


def _rgba(hex_color, alpha):
    r, g, b = (round(c * 255) for c in _hex_to_rgb01(hex_color))
    return f"rgba({r}, {g}, {b}, {alpha})"


def derive_theme(accent_hex=DEFAULT_ACCENT):
    """Return {"light": {css_var: value, ...}, "dark": {...}}."""
    hue = _hue_of(accent_hex)

    light_accent = accent_hex
    light_accent_dark = _shade(accent_hex, target_lightness=0.25, blend=0.65, saturation_factor=1.05)
    light_accent_light = _shade(accent_hex, target_lightness=0.78, blend=0.6, saturation_factor=0.85)

    dark_accent = _shade(accent_hex, target_lightness=0.70, blend=0.7)
    dark_accent_dark = _shade(accent_hex, target_lightness=0.45, blend=0.4)
    dark_accent_light = _shade(accent_hex, target_lightness=0.85, blend=0.65, saturation_factor=0.85)

    light = {
        "--bg-page": _neutral(hue, 0.98),
        "--bg-card": _neutral(hue, 1.0, 0.0),
        "--bg-sunken": _neutral(hue, 0.95),
        "--text-primary": _neutral(hue, 0.12, 0.03),
        "--text-secondary": _neutral(hue, 0.40, 0.05),
        "--border": _neutral(hue, 0.90),
        "--accent": light_accent,
        "--accent-dark": light_accent_dark,
        "--accent-light": light_accent_light,
        "--accent-tint": _rgba(light_accent, 0.08),
        "--status-good": "#2D7D46",
        "--status-good-bg": "#E9F4EC",
        "--status-warn": "#9C6B12",
        "--status-warn-bg": "#FBF1DD",
        "--shadow": "0 1px 2px rgba(20,20,20,0.05), 0 10px 24px -16px rgba(20,20,20,0.16)",
        "--shadow-hover": "0 6px 14px rgba(20,20,20,0.10), 0 20px 36px -18px rgba(20,20,20,0.22)",
    }

    dark = {
        "--bg-page": _neutral(hue, 0.08),
        "--bg-card": _neutral(hue, 0.13),
        "--bg-sunken": _neutral(hue, 0.16),
        "--text-primary": _neutral(hue, 0.95, 0.02),
        "--text-secondary": _neutral(hue, 0.72, 0.04),
        "--border": _neutral(hue, 0.24),
        "--accent": dark_accent,
        "--accent-dark": dark_accent_dark,
        "--accent-light": dark_accent_light,
        "--accent-tint": _rgba(dark_accent, 0.12),
        "--status-good": "#63C084",
        "--status-good-bg": "rgba(99, 192, 132, 0.14)",
        "--status-warn": "#E6BB5C",
        "--status-warn-bg": "rgba(230, 187, 92, 0.14)",
        "--shadow": "0 1px 2px rgba(0,0,0,0.4), 0 10px 26px -14px rgba(0,0,0,0.55)",
        "--shadow-hover": "0 6px 16px rgba(0,0,0,0.5), 0 22px 40px -16px rgba(0,0,0,0.65)",
    }

    return {"light": light, "dark": dark}


def css_vars_block(vars_dict, indent="    "):
    return "\n".join(f"{indent}{k}: {v};" for k, v in vars_dict.items())
