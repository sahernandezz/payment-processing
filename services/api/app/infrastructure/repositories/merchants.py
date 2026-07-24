import uuid

from payment_db_models.models import Merchant
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class MerchantRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, merchant: Merchant) -> Merchant:
        self.session.add(merchant)
        return merchant

    def get(self, merchant_id: uuid.UUID) -> Merchant | None:
        return self.session.get(Merchant, merchant_id)

    def by_document(self, document_number: str) -> Merchant | None:
        stmt = select(Merchant).where(Merchant.document_number == document_number)
        return self.session.scalar(stmt)

    def random(self) -> Merchant | None:
        return self.session.scalar(select(Merchant).order_by(func.random()).limit(1))
