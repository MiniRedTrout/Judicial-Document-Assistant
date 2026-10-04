import os, re, glob
import pandas as pd
import xml.etree.ElementTree as ET

DOCTYPE2_MAP = {
    'Постановление об окончании исполнительного производства': 'Постановление об окончании ИП',
    'Постановление о прекращении исполнительного производства': 'Постановление о прекращении ИП',
    'Постановление об отказе в возбуждении исполнительного производства': 'Постановление об отказе в возбуждении ИП',
    'Постановление об окончании и возвращении ИД взыскателю': 'Постановление об окончании и возвращении ИД',
    'Постановление о возбуждении исполнительного производства': 'Постановление о возбуждении',
}

RUB = r'(?:руб\.?|рублей)'
DATE_OPT = r'(\d{2}\.\d{2}\.\d{4})(?:\s*г\.?)?'
BASE_DIR = 'fssp'

def local(tag):
    return tag.split('}')[-1]


def get_text(root, tag_name):
    for el in root:
        if local(el.tag) == tag_name:
            return el.text.strip() if el.text else None
    return None


def _to_float(s):
    if s is None:
        return None
    return float(s.replace('\xa0', '').replace(' ', '').replace(',', '.'))


def parse_debt_text(text):
    res = {'date_start': None, 'date_end': None,
           'rub_deb': None, 'rub_peni': None,
           'rub_poshlina': None, 'rub_post': None}
    if not text:
        return res
    t = re.sub(r'\s+', ' ', text.replace('\xa0', ' '))

    m = re.search(rf'за период\s+с\s+{DATE_OPT}\s+по\s+{DATE_OPT}', t)
    if m:
        res['date_start'] = pd.to_datetime(m.group(1), format='%d.%m.%Y')
        res['date_end']   = pd.to_datetime(m.group(2), format='%d.%m.%Y')

    # задолженность (с копейками и без)
    m = (re.search(rf'задолженност[ьи].{{0,300}}?в размере\s*([\d\s]+[,.]\d{{2}})\s*{RUB}', t)
        or re.search(rf'задолженность.{{0,300}}?в размере\s*([\d\s]+)\s*{RUB}', t))
    if m:
        res['rub_deb'] = _to_float(m.group(1))

    # пени — два порядка слов
    m = re.search(rf'пени\s+за период\s+с\s+{DATE_OPT}\s+по\s+{DATE_OPT}\s+в размере\s*([\d\s]+[,.]\d{{2}})\s*{RUB}', t)
    if not m:
        m = re.search(rf'пени в размере\s*([\d\s]+(?:[,.]\d{{2}})?)\s*{RUB}', t)
    if m:
        res['rub_peni'] = _to_float(m.group(m.lastindex))

    m = re.search(rf'государственной пошлины в размере\s*([\d\s]+(?:[,.]\d{{2}})?)\s*{RUB}', t)
    if m:
        res['rub_poshlina'] = _to_float(m.group(1))

    m = re.search(rf'почтовые расходы в размере\s*([\d\s]+(?:[,.]\d{{2}})?)\s*{RUB}', t)
    if m:
        res['rub_post'] = _to_float(m.group(1))

    return res


def is_kladr(adr):
    if not adr or ',,' not in adr:
        return False
    first = adr.split(',')[0].strip()
    return first.isdigit() and len(first) <= 3


def parse_kladr_address(adr):
    if not adr:
        return None, None, None
    parts = [p.strip() for p in adr.split(',')]
    street = parts[-3] if len(parts) >= 3 else None
    dom_raw = parts[-2] if len(parts) >= 2 else None
    kv = parts[-1] if len(parts) >= 1 else None
    dom = dom_raw
    if dom_raw:
        m = re.match(r'^(\d+[А-Яа-я]?)к(\d+)$', dom_raw)
        if m:
            dom = f'{m.group(1)} корп.{m.group(2)}'
    return street, dom, kv


def parse_human_address(adr):
    """'644027, Россия, , , г. Тест, , ул. Примерова, д. 235, корп. А, кв. 4'
       -> ('г Тест, ул. Примерова', '235/А', '4')"""
    if not adr:
        return None, None, None
    # вытаскиваем индекс/страну — убираем
    cleaned = re.sub(r'\b\d{6}\b', '', adr)
    cleaned = cleaned.replace('Россия', '')
    parts = [p.strip(' .,') for p in cleaned.split(',') if p.strip(' .,')]

    city = street = dom = korp = kv = None
    for p in parts:
        low = p.lower()
        if low.startswith('г ') or (len(p) < 20 and p[0].isupper() and not re.match(r'^\d', p) and city is None):
            city = p.replace('г.', '').strip()
        elif 'ул' in low:
            street = re.sub(r'^ул\.?\s*', '', p).strip()
        elif low.startswith('д') or re.match(r'^\d', p) and dom is None and kv is None:
            dom = re.sub(r'^д\.?\s*', '', p).strip()
        elif 'корп' in low:
            korp = re.sub(r'^корп\.?\s*', '', p).strip()
        elif low.startswith('кв') or 'квартира' in low:
            kv = re.sub(r'^кв\.?\s*', '', p).strip()

    dom_full = f'{dom}/{korp}' if dom and korp else dom
    street_full = f'г {city}, ул. {street}' if city and street else (street or city)
    return street_full, dom_full, kv


def normalize_street(s):
    if not s:
        return s
    m = re.match(r'^(\d+)-я\s+(.+)$', s)
    return f'{m.group(2)} {m.group(1)}-я' if m else s


def parse_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()

    dbtr_adr = get_text(root, 'DbtrAdr')
    if is_kladr(dbtr_adr):
        street, dom, kv = parse_kladr_address(dbtr_adr)
        street = normalize_street(street)
    else:
        street, dom, kv = parse_human_address(dbtr_adr)

    id_debt_text = get_text(root, 'IdDebtText')

    debt_info = parse_debt_text(id_debt_text)

    # тут поправить, при сравнении есть несовпадения
    id_debt_sum = (get_text(root, 'IpRestDebtsum')
                   or get_text(root, 'IpRestOthersum')
                   or get_text(root, 'IdDebtSum'))

    # fallback: если rub_deb пуст и в тексте вообще нет слова "задолженност"
    if debt_info['rub_deb'] is None:
        t_low = (id_debt_text or '').lower()
        has_debt_word = 'задолженност' in t_low
        if not has_debt_word and id_debt_sum is not None:
            try:
                total = _to_float(id_debt_sum)
                rest = sum(x or 0 for x in [
                    debt_info['rub_peni'],
                    debt_info['rub_poshlina'],
                    debt_info['rub_post'],
                ])
                debt_info['rub_deb'] = round(total - rest, 2) if rest else total
            except (TypeError, ValueError):
                pass

    doc_name = get_text(root, 'DocName')
    return {
        'FileName':   os.path.relpath(path, start=os.path.dirname(BASE_DIR)).replace('\\', '/'),
        'DocType':    get_text(root, 'DocType'),
        'DocType2':   DOCTYPE2_MAP.get(doc_name, doc_name),
        'DebtorType': get_text(root, 'DebtorType'),
        'DocDate':    get_text(root, 'DocDate'),
        'IdDebtText': id_debt_text,
        'IdDocNo':    get_text(root, 'IdDocNo'),
        'IdDocDate':  get_text(root, 'IdDocDate'),
        'IdDeloNo':   get_text(root, 'IdDeloNo'),
        'IdDeloDate': get_text(root, 'IdDeloDate'),
        'IdDebtSum':  id_debt_sum,
        'IpNo':       get_text(root, 'IpNo'),
        'IdType':     get_text(root, 'IdType'),
        'DbtrAdr':    dbtr_adr,
        'street':     street,
        'dom':        dom,
        'kv':         kv,
        'DbtrName':   get_text(root, 'DbtrName'),
        **debt_info,
    }


def build_table(xml_paths, out_file='result.xlsx'):
    rows = [parse_xml(p) for p in xml_paths]
    cols = ['FileName','DocType','DocType2','DebtorType','DocDate','IdDebtText',
            'IdDocNo','IdDocDate','IdDeloNo','IdDeloDate','IdDebtSum','IpNo',
            'IdType','DbtrAdr','street','dom','kv','DbtrName',
            'date_start','date_end','rub_deb','rub_peni','rub_poshlina','rub_post']
    df = pd.DataFrame(rows, columns=cols)
    for c in ['DocDate','IdDocDate','IdDeloDate','date_start','date_end']:
        df[c] = pd.to_datetime(df[c], errors='coerce')
    with pd.ExcelWriter(out_file, engine='xlsxwriter',
                        datetime_format='yyyy-mm-dd') as w:
        df.to_excel(w, index=False)
    return df


if __name__ == '__main__':
    files = glob.glob('fssp/**/*.xml', recursive=True)
    df = build_table(files)