import os

from services.files.base import BaseProcessor
from services.files.docx_processor import DocxProcessor
from services.files.pdf_processor import PdfProcessor
from services.files.pptx_processor import PptxProcessor
from services.files.txt_processor import TxtProcessor
from services.files.xlsx_processor import XlsxProcessor

_PROCESSORS: dict[str, type[BaseProcessor]] = {
    ".docx": DocxProcessor,
    ".xlsx": XlsxProcessor,
    ".pptx": PptxProcessor,
    ".pdf": PdfProcessor,
    ".txt": TxtProcessor,
}

SUPPORTED_EXTENSIONS = tuple(_PROCESSORS.keys())


class UnsupportedFileError(Exception):
    pass


def get_processor(file_name: str) -> BaseProcessor:
    ext = os.path.splitext(file_name)[1].lower()
    processor_cls = _PROCESSORS.get(ext)
    if processor_cls is None:
        raise UnsupportedFileError(ext)
    return processor_cls()
