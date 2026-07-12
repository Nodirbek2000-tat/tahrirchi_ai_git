"""PDF <-> DOCX konvertatsiyasi.

PDF -> DOCX: pdf2docx (matn, rasm, jadval, joylashuv saqlanadi).
DOCX -> PDF: LibreOffice (serverda o'rnatilgan bo'lishi shart) — asl style/joylashuvni
aniq render qiladi.
"""

import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# pdf2docx juda ko'p log yozadi — jimlashtiramiz
logging.getLogger("pdf2docx").setLevel(logging.ERROR)

_SOFFICE_TIMEOUT = 180  # soniya


def pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    """PDF ni DOCX ga o'giradi (matn, rasm, jadval, joylashuv bilan)."""
    from pdf2docx import Converter

    # pdf2docx log shovqinini o'chirish (import'dan keyin)
    logging.getLogger("pdf2docx").setLevel(logging.ERROR)

    cv = Converter(pdf_path)
    try:
        cv.convert(docx_path, start=0, end=None)
    finally:
        cv.close()


def docx_to_pdf(docx_path: str, out_pdf_path: str) -> None:
    """DOCX ni PDF ga o'giradi (LibreOffice headless).

    Har chaqiruv uchun alohida profil — bir vaqtda bir nechta konvertatsiya
    bir-biriga xalaqit bermaydi.
    """
    outdir = os.path.dirname(out_pdf_path) or "."
    profile = tempfile.mkdtemp(prefix="lo_profile_")
    try:
        cmd = [
            "soffice",
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            "pdf",
            "--outdir",
            outdir,
            docx_path,
        ]
        result = subprocess.run(
            cmd,
            timeout=_SOFFICE_TIMEOUT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"soffice xatosi: {result.stderr.decode(errors='ignore')[:300]}"
            )
        # LibreOffice natija nomi = docx bazasi + .pdf
        produced = os.path.join(
            outdir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
        )
        if not os.path.exists(produced):
            raise RuntimeError("PDF yaratilmadi (soffice)")
        if os.path.abspath(produced) != os.path.abspath(out_pdf_path):
            shutil.move(produced, out_pdf_path)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
