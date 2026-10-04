from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    COURT_ORDER = "Судебный приказ"
    WRIT_OF_EXECUTION = "Исполнительный лист"
    FSSP_DECISION = "Постановление ФССП"
    UNKNOWN = "Не определён"
    UNSUPPORTED = "Не поддерживается"


class DocumentInfo(BaseModel):
    file_name: str
    document_type: DocumentType
    document_type_2: Optional[str] = None
    document_date: Optional[date] = None
    debtor_type: Optional[str] = None


class DebtorInfo(BaseModel):
    full_name: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    birth_date: Optional[date] = None
    passport: Optional[str] = None
    snils: Optional[str] = None
    inn: Optional[str] = None


class AddressInfo(BaseModel):
    full_address: Optional[str] = None
    street: Optional[str] = None
    dom: Optional[str] = None
    kv: Optional[str] = None


class CaseInfo(BaseModel):
    number: Optional[str] = None
    case_date: Optional[date] = None


class DebtInfo(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    principal: Optional[Decimal] = None
    penalty: Optional[Decimal] = None
    state_duty: Optional[Decimal] = None
    postal_expenses: Optional[Decimal] = None


class EnforcementInfo(BaseModel):
    proceedings_number: Optional[str] = None
    debt_text: Optional[str] = None
    document_number: Optional[str] = None
    document_date: Optional[date] = None
    debt_sum: Optional[Decimal] = None
    id_type: Optional[str] = None
    enforcement_fee: Optional[Decimal] = None


class CoDefendantsInfo(BaseModel):
    count: Optional[int] = None
    names: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    requires_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1
    )


class DocumentResult(BaseModel):
    document: DocumentInfo
    debtor: Optional[DebtorInfo] = None
    address: Optional[AddressInfo] = None
    case: Optional[CaseInfo] = None
    debt: Optional[DebtInfo] = None
    enforcement: Optional[EnforcementInfo] = None
    co_defendants: Optional[CoDefendantsInfo] = None
    analysis: AnalysisResult
