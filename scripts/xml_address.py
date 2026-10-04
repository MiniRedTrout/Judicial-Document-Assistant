"""Разбор адреса должника: DbtrAdr имеет приоритет над цитатами судебного акта."""
import re


def house_number(value, building=None):
    if not value:
        return None
    value = value.strip()
    match = re.fullmatch(r"(\d+[А-Яа-я]?)\s*к\s*(\d+)", value)
    if match:
        value = f"{match[1]} корп.{match[2]}"
    else:
        value = re.sub(r"^(\d+)\s*([А-Яа-я])$", r"\1/\2", value)
    if building:
        value += f" корп.{building}" if building.isdigit() else f"/{building}"
    return value


def street_parts(value):
    value = value.strip()
    types = [(r"ул\.?", "ул."), (r"пер\.?", "пер."),
             (r"пр-кт|проспект", "пр-кт"), (r"городок\.?", "городок.")]
    for pattern, kind in types:
        match = re.fullmatch(rf"(?:{pattern})\s+(.+)", value, re.I)
        if match:
            return match[1], kind
        match = re.fullmatch(rf"(.+?)\s+(?:{pattern})", value, re.I)
        if match:
            return match[1], kind
    return value, None


def parse_address(address, debt_text=""):
    if not address:
        return None, None, None
    parts = [x.strip() for x in address.split(",")]
    structured = parts[0].isdigit() and len(parts[0]) <= 3 and len(parts) >= 8
    kind = building = None
    if structured:
        street, house, flat = parts[-3:]
        # В формате КЛАДР город находится в позициях 4/5; район выше не является городом.
        city = parts[-4] or parts[-5]
        city = re.sub(r"^г(?:\.\s*|\s+)", "", city)
        street, kind = street_parts(street)
    else:
        city = street = house = flat = None
        for item in parts:
            match = re.fullmatch(r"г\.?\s+(.+)", item, re.I)
            if match:
                city = match[1]
                continue
            match = re.fullmatch(r"(д|корп|кв)\.?\s*(.+)", item, re.I)
            if match:
                label, value = match[1].lower(), match[2]
                if label == "д": house = value
                elif label == "корп": building = value
                else: flat = value
                continue
            name, road_type = street_parts(item)
            if road_type:
                street, kind = name, road_type
    if street:
        # Цитата может уточнить тип той же улицы, но не заменяет текущий дом/квартиру.
        quoted = re.sub(r"\s+", " ", debt_text or "")
        escaped = re.escape(street)
        for pattern, road_type in [(r"пер\.?", "пер."), (r"пр-кт|проспект", "пр-кт"),
                                   (r"городок\.?", "городок.")]:
            if re.search(rf"(?:{pattern})\s+{escaped}(?!\w)|(?<!\w){escaped}\s+(?:{pattern})(?!\w)", quoted, re.I):
                kind = road_type
                break
        # Переставляем порядковый номер только при явном суффиксе в источнике.
        numbered = re.fullmatch(r"(\d+)(-я)?\s+(.+)", street)
        if numbered:
            number, suffix, name = numbered.groups()
            if suffix or re.search(rf"(?<!\d){number}-я\s+{re.escape(name)}(?!\w)", quoted, re.I):
                street = f"{name} {number}-я"
        street = f"г {city}, {kind or 'ул.'} {street}" if city else f"{kind or 'ул.'} {street}"
    return street, house_number(house, building), flat or None
