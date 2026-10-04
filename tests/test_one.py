import argparse
import json
import sys
from pathlib import Path

from src.pdf_extractor import extract_all


def print_header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Извлечь данные из одного PDF и показать результат",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python scripts/test_one.py data/input/ocr/test.pdf
  python scripts/test_one.py data/input/ocr/test.pdf --full
  python scripts/test_one.py data/input/ocr/test.pdf --text-only
  python scripts/test_one.py data/input/ocr/test.pdf --json output.json
  python scripts/test_one.py data/input/ocr/test.pdf --pages 1,2
        """,
    )
    parser.add_argument("pdf", type=Path, help="Путь к PDF")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Показать весь текст (по умолчанию первые 2000 символов)",
    )
    parser.add_argument(
        "--text-only", "-t",
        action="store_true",
        help="Только текст, без метаданных",
    )
    parser.add_argument(
        "--json", "-j",
        type=Path,
        default=None,
        help="Сохранить полный результат в JSON",
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Показать конкретные страницы (например: 1,3,5)",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"❌ Файл не найден: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    print(f"📄 Файл: {args.pdf}")
    print(f"📦 Размер: {args.pdf.stat().st_size / 1024:.1f} KB")

    print()
    print("⏳ Извлечение...")
    result = extract_all(args.pdf)
    print("✅ Готово")

    if args.text_only:
        print()
        print(result.text)
        return

    print_header("МЕТАДАННЫЕ")
    print(f"Файл:              {result.file}")
    print(f"Формат:            {result.source_format}")
    print(f"Текстовый слой:    {'✅ да' if result.has_text_layer else '❌ нет (OCR)'}")
    print(f"Страниц:           {result.pages_count}")
    print(f"Извлекатель:       {result.metadata.extractor}")
    print(f"OCR использован:   {'✅ да' if result.metadata.ocr_used else '❌ нет'}")
    if result.metadata.ocr_confidence is not None:
        print(f"Уверенность OCR:   {result.metadata.ocr_confidence:.2%}")
    if result.metadata.dpi:
        print(f"DPI:               {result.metadata.dpi}")
    if result.metadata.preprocessing:
        print(f"Предобработка:     {', '.join(result.metadata.preprocessing)}")

    if result.errors:
        print_header(f"⚠️  ОШИБКИ ({len(result.errors)})")
        for err in result.errors:
            print(f"  • {err}")

    print_header("СТАТИСТИКА ТЕКСТА")
    print(f"Всего символов:    {len(result.text)}")
    print(f"Всего строк:       {len(result.text.splitlines())}")
    print(f"Страниц с текстом: {sum(1 for p in result.text_by_page if p.text.strip())}")

    print_header("ТЕКСТ")

    if args.pages:
        page_nums = {int(x.strip()) for x in args.pages.split(",")}
        pages_to_show = [p for p in result.text_by_page if p.page in page_nums]
    else:
        pages_to_show = result.text_by_page

    max_chars = None if args.full else 3000
    total_shown = 0

    for page in pages_to_show:
        print(f"\n--- Страница {page.page} ({len(page.text)} символов) ---")
        text = page.text
        if max_chars is not None:
            remaining = max_chars - total_shown
            if remaining <= 0:
                print("  [... остальное скрыто, используйте --full]")
                break
            if len(text) > remaining:
                text = text[:remaining]
                print(text)
                print(f"  [... обрезано, показано {remaining} символов]")
                total_shown += remaining
                break
        print(text)
        total_shown += len(text)

    if result.tables:
        print_header(f"ТАБЛИЦЫ ({len(result.tables)})")
        for i, table in enumerate(result.tables, start=1):
            print(f"\n--- Таблица {i} (стр. {table.page}, {table.extractor}) ---")
            for row in table.data[:10]:
                print("  | " + " | ".join(str(c) for c in row))
            if len(table.data) > 10:
                print(f"  ... ещё {len(table.data) - 10} строк")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print()
        print(f"💾 JSON сохранён: {args.json}")


if __name__ == "__main__":
    main()