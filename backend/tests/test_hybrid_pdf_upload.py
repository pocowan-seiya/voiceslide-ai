"""Regression tests for hybrid mode PDF uploads."""

import io

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers


def make_upload(filename: str, content_type: str = "application/octet-stream") -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(b"dummy"),
        headers=Headers({"content-type": content_type}),
    )


def test_pdf_upload_detection_is_case_insensitive():
    from services.upload_utils import is_pdf_upload

    assert is_pdf_upload(make_upload("slides.pdf")) is True
    assert is_pdf_upload(make_upload("slides.PDF")) is True
    assert is_pdf_upload(make_upload("slides", "application/pdf")) is True
    assert is_pdf_upload(make_upload("slides.png", "image/png")) is False


def test_slide_image_detection_rejects_pdf_in_image_mode():
    from services.upload_utils import is_supported_slide_image

    assert is_supported_slide_image(make_upload("slide.PNG", "image/png")) is True
    assert is_supported_slide_image(make_upload("slide.jpeg", "image/jpeg")) is True
    assert is_supported_slide_image(make_upload("slides.PDF", "application/pdf")) is False


@pytest.mark.asyncio
async def test_pdf_to_images_handles_pdf_without_external_api(tmp_path):
    fitz = pytest.importorskip("fitz")
    from services.slide_analyzer import pdf_to_images

    pdf_path = tmp_path / "sample.PDF"
    output_dir = tmp_path / "images"
    output_dir.mkdir()

    doc = fitz.open()
    page = doc.new_page(width=640, height=360)
    page.insert_text((72, 72), "VoiSlide PDF conversion regression")
    doc.save(pdf_path)
    doc.close()

    image_paths = await pdf_to_images(str(pdf_path), str(output_dir))

    assert len(image_paths) == 1
    assert image_paths[0].endswith("slide_001.png")
    assert (output_dir / "slide_001.png").exists()