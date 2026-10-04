from pydantic_settings import BaseSettings, SettingsConfigDict


class PDFExtractorSettings(BaseSettings):

    min_text_length: int = 50
    sample_pages: int = 3

    ocr_engine: str = "easyocr"
    ocr_languages: list[str] = ["ru"]
    ocr_dpi: int = 300
    ocr_use_gpu: bool = False
    ocr_confidence_threshold: float = 0.5

    enable_deskew: bool = True
    enable_denoise: bool = True
    enable_binarization: bool = True
    binarization_method: str = "otsu"     
    enable_multi_pass: bool = True      
    multi_pass_methods: list[str] = ["otsu", "adaptive"]
    enable_postprocess: bool = True  
    enable_dedup: bool = True     

    enable_table_extraction: bool = True
    enable_pp_structure: bool = False
    camelot_flavor: str = "lattice"

    model_config = SettingsConfigDict(
        env_prefix="PDF_EXTRACTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


pdf_settings = PDFExtractorSettings()
