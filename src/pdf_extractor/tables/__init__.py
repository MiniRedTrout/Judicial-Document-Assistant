from .camelot_extractor import extract_tables_camelot

__all__ = ["extract_tables_camelot"]


def extract_tables_pp_structure(pdf_path):
    from .pp_structure import extract_tables_pp_structure as _impl
    return _impl(pdf_path)