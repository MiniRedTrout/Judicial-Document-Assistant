import re
from dataclasses import dataclass, field



#Все ключевые слова
MARKER_PHRASES = [
    "в удовлетворении остальной части…требований отказать",
    "заявление оставить без движения",
    "возвратить…из федерального бюджета…государственной пошлины",
    "заявление возвратить заявителю",
    "оставить… без рассмотрения",
    "в иске отказать",
    "решение…отменить",
    "направить на новое рассмотрение",
    "производство по делу прекратить",
    "утвердить мировое соглашение",
]


#Нормализация текста
def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("...", "…")
    text = text.replace(". . .", "…")
    text = re.sub(r"\s+", " ", text)
    text = text.lower()
    return text.strip()

#Работа с ключевыми словаи
def phrase_to_regex(phrase: str):
    phrase = phrase.replace("...", "…")
    phrase = phrase.lower()

    parts = phrase.split("…")

    regex_parts = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        words = part.split()
        escaped = []
        for word in words:
            escaped.append(re.escape(word))

        regex_parts.append(r"\s+".join(escaped))

    pattern = r".*?".join(regex_parts)
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


MARKER_REGEXES = []
for phrase in MARKER_PHRASES:
    MARKER_REGEXES.append((phrase, phrase_to_regex(phrase)))


@dataclass
class Match:
    phrase: str
    page: int | None
    snippet: str
    
@dataclass
class CheckResult:
    file: str
    doc_type: str = "Судебный акт"
    needs_lawyer: bool = False
    matches: list = field(default_factory=list)

    def summary(self) -> str:
        if not self.needs_lawyer:
            return self.file + ": юрист не нужен"
        phrases = []
        for m in self.matches:
            phrases.append(m.phrase)
        return self.file + ": ЮРИСТУ (" + "; ".join(phrases) + ")"


#Создание 'окна' Чтобы понимать контекст вместе с ключевыми словами
#(Можно удалить)
def make_snippet(text: str, start: int, end: int, window: int = 80) -> str:
    left = start - window
    if left < 0:
        left = 0
    right = end + window
    if right > len(text):
        right = len(text)
    return text[left:right].strip()

#Поиск ключевых слов в тексте
def find_markers(text: str, page: int | None = None) -> list:
    found = []
    if not text:
        return found

    for phrase, regex in MARKER_REGEXES:
        m = regex.search(text)
        if m:
            found.append(Match(
                phrase=phrase,
                page=page,
                snippet=make_snippet(text, m.start(), m.end()),
            ))
    return found


def check_document(result, doc_type: str = "Судебный акт") -> CheckResult:
    matches = []

    if getattr(result, "text_by_page", None):
        for page in result.text_by_page:
            page_text = normalize_text(page.text or "")
            page_matches = find_markers(page_text, page=page.page)
            matches.extend(page_matches)
    elif result.text:
        text = normalize_text(result.text)
        matches.extend(find_markers(text))

    # убираем дубли по фразе
    unique = []
    seen = set()
    for m in matches:
        if m.phrase in seen:
            continue
        seen.add(m.phrase)
        unique.append(m)

    return CheckResult(
        file=result.file,
        doc_type=doc_type,
        needs_lawyer=len(unique) > 0,
        matches=unique,
    )

# Главная функция которая принимает документы
def check_documents(results: list) -> list:
    to_send = []
    for result in results:
        doc_type = getattr(result, "doc_type", "Судебный акт")
        checked = check_document(result, doc_type=doc_type)
        if checked.needs_lawyer:
            to_send.append(checked)
    return to_send