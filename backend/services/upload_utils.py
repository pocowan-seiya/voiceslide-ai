"""Upload file type helpers for VoiSlide hybrid mode."""

import os
from typing import Optional

from fastapi import UploadFile


def is_pdf_upload(upload_file: Optional[UploadFile]) -> bool:
    """Return True when an uploaded slide file is a PDF.

    The frontend normally sends file_type=pdf, but users can upload files with
    uppercase extensions such as `.PDF`. Older clients may then classify the
    file as `images`, so the backend must also infer the type safely.
    """
    if not upload_file or not upload_file.filename:
        return False
    filename = upload_file.filename.lower()
    content_type = (upload_file.content_type or "").lower()
    return filename.endswith(".pdf") or content_type == "application/pdf"


def is_supported_slide_image(upload_file: Optional[UploadFile]) -> bool:
    if not upload_file or not upload_file.filename:
        return False
    return os.path.splitext(upload_file.filename)[1].lower() in {".png", ".jpg", ".jpeg"}