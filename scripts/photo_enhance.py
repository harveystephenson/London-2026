"""The single, deterministic photo-enhancement recipe.

Shared by make_edit_review.py (which renders candidates for the user's
before/after approval pass) and build_gallery.py (which applies it to
approved photos during encoding). Keeping it in one place guarantees the
candidate the user approved is pixel-identical to what ships.

Deliberately conservative: fix flat/hazy exposure, nudge color, sharpen
gently. No geometry changes, no cropping, no AI.
"""

from PIL import ImageEnhance, ImageFilter, ImageOps

# Bump this if the recipe ever changes materially — make_edit_review.py uses
# it to invalidate previously rendered candidates.
RECIPE_VERSION = 2


def enhance(img):
    """Enhance a PIL image (expects RGB, already resized to output size).

    v2: sharpening softened after user feedback that skin (hands) looked
    more wrinkled — smaller radius/amount and a higher threshold, which
    skips low-contrast gradients like skin while still crisping real edges.
    """
    try:
        img = ImageOps.autocontrast(img, cutoff=1, preserve_tone=True)
    except TypeError:  # Pillow < 8.2 has no preserve_tone
        img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Color(img).enhance(1.08)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=50, threshold=8))
    return img
