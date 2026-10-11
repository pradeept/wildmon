from io import BytesIO
from os import urandom

from PIL import Image

from app.ai.image_prep import MODEL_IMAGE_BYTES, prepare_model_image


def test_small_model_image_is_left_unchanged():
    image = b"small image"
    assert prepare_model_image(image, "image/jpeg") == (image, "image/jpeg")


def test_large_photo_is_bounded_for_inference():
    source = Image.frombytes("RGB", (1800, 1800), urandom(1800 * 1800 * 3))
    original = BytesIO()
    source.save(original, format="PNG")
    raw = original.getvalue()
    assert len(raw) > MODEL_IMAGE_BYTES

    prepared, mime = prepare_model_image(raw, "image/png")

    assert mime == "image/jpeg"
    assert len(prepared) <= MODEL_IMAGE_BYTES
    assert raw == original.getvalue()
    with Image.open(BytesIO(prepared)) as result:
        assert max(result.size) <= 1600


def test_large_phone_photo_keeps_orientation_without_exif():
    source = Image.frombytes("RGB", (1800, 1200), urandom(1800 * 1200 * 3))
    exif = Image.Exif()
    exif[274] = 6
    original = BytesIO()
    source.save(original, format="JPEG", quality=98, exif=exif)

    prepared, mime = prepare_model_image(original.getvalue(), "image/jpeg")

    assert mime == "image/jpeg"
    with Image.open(BytesIO(prepared)) as result:
        assert result.width < result.height
        assert result.getexif().get(274) is None
