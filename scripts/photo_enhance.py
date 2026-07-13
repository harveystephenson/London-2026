"""The single, deterministic photo-enhancement recipe.

Shared by make_edit_review.py (which renders candidates for the user's
before/after approval pass) and build_gallery.py (which applies it to
approved photos during encoding). Keeping it in one place guarantees the
candidate the user approved is pixel-identical to what ships.

Deliberately conservative: fix flat/hazy exposure, nudge color, sharpen
gently. No geometry changes, no cropping, no AI.
"""

from PIL import ImageEnhance, ImageFilter, ImageOps

# Bump this if the recipe ever changes materially — apply_photo_edits.py /
# build_gallery.py can use it to invalidate previously encoded outputs.
RECIPE_VERSION = 1


def enhance(img):
    """Enhance a PIL image (expects RGB, already resized to output size)."""
    try:
        img = ImageOps.autocontrast(img, cutoff=1, preserve_tone=True)
    except TypeError:  # Pillow < 8.2 has no preserve_tone
        img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Color(img).enhance(1.08)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=3))
    return img
