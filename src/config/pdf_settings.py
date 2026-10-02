from pydantic_settings import BaseSettings


class PDFExtractorSettings(BaseSettings):

    min_text_length: int = 50
    sample_pages: int = 3

    ocr_engine: str = "easyocr" 
    ocr_languages: list[str] = ["ru", "en"]
    ocr_dpi: int = 300
    ocr_use_gpu: bool = False
    ocr_confidence_threshold: float = 0.5

    enable_deskew: bool = True
    enable_denoise: bool = True
    enable_binarization: bool = True

    enable_table_extraction: bool = True
    enable_pp_structure: bool = False
    camelot_flavor: str = "lattice"

    class Config:
        env_prefix = "PDF_EXTRACTOR_"
        env_file = ".env"
        extra = "ignore"


pdf_settings = PDFExtractorSettings()