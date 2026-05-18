"""
Module d'extraction de texte depuis un CV PDF.
Supporte les PDFs natifs (texte) et scannés (OCR via Tesseract).
"""
import io
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from loguru import logger

from app.config import settings

# Configuration du chemin Tesseract pour Windows
pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

ExtractionMethod = Literal["native", "ocr", "hybrid"]


class PDFExtractor:
    """Extrait le texte d'un CV PDF, qu'il soit natif ou scanné."""

    # Seuil minimum de caractères pour considérer un PDF comme "natif"
    MIN_NATIVE_CHARS = 100

    def __init__(self, ocr_languages: str = "fra+eng"):
        """
        :param ocr_languages: codes Tesseract pour les langues à reconnaître
        """
        self.ocr_languages = ocr_languages

    def extract(self, pdf_source: bytes | str | Path) -> dict:
        """
        Extrait le texte d'un PDF.

        :param pdf_source: bytes du PDF, ou chemin vers le fichier
        :return: dict avec text, method, num_pages, char_count
        """
        # Charger le PDF
        if isinstance(pdf_source, (str, Path)):
            doc = fitz.open(str(pdf_source))
            source_name = Path(pdf_source).name
        else:
            doc = fitz.open(stream=pdf_source, filetype="pdf")
            source_name = "uploaded_file"

        num_pages = len(doc)
        logger.info(f"Extraction de {source_name} ({num_pages} pages)")

        # 1) Tentative extraction native (rapide)
        native_text = self._extract_native(doc)
        char_count = len(native_text.strip())

        # 2) Décision : natif suffisant ou OCR nécessaire ?
        if char_count >= self.MIN_NATIVE_CHARS:
            logger.info(f"Extraction native réussie ({char_count} caractères)")
            doc.close()
            return {
                "text": native_text,
                "method": "native",
                "num_pages": num_pages,
                "char_count": char_count,
            }

        # 3) Fallback OCR (CV scanné)
        logger.info(f"Texte natif insuffisant ({char_count} chars) → OCR")
        ocr_text = self._extract_ocr(doc)
        doc.close()

        return {
            "text": ocr_text,
            "method": "ocr",
            "num_pages": num_pages,
            "char_count": len(ocr_text.strip()),
        }

    def _extract_native(self, doc: fitz.Document) -> str:
        """Extraction texte natif via PyMuPDF (rapide, ~50 ms)."""
        chunks = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                chunks.append(text)
        return "\n".join(chunks)

    def _extract_ocr(self, doc: fitz.Document) -> str:
        """Extraction par OCR Tesseract (lent, ~2-5 s par page)."""
        chunks = []
        for i, page in enumerate(doc):
            # Convertir la page en image haute résolution
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # OCR
            text = pytesseract.image_to_string(img, lang=self.ocr_languages)
            if text.strip():
                chunks.append(text)
            logger.debug(f"OCR page {i+1}/{len(doc)} : {len(text)} chars")

        return "\n".join(chunks)


# Singleton réutilisable
pdf_extractor = PDFExtractor()