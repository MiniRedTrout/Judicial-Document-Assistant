from datetime import date
from decimal import Decimal

from app.schemas.document_result import (
    DocumentResult,
    DocumentInfo,
    DebtorInfo,
    AddressInfo,
    CaseInfo,
    DebtInfo,
    EnforcementInfo,
    CoDefendantsInfo,
    AnalysisResult,
    DocumentType,
)


def test_document_result():
    result = DocumentResult(
        document=DocumentInfo(
            file_name="example.pdf",
            document_type=DocumentType.COURT_ORDER,
            document_date=date(2026, 9, 1),
        ),

        debtor=DebtorInfo(
            full_name="Иванов Иван Иванович",
            last_name="Иванов",
            first_name="Иван",
            middle_name="Иванович",
            birth_date=date(1990, 5, 15),
            passport="4010 123456",
            snils="123-456-789 00",
            inn="781234567890",
        ),

        address=AddressInfo(
            full_address="г. Санкт-Петербург, ул. Ленина, д. 10, кв. 25",
            street="ул. Ленина",
            dom="10",
            kv="25",
        ),

        case=CaseInfo(
            number="2-1234/2026",
            case_date=date(2026, 8, 20),
        ),

        debt=DebtInfo(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            principal=Decimal("15000.50"),
            penalty=Decimal("1200.25"),
            state_duty=Decimal("500.00"),
        ),

        enforcement=EnforcementInfo(
            proceedings_number="12345/26/78001-ИП",
            debt_text="Задолженность по договору",
            document_number="123456",
            document_date=date(2026, 8, 25),
            debt_sum=Decimal("16700.75"),
            id_type="Судебный приказ",
            enforcement_fee=Decimal("1170.00"),
        ),

        co_defendants=CoDefendantsInfo(
            count=2,
            names=[
                "Петров Петр Петрович",
                "Сидоров Алексей Сергеевич",
            ],
        ),

        analysis=AnalysisResult(
            requires_review=False,
            review_reasons=[],
            missing_fields=[],
            confidence=0.95,
        ),
    )

    assert result.document.file_name == "example.pdf"
    assert result.document.document_type == DocumentType.COURT_ORDER

    assert result.debtor.full_name == "Иванов Иван Иванович"
    assert result.debtor.birth_date == date(1990, 5, 15)
    assert result.case.case_date == date(2026, 8, 20)

    assert result.debt.principal == Decimal("15000.50")
    assert result.debt.penalty == Decimal("1200.25")

    assert result.co_defendants.count == 2

    assert result.analysis.requires_review is False
    assert result.analysis.confidence == 0.95

    print(result.model_dump())