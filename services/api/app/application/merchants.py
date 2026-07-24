import uuid

from payment_db_models.models import Merchant
from sqlalchemy.exc import IntegrityError

from app.domain.errors import DuplicateMerchant, MerchantNotFound
from app.infrastructure.metrics import track_usecase
from app.infrastructure.unit_of_work import UnitOfWork


class MerchantService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def create(self, *, name: str, document_number: str, email: str) -> Merchant:
        with track_usecase("create_merchant"):
            merchant = Merchant(name=name, document_number=document_number, email=email)
            self.uow.merchants.add(merchant)
            try:
                self.uow.commit()
            except IntegrityError as exc:
                self.uow.rollback()
                raise DuplicateMerchant("A merchant with this document already exists") from exc
            return merchant

    def get(self, merchant_id: uuid.UUID) -> Merchant:
        merchant = self.uow.merchants.get(merchant_id)
        if merchant is None:
            raise MerchantNotFound("Merchant not found")
        return merchant

    def summary(self, merchant_id: uuid.UUID) -> dict[str, object]:
        self.get(merchant_id)
        return {"merchant_id": merchant_id, **self.uow.payments.summary(merchant_id)}
