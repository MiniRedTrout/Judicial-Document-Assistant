import time
from difflib import SequenceMatcher
from pathlib import Path

from src.config import pdf_settings
from src.schemas.pdf_parser import (
    ExtractionMetadata,
    ExtractionResult,
    PageText,
    error_result,
)
from src.utils.imaging import pdf_to_images
from src.utils.logger import get_logger

from ..ocr import get_ocr_engine
from ..ocr.postprocess import postprocess
from ..preprocessing import preprocess

logger = get_logger(__name__)


def _similar(a: str, b: str, threshold: float = 0.85) -> bool:
    if a == b:
        return True
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def _score_line(line: str) -> int:
    score = len(line)
    cyrillic = sum(1 for c in line if 'а' <= c.lower() <= 'я')
    score += cyrillic * 2
    trash = sum(1 for c in line if c in "|_~`")
    score -= trash * 5
    return score


def _merge_texts_with_dedup(texts: list[str], threshold: float = 0.85) -> str:
    kept: list[tuple[str, int]] = []

    for text in texts:
        for line in text.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            score = _score_line(line_stripped)

            match_idx = None
            for i, (existing, _) in enumerate(kept):
                if _similar(line_stripped, existing, threshold):
                    match_idx = i
                    break

            if match_idx is None:
                kept.append((line_stripped, score))
            else:
                existing, existing_score = kept[match_idx]
                if score > existing_score:
                    kept[match_idx] = (line_stripped, score)

    return "\n".join(line for line, _ in kept)


def _extract_text_multi_pass(image, engine) -> tuple[str, float, list[str], dict]:
    methods = pdf_settings.multi_pass_methods
    texts: list[str] = []
    confidences: list[float] = []
    all_steps: list[str] = []

    timings = {
        "preprocess": 0.0,
        "ocr": 0.0,
        "per_method": {},
    }

    for method in methods:
        method_timing = {"preprocess": 0.0, "ocr": 0.0}

        try:
            t0 = time.perf_counter()
            processed, steps = preprocess(image, binarization_method=method)
            t1 = time.perf_counter()
            method_timing["preprocess"] = t1 - t0
            timings["preprocess"] += t1 - t0

            t2 = time.perf_counter()
            text, conf = engine.recognize(processed)
            t3 = time.perf_counter()
            method_timing["ocr"] = t3 - t2
            timings["ocr"] += t3 - t2

            if text:
                texts.append(text)
            if conf > 0:
                confidences.append(conf)

            for step in steps:
                if step not in all_steps:
                    all_steps.append(step)

            timings["per_method"][method] = method_timing

            logger.debug(
                "  Проход {}: preprocess {:.2f}s, OCR {:.2f}s",
                method, method_timing["preprocess"], method_timing["ocr"],
            )

        except Exception as e:
            logger.warning("Мульти-проход {} упал: {}", method, e)

    t0 = time.perf_counter()
    merged = _merge_texts_with_dedup(texts)
    if pdf_settings.enable_postprocess:
        merged = postprocess(merged, dedup=pdf_settings.enable_dedup)
    timings["merge"] = time.perf_counter() - t0

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return merged, avg_conf, all_steps, timings


def extract_text_from_scan_pdf(pdf_path: str | Path) -> ExtractionResult:
    pdf_path = Path(pdf_path)
    errors: list[str] = []
    text_by_page: list[PageText] = []
    all_confidences: list[float] = []
    preprocessing_steps: list[str] = []
    pages_count = 0
    engine_name = "unknown"

    total_t0 = time.perf_counter()
    timings_total = {
        "pdf_to_images": 0.0,
        "ocr_init": 0.0,
        "pages": [],          
        "total": 0.0,
    }

    logger.info("Конвертация PDF → изображения (dpi={})...", pdf_settings.ocr_dpi)
    t0 = time.perf_counter()
    try:
        images = pdf_to_images(pdf_path, dpi=pdf_settings.ocr_dpi)
        pages_count = len(images)
        timings_total["pdf_to_images"] = time.perf_counter() - t0
        logger.info(
            "  Конвертация: {:.2f}s, страниц: {}",
            timings_total["pdf_to_images"], pages_count,
        )
    except Exception as e:
        logger.error("Ошибка конвертации PDF → images {}: {}", pdf_path.name, e)
        return error_result(
            pdf_path,
            f"pdf_to_images_failed: {e}",
            extractor="easyocr",
            ocr_used=True,
            dpi=pdf_settings.ocr_dpi,
        )

    if not images:
        return error_result(
            pdf_path,
            "no_pages",
            extractor="easyocr",
            ocr_used=True,
            dpi=pdf_settings.ocr_dpi,
        )

    logger.info("Инициализация OCR...")
    t0 = time.perf_counter()
    try:
        engine = get_ocr_engine()
        engine_name = engine.name
        timings_total["ocr_init"] = time.perf_counter() - t0
        logger.info(
            "  Инициализация {}: {:.2f}s",
            engine_name, timings_total["ocr_init"],
        )
    except Exception as e:
        logger.error("Ошибка инициализации OCR: {}", e)
        return error_result(
            pdf_path,
            f"ocr_init_failed: {e}",
            extractor="easyocr",
            ocr_used=True,
            dpi=pdf_settings.ocr_dpi,
        )

    logger.info("OCR {} страниц...", pages_count)
    for i, img in enumerate(images, start=1):
        page_timing = {"page": i, "total": 0.0}
        page_t0 = time.perf_counter()

        try:
            if pdf_settings.enable_multi_pass:
                text, conf, steps, timings = _extract_text_multi_pass(img, engine)
                page_timing.update(timings)
            else:
                t0 = time.perf_counter()
                processed, steps = preprocess(img)
                t1 = time.perf_counter()
                text, conf = engine.recognize(processed)
                t2 = time.perf_counter()

                if pdf_settings.enable_postprocess:
                    text = postprocess(text, dedup=pdf_settings.enable_dedup) 

                page_timing["preprocess"] = t1 - t0
                page_timing["ocr"] = t2 - t1

            text_by_page.append(PageText(page=i, text=text))
            if conf > 0:
                all_confidences.append(conf)
            if not preprocessing_steps:
                preprocessing_steps = steps

            page_timing["total"] = time.perf_counter() - page_t0
            timings_total["pages"].append(page_timing)

            logger.info(
                "  Страница {}/{}: {:.2f}s (preprocess {:.2f}s, OCR {:.2f}s)",
                i, pages_count,
                page_timing["total"],
                page_timing.get("preprocess", 0),
                page_timing.get("ocr", 0),
            )

        except Exception as e:
            logger.warning("Ошибка OCR страницы {} в {}: {}", i, pdf_path.name, e)
            text_by_page.append(PageText(page=i, text=""))
            errors.append(f"page_{i}_ocr_failed: {e}")
            page_timing["total"] = time.perf_counter() - page_t0
            page_timing["error"] = str(e)
            timings_total["pages"].append(page_timing)

    timings_total["total"] = time.perf_counter() - total_t0

    logger.info("=" * 60)
    logger.info("ТАЙМИНГИ для {}", pdf_path.name)
    logger.info("=" * 60)
    logger.info("  PDF → images:   {:.2f}s", timings_total["pdf_to_images"])
    logger.info("  OCR init:       {:.2f}s", timings_total["ocr_init"])
    logger.info("  Страниц:        {}", pages_count)
    logger.info("  --- По страницам ---")
    for pt in timings_total["pages"]:
        line = f"  Стр. {pt['page']}: total {pt['total']:.2f}s"
        if "preprocess" in pt:
            line += f", preprocess {pt['preprocess']:.2f}s"
        if "ocr" in pt:
            line += f", OCR {pt['ocr']:.2f}s"
        if "pre_method" in pt:
            for method, t in pt["per_method"].items():
                line += f", [{method}: prep {t['preprocess']:.2f}s, ocr {t['ocr']:.2f}s]"
        if "error" in pt:
            line += f", ERROR: {pt['error']}"
        logger.info(line)
    logger.info("  --- Итого ---")
    logger.info("  ВСЕГО:          {:.2f}s", timings_total["total"])
    if pages_count > 0:
        logger.info("  На страницу:    {:.2f}s", timings_total["total"] / pages_count)
    logger.info("=" * 60)

    full_text = "\n\n".join(p.text for p in text_by_page)
    avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else None

    return ExtractionResult(
        file=str(pdf_path),
        has_text_layer=False,
        pages_count=pages_count,
        text=full_text,
        text_by_page=text_by_page,
        tables=[],
        metadata=ExtractionMetadata(
            extractor=engine_name,
            ocr_used=True,
            ocr_confidence=avg_conf,
            dpi=pdf_settings.ocr_dpi,
            preprocessing=preprocessing_steps,
        ),
        errors=errors,
    )