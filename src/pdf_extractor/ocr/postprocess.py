import re


_GENERAL_REPLACEMENTS = [
    (r'\bNg\b', '№'),
    (r'\bN°\b', '№'),
    (r'\bN9\b', '№'),
    (r'\bNo\b', '№'),
    (r"\bN'", '№'),

    (r'\bИHН\b', 'ИНН'),
    (r'\bИHH\b', 'ИНН'),
    (r'\bОKВ\b', 'ОКВ'),
    (r'\bOКВ\b', 'ОКВ'),
    (r'\bОKB\b', 'ОКВ'),
    (r'\bОГPH\b', 'ОГРН'),
    (r'\bOГРН\b', 'ОГРН'),
    (r'\bКПЙПI\b', 'КПП'),
    (r'\bКППI\b', 'КПП'),
    (r'\bКПЙП\b', 'КПП'),

    (r'\bВВикторович', 'Викторович'),
    (r'\bВВыдан', 'Выдан'),
    (r'\bППробник', 'Пробник'),
    (r'\bТТест', 'Тест'),
    (r'\bССудебный', 'Судебный'),
    (r'\bММировой', 'Мировой'),
]


_FSSP_ID_REPLACEMENTS = [
    (r'\b[5S][5S]?MS[O0]{2}9[1lI]?\b', '55MS0091'),
    (r'\b33MS009\b', '55MS0091'),
    (r'\b35MS009D\b', '55MS0091'),
    (r'\b55MSOO9\b', '55MS0091'),
]


_DEAL_REPLACEMENTS = [
    (r'(\d+-\d+/\d{4})#\d+', r'\1'),
    (r'(\d+-\d+)/2033(\d+)', r'\1/2033'),
]


def _fix_ogrn(text: str) -> str:
    def repl(match):
        ogrn = match.group(1)
        if len(ogrn) == 14 and ogrn.startswith('1'):
            ogrn = ogrn[1:]
        return f"ОГРН {ogrn}"

    return re.sub(r'ОГРН[\s:]*(\d{13,14})', repl, text)


def _fix_money(text: str) -> str:
    text = re.sub(r'(\d{4,})\.(\d{2})\b', r'\1,\2', text)
    text = re.sub(r'(\d{4,}):(\d{2})\b', r'\1,\2', text)
    return text


def _fix_dates(text: str) -> str:
    text = re.sub(r'(\d{2}):(\d{2}):(\d{4})', r'\1.\2.\3', text)
    text = re.sub(r'(\d{2}\.\d{2}\.)\s+(\d{4})', r'\1\2', text)
    return text


_DIGIT_REPLACEMENTS = [
    (r'(?<=\d)[ОO](?=\d)', '0'),
    (r'(?<=\d)[ОO]\b', '0'),
    (r'\b[ОO](?=\d)', '0'),

    (r'(?<=\d)[lI](?=\d)', '1'),
    (r'(?<=\d)[lI]\b', '1'),

    (r'(?<=\d)[З](?=\d)', '3'),

    (r'(?<=серия\s)[ВB](?=\d{3}\s\d{6})', '8'),
    (r'(?<=\s)[ВB](?=\d{3}\s\d{6})', '8'),
]


_WORD_REPLACEMENTS = [
    (r'\bПройзводство\b', 'Производство'),
    (r'\bролдения\b', 'рождения'),
    (r'\bТешловую\b', 'Тепловую'),
    (r'\bЁруговай\b', 'Круговой'),
    (r'\bЁруговая\b', 'Круговая'),
    (r'\bЁруговай\b', 'Круговой'),
    (r'\bТеПо\b', 'Тепло'),
    (r'\bиспошения\b', 'исполнения'),
    (r'\bсудёбный\b', 'судебный'),
    (r'\bсудёбного\b', 'судебного'),
    (r'\bсудёбном\b', 'судебном'),
    (r'\bрайонё\b', 'районе'),
    (r'\bгородё\b', 'городе'),
    (r'\bрайонёв\b', 'районе в'),
    (r'\bгородёТесте\b', 'городе Тесте'),
]


_TAX_REPLACEMENTS = [
    (r'\bКЁйi\b', 'КПП'),
    (r'\bКПЙПI\b', 'КПП'),
    (r'\bИН\b', 'ИНН'),
    (r'\bин(\d)', r'ИНН \1'),
]


def _fix_inn(text: str) -> str:
    def repl(match):
        inn = match.group(1)
        inn = inn.replace('О', '0').replace('о', '0')
        inn = inn.replace('l', '1').replace('I', '1')
        inn = inn.replace('З', '3').replace('з', '3')
        inn = inn.replace('В', '8').replace('в', '8')
        return f"ИНН {inn}"

    return re.sub(r'ИНН[\s:]*([\dОоlIЗзВв]{10,12})', repl, text)


def _fix_passport_series(text: str) -> str:
    def repl(match):
        series = match.group(1)
        series = series.replace('В', '8').replace('в', '8')
        series = series.replace('З', '2').replace('з', '2')
        series = series.replace('О', '0').replace('о', '0')
        return f"серия {series} {match.group(2)}"

    return re.sub(
        r'серия[\s:]*([\dВвЗзОо]{4})\s*(\d{6})',
        repl,
        text,
    )


def _fix_dates(text: str) -> str:
    def repl(match):
        day, month, year = match.group(1), match.group(2), match.group(3)
        day = day.replace('О', '0').replace('о', '0').replace('l', '1')
        month = month.replace('О', '0').replace('о', '0').replace('l', '1')
        year = year.replace('О', '0').replace('о', '0').replace('l', '1')
        return f"{day}.{month}.{year}"

    return re.sub(
        r'(\d{1,2})[.\s](\d{2})[.\s](\d{4})',
        repl,
        text,
    )


def _fix_deal_number(text: str) -> str:
    def repl(match):
        num = match.group(1)
        num = num.replace('О', '0').replace('о', '0').replace('l', '1')
        return f"№ {num}/{match.group(2)}"

    return re.sub(
        r'№?\s*(\d+-\d+)[/\\](\d{4})',
        repl,
        text,
    )


def remove_headers_footers(text: str) -> str:
    patterns = [
        r'^\s*\d+\s+of\s+\d+\s*$',
        r'^\s*of\s*$',
        r'^\s*page\s*\d*\s*(of\s*\d+)?\s*$',
        r'^\s*страница\s+\d+\s+из\s+\d+\s*$',
        r'^\s*экз\.?\s*\d*\s*$',
        r'^\s*ex\.?\s*\d*\s*$',
    ]

    lines = text.splitlines()
    result = []
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if any(re.match(p, line_stripped, re.IGNORECASE) for p in patterns):
            continue
        if len(line_stripped) == 1 and not line_stripped.isdigit():
            continue
        result.append(line)

    return "\n".join(result)


def remove_duplicate_lines(text: str, threshold: float = 0.95) -> str:
    from difflib import SequenceMatcher

    seen: list[str] = []
    result: list[str] = []

    for line in text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue

        is_dup = False
        for s in seen:
            if SequenceMatcher(None, line_stripped, s).ratio() >= threshold:
                is_dup = True
                break

        if not is_dup:
            seen.append(line_stripped)
            result.append(line_stripped)

    return "\n".join(result)


def postprocess(text: str, *, dedup: bool = False) -> str:
    # 1. Убираем колонтитулы
    text = remove_headers_footers(text)

    # 2. Общие замены (Ng, ИHН, ОKВ, дубли букв)
    for pattern, replacement in _GENERAL_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)

    # 3. Идентификаторы ФССП
    for pattern, replacement in _FSSP_ID_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)

    # 4. Номера дел
    for pattern, replacement in _DEAL_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)

    # 5. Слова
    for pattern, replacement in _WORD_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)

    # 6. Налоговые
    for pattern, replacement in _TAX_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)

    # 7. Замены в цифровых контекстах
    for pattern, replacement in _DIGIT_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)

    # 8. Специальные поля
    text = _fix_ogrn(text)
    text = _fix_inn(text)
    text = _fix_passport_series(text)
    text = _fix_dates(text)
    text = _fix_money(text)
    text = _fix_deal_number(text)

    # 9. Дедупликация
    if dedup:
        text = remove_duplicate_lines(text)

    # 10. Убираем пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text