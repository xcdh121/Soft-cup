"""Transactional quota reservation, commit and release operations."""

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from edu_db.models import QuotaBucket, QuotaLedger, UserEntitlement
from edu_db.session import get_session_factory
from sqlalchemy import func

from edu_core.exceptions import UsageLimitExceededError


class QuotaService:
    def has_active_entitlement(self, user_id: str) -> bool:
        with self._session() as db:
            now = datetime.now(UTC)
            return (
                db.query(UserEntitlement.id)
                .filter(
                    UserEntitlement.user_id == user_id,
                    UserEntitlement.status == "active",
                    UserEntitlement.ends_at > now,
                )
                .first()
                is not None
            )

    def reserve(
        self,
        *,
        user_id: str,
        resource_type: str,
        quantity: int,
        idempotency_key: str,
        business_type: str,
        business_id: str,
    ) -> dict:
        if quantity <= 0:
            raise ValueError("Reservation quantity must be positive")
        with self._session() as db:
            duplicate = (
                db.query(QuotaLedger)
                .filter(QuotaLedger.idempotency_key == idempotency_key)
                .first()
            )
            if duplicate:
                bucket = (
                    db.query(QuotaBucket)
                    .filter(QuotaBucket.id == duplicate.bucket_id)
                    .first()
                )
                return self._bucket_dict(bucket)
            now = datetime.now(UTC)
            buckets = (
                db.query(QuotaBucket)
                .filter(
                    QuotaBucket.user_id == user_id,
                    QuotaBucket.resource_type == resource_type,
                    QuotaBucket.starts_at <= now,
                    QuotaBucket.expires_at > now,
                )
                .order_by(QuotaBucket.expires_at.asc())
                .with_for_update()
                .all()
            )
            available = sum(
                bucket.granted - bucket.used - bucket.reserved for bucket in buckets
            )
            if available < quantity:
                used, granted = (
                    db.query(
                        func.coalesce(func.sum(QuotaBucket.used), 0),
                        func.coalesce(func.sum(QuotaBucket.granted), 0),
                    )
                    .filter(
                        QuotaBucket.user_id == user_id,
                        QuotaBucket.resource_type == resource_type,
                        QuotaBucket.expires_at > now,
                    )
                    .one()
                )
                raise UsageLimitExceededError(
                    usage_type=resource_type,
                    current_count=int(used),
                    limit=int(granted),
                )
            bucket = next(
                item
                for item in buckets
                if item.granted - item.used - item.reserved >= quantity
            )
            bucket.reserved += quantity
            db.add(
                QuotaLedger(
                    id=str(uuid4()),
                    user_id=user_id,
                    bucket_id=bucket.id,
                    resource_type=resource_type,
                    operation="reserve",
                    quantity=quantity,
                    business_type=business_type,
                    business_id=business_id,
                    idempotency_key=idempotency_key,
                )
            )
            db.commit()
            return self._bucket_dict(bucket)

    def commit(self, *, idempotency_key: str) -> dict:
        return self._finish(idempotency_key=idempotency_key, operation="commit")

    def release(self, *, idempotency_key: str) -> dict:
        return self._finish(idempotency_key=idempotency_key, operation="release")

    def consume(
        self,
        *,
        user_id: str,
        resource_type: str,
        idempotency_key: str,
        business_type: str,
        business_id: str,
    ) -> dict:
        self.reserve(
            user_id=user_id,
            resource_type=resource_type,
            quantity=1,
            idempotency_key=idempotency_key,
            business_type=business_type,
            business_id=business_id,
        )
        return self.commit(idempotency_key=idempotency_key)

    def _finish(self, *, idempotency_key: str, operation: str) -> dict:
        finish_key = f"{idempotency_key}:{operation}"
        with self._session() as db:
            duplicate = (
                db.query(QuotaLedger)
                .filter(QuotaLedger.idempotency_key == finish_key)
                .first()
            )
            if duplicate:
                bucket = (
                    db.query(QuotaBucket)
                    .filter(QuotaBucket.id == duplicate.bucket_id)
                    .first()
                )
                return self._bucket_dict(bucket)
            reservation = (
                db.query(QuotaLedger)
                .filter(
                    QuotaLedger.idempotency_key == idempotency_key,
                    QuotaLedger.operation == "reserve",
                )
                .first()
            )
            if not reservation:
                raise ValueError("Quota reservation not found")
            bucket = (
                db.query(QuotaBucket)
                .filter(QuotaBucket.id == reservation.bucket_id)
                .with_for_update()
                .first()
            )
            if not bucket or bucket.reserved < reservation.quantity:
                raise ValueError("Quota reservation is no longer available")
            bucket.reserved -= reservation.quantity
            if operation == "commit":
                bucket.used += reservation.quantity
            db.add(
                QuotaLedger(
                    id=str(uuid4()),
                    user_id=reservation.user_id,
                    bucket_id=reservation.bucket_id,
                    resource_type=reservation.resource_type,
                    operation=operation,
                    quantity=reservation.quantity,
                    business_type=reservation.business_type,
                    business_id=reservation.business_id,
                    idempotency_key=finish_key,
                )
            )
            db.commit()
            return self._bucket_dict(bucket)

    @staticmethod
    def _bucket_dict(bucket: QuotaBucket) -> dict:
        return {
            "id": bucket.id,
            "resource_type": bucket.resource_type,
            "granted": bucket.granted,
            "used": bucket.used,
            "reserved": bucket.reserved,
            "remaining": bucket.granted - bucket.used - bucket.reserved,
            "expires_at": bucket.expires_at,
        }

    @contextmanager
    def _session(self):
        db = get_session_factory()()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
