from io import BytesIO

from PIL import Image, ImageOps

MODEL_IMAGE_BYTES = 2 * 1024 * 1024
MODEL_MAX_EDGE = 1600


def prepare_model_image(image: bytes, mime: str) -> tuple[bytes, str]:
    """Bound large inference payloads while leaving the stored original untouched.

    Re-encoding also applies EXIF orientation and drops metadata. Small uploads pass
    through unchanged to avoid unnecessary quality loss and CPU work.
    """
    if len(image) <= MODEL_IMAGE_BYTES:
        return image, mime

    with Image.open(BytesIO(image)) as source:
        oriented = ImageOps.exif_transpose(source)
        if oriented.mode not in {"RGB", "L"}:
            oriented = oriented.convert("RGB")
        for edge in (MODEL_MAX_EDGE, 1200, 960):
            resized = oriented.copy()
            resized.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            for quality in (84, 72, 60):
                output = BytesIO()
                resized.save(output, format="JPEG", quality=quality, optimize=True)
                result = output.getvalue()
                if len(result) <= MODEL_IMAGE_BYTES:
                    return result, "image/jpeg"
    raise ValueError("Photo could not be reduced for model inference")
