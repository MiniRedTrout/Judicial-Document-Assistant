import os
import re
import glob
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import get_logger

logger = get_logger(__name__)


DOCTYPE2_MAP = {
    'Постановление об окончании исполнительного производства': 'Постановление об окончании ИП',
    'Постановление о прекращении исполнительного производства': 'Постановление о прекращении ИП',
    'Постановление об отказе в возбуждении исполнительного производства': 'Постановление об отказе в возбуждении ИП',
    'Постановление об окончании и возвращении ИД взыскателю': 'Постановление об окончании и возвращении ИД',
    'Постановление о возбуждении исполнительного производства': 'Постановление о возбуждении',
}

RUB = r'(?:руб\.?|рублей)'
DATE_OPT = r'(\d{2}\.\d{2}\.\d{4})(?!\d)(?:\s*г\.?)?'
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
    try:
        return float(s.replace('\xa0', '').replace(' ', '').replace(',', '.'))
    except (ValueError, AttributeError) as e:
        logger.warning("Не удалось преобразовать в float: {!r} ({})", s, e)
        return None


def parse_debt_text(text):
    res = {
        'date_start': None, 'date_end': None,
        'rub_deb': None, 'rub_peni': None,
        'rub_poshlina': None, 'rub_post': None,
    }
    if not text:
        return res

    t = re.sub(r'\s+', ' ', text.replace('\xa0', ' '))

    m = re.search(r'за период\s+с\s+(\d{2}\.\d{2}\.\d+)\s*(?:г\.?)?\s+по\s+(\d{2}\.\d{2}\.\d+)', t, re.I)
    if m:
        for key, value in zip(('date_start', 'date_end'), m.groups()):
            try:
                if not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', value):
                    raise ValueError('Год должен содержать четыре цифры')
                res[key] = pd.to_datetime(value, format='%d.%m.%Y')
            except ValueError:
                logger.warning("Некорректная дата периода {}: {}", key, value)

    m = (
        re.search(rf'задолженност[ьи].{{0,300}}?в размере\s*([\d\s]+[,.]\d{{2}})\s*{RUB}', t)
        or re.search(rf'задолженность.{{0,300}}?в размере\s*([\d\s]+)\s*{RUB}', t)
    )
    if m:
        res['rub_deb'] = _to_float(m.group(1))

    m = re.search(
        rf'пени\s+за период\s+с\s+{DATE_OPT}\s+по\s+{DATE_OPT}\s+в размере\s*([\d\s]+[,.]\d{{2}})\s*{RUB}',
        t,
    )
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


def parse_xml(path: str, *, include_details=False) -> dict | None:
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error("Ошибка парсинга XML {}: {}", path, e)
        return None
    except Exception as e:
        logger.error("Ошибка открытия XML {}: {}", path, e)
        return None

    try:
        from scripts.xml_address import parse_address
        dbtr_adr = get_text(root, 'DbtrAdr')
        id_debt_text = get_text(root, 'IdDebtText')
        street, dom, kv = parse_address(dbtr_adr, id_debt_text)
        debt_info = parse_debt_text(id_debt_text)
        
        # Сумма исполнительного документа; остаток ИП — отдельная величина.
        id_debt_sum = get_text(root, 'IdDebtSum')

        # fallback: если rub_deb пуст и в тексте нет слова "задолженност"
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
                except (TypeError, ValueError) as e:
                    logger.warning("Ошибка fallback для {}: {}", path, e)

        doc_name = get_text(root, 'DocName')

        result = {
            'FileName': os.path.relpath(path, start=os.path.dirname(BASE_DIR)).replace('\\', '/'),
            'DocType': get_text(root, 'DocType'),
            'DocType2': DOCTYPE2_MAP.get(doc_name, doc_name),
            'DebtorType': get_text(root, 'DebtorType'),
            'DocDate': get_text(root, 'DocDate'),
            'IdDebtText': id_debt_text,
            'IdDocNo': get_text(root, 'IdDocNo'),
            'IdDocDate': get_text(root, 'IdDocDate'),
            'IdDeloNo': get_text(root, 'IdDeloNo'),
            'IdDeloDate': get_text(root, 'IdDeloDate'),
            'IdDebtSum': id_debt_sum,
            'IpNo': get_text(root, 'IpNo'),
            'IdType': get_text(root, 'IdType'),
            'DbtrAdr': dbtr_adr,
            'street': street,
            'dom': dom,
            'kv': kv,
            'DbtrName': get_text(root, 'DbtrName'),
            **debt_info,
        }
        if include_details:
            result['_debtor'] = {
                'birth_date': get_text(root, 'idDbtrBorn'),
                'inn': get_text(root, 'DbtrInn'),
                'snils': get_text(root, 'IdDbtrSNILS'),
            }
            result['_warnings'] = []
            if re.search(r'за период\s+с', id_debt_text or '', re.I) and (not debt_info['date_start'] or not debt_info['date_end']):
                result['_warnings'].append('Период задолженности в IdDebtText содержит нераспознанную дату; требуется сверка с документом')
        return result


    except Exception as e:
        logger.error("Ошибка обработки {}: {}", path, e)
        logger.debug("Traceback: {}", traceback.format_exc())
        return None


def build_table(xml_paths: list[str], out_file: str = 'result.xlsx') -> pd.DataFrame:
    rows = []
    errors = []

    logger.info("Начинаю обработку {} файлов", len(xml_paths))

    for i, path in enumerate(xml_paths, start=1):
        logger.info("[{}/{}] {}", i, len(xml_paths), path)
        try:
            row = parse_xml(path)
            if row is not None:
                rows.append(row)
            else:
                errors.append(path)
        except Exception as e:
            logger.error("Критическая ошибка на {}: {}", path, e)
            errors.append(path)

    logger.info(
        "Готово: успешно {} из {}, ошибок {}",
        len(rows), len(xml_paths), len(errors),
    )

    cols = [
        'FileName', 'DocType', 'DocType2', 'DebtorType', 'DocDate', 'IdDebtText',
        'IdDocNo', 'IdDocDate', 'IdDeloNo', 'IdDeloDate', 'IdDebtSum', 'IpNo',
        'IdType', 'DbtrAdr', 'street', 'dom', 'kv', 'DbtrName',
        'date_start', 'date_end', 'rub_deb', 'rub_peni', 'rub_poshlina', 'rub_post',
    ]

    df = pd.DataFrame(rows, columns=cols)

    for c in ['DocDate', 'IdDocDate', 'IdDeloDate', 'date_start', 'date_end']:
        df[c] = pd.to_datetime(df[c], errors='coerce')

    try:
        with pd.ExcelWriter(out_file, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as w:
            df.to_excel(w, index=False)
        logger.info("Таблица сохранена: {}", out_file)
    except Exception as e:
        logger.error("Ошибка сохранения в {}: {}", out_file, e)

    if errors:
        logger.warning("Не обработаны файлы ({}):", len(errors))
        for p in errors:
            logger.warning("  - {}", p)

    return df


if __name__ == '__main__':
    files = glob.glob('fssp/**/*.xml', recursive=True)

    if not files:
        logger.error("Не найдено XML в fssp/**/*.xml")
        sys.exit(1)

    logger.info("Найдено {} XML-файлов", len(files))
    df = build_table(files)
    print(f"\nВсего строк: {len(df)}")