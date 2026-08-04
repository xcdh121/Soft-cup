"""Billing state machine, entitlements and quota accounting."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_hex
from typing import Any
from uuid import uuid4

from edu_db.models import (
    AdminAuditLog,
    BillingPlan,
    PaymentEvent,
    PaymentOrder,
    QuotaBucket,
    QuotaLedger,
    User,
    UserEntitlement,
)
from edu_db.session import get_session_factory
from sqlalchemy.orm import Session

ORDER_TRANSITIONS = {
    "created": {"pending_payment", "closed"},
    "pending_payment": {"paid", "closed"},
    "paid": {"refunding"},
    "refunding": {"refunded", "refund_failed"},
    "refund_failed": {"refunding"},
    "closed": set(),
    "refunded": set(),
}

DEFAULT_PLANS = (
    {
        "code": "trial",
        "name": "体验版",
        "description": "注册后 7 天内体验核心学习能力",
        "price_cents": 0,
        "duration_days": 7,
        "sort_order": 0,
        "quotas": {
            "chat_message": 30,
            "document_upload": 3,
            "quiz_generation": 3,
            "flashcard_generation": 3,
            "mindmap_generation": 1,
            "agent_run": 2,
            "resource_package": 1,
            "active_project": 1,
            "storage_mb": 200,
        },
        "features": {"priority": "normal", "advanced_diagnosis": "trial"},
    },
    {
        "code": "basic_2990",
        "name": "基础版",
        "description": "适合轻量、稳定的日常学习",
        "price_cents": 2990,
        "duration_days": 30,
        "sort_order": 10,
        "quotas": {
            "chat_message": 300,
            "document_upload": 20,
            "quiz_generation": 20,
            "flashcard_generation": 20,
            "mindmap_generation": 10,
            "agent_run": 15,
            "resource_package": 5,
            "active_project": 3,
            "storage_mb": 1024,
        },
        "features": {"priority": "normal", "advanced_diagnosis": True},
    },
    {
        "code": "advanced_5990",
        "name": "进阶版",
        "description": "高频学习与多智能体协作的推荐选择",
        "price_cents": 5990,
        "duration_days": 30,
        "sort_order": 20,
        "quotas": {
            "chat_message": 800,
            "document_upload": 60,
            "quiz_generation": 60,
            "flashcard_generation": 60,
            "mindmap_generation": 30,
            "agent_run": 50,
            "resource_package": 20,
            "active_project": 10,
            "storage_mb": 3072,
        },
        "features": {"priority": "high", "advanced_diagnosis": True},
    },
    {
        "code": "pro_7990",
        "name": "专业版",
        "description": "面向重度使用者的完整专业能力",
        "price_cents": 7990,
        "duration_days": 30,
        "sort_order": 30,
        "quotas": {
            "chat_message": 1500,
            "document_upload": 120,
            "quiz_generation": 120,
            "flashcard_generation": 120,
            "mindmap_generation": 60,
            "agent_run": 100,
            "resource_package": 40,
            "active_project": 30,
            "storage_mb": 5120,
        },
        "features": {"priority": "highest", "advanced_diagnosis": True},
    },
)


class BillingError(ValueError):
    """A safe business error suitable for an API response."""


class BillingService:
    def __init__(self, *, order_expiry_minutes: int = 30) -> None:
        self.order_expiry_minutes = order_expiry_minutes

    def ensure_default_plans(self) -> None:
        with self._session() as db:
            if db.query(BillingPlan.id).first():
                return
            for data in DEFAULT_PLANS:
                db.add(BillingPlan(id=str(uuid4()), is_active=True, **data))
            db.commit()

    def list_plans(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        self.ensure_default_plans()
        with self._session() as db:
            query = db.query(BillingPlan)
            if not include_inactive:
                query = query.filter(BillingPlan.is_active.is_(True))
            return [self._plan_dict(plan) for plan in query.order_by(BillingPlan.sort_order).all()]

    def create_order(self, *, user_id: str, plan_code: str, provider: str) -> dict[str, Any]:
        if provider not in {"manual", "manual_wechat", "manual_qq", "wechat_pay", "alipay"}:
            raise BillingError("不支持的支付渠道")
        self.ensure_default_plans()
        with self._session() as db:
            plan = db.query(BillingPlan).filter(BillingPlan.code == plan_code, BillingPlan.is_active.is_(True)).first()
            if not plan or plan.price_cents <= 0:
                raise BillingError("该套餐不可购买")
            now = self._now()
            order = PaymentOrder(
                id=str(uuid4()),
                order_no=self._order_no(now),
                user_id=user_id,
                plan_id=plan.id,
                plan_snapshot=self._plan_snapshot(plan),
                amount_cents=plan.price_cents,
                currency=plan.currency,
                provider=provider,
                status="pending_payment",
                expires_at=now + timedelta(minutes=self.order_expiry_minutes),
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            return self._order_dict(order)

    def ensure_trial_entitlement(self, *, user_id: str) -> None:
        """Grant the one-time registration trial without creating a zero-value order."""
        self.ensure_default_plans()
        with self._session() as db:
            plan = db.query(BillingPlan).filter(BillingPlan.code == "trial").first()
            if not plan:
                return
            existing = db.query(UserEntitlement.id).filter(
                UserEntitlement.user_id == user_id,
                UserEntitlement.plan_id == plan.id,
            ).first()
            if existing:
                return
            now = self._now()
            entitlement = UserEntitlement(
                id=str(uuid4()), user_id=user_id, plan_id=plan.id,
                plan_snapshot=self._plan_snapshot(plan), status="active",
                starts_at=now, ends_at=now + timedelta(days=plan.duration_days),
                grant_reason="注册体验权益",
            )
            db.add(entitlement)
            db.flush()
            self._create_buckets(db, entitlement, plan.quotas, operator_id=None, reason="注册体验权益")
            db.commit()

    def list_orders(self, *, user_id: str) -> list[dict[str, Any]]:
        with self._session() as db:
            rows = db.query(PaymentOrder).filter(PaymentOrder.user_id == user_id).order_by(PaymentOrder.created_at.desc()).all()
            return [self._order_dict(row) for row in rows]

    def get_order(self, *, user_id: str, order_no: str) -> dict[str, Any]:
        with self._session() as db:
            row = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no, PaymentOrder.user_id == user_id).first()
            if not row:
                raise BillingError("订单不存在")
            return self._order_dict(row)

    def close_order(self, *, user_id: str, order_no: str) -> dict[str, Any]:
        with self._session() as db:
            row = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no, PaymentOrder.user_id == user_id).with_for_update().first()
            if not row:
                raise BillingError("订单不存在")
            self._transition(row, "closed")
            db.commit()
            db.refresh(row)
            return self._order_dict(row)

    def submit_payment_claim(
        self,
        *,
        user_id: str,
        order_no: str,
        payment_claim_note: str,
        payment_reference: str | None = None,
    ) -> dict[str, Any]:
        """Record an unverified user claim without granting any entitlement."""
        note = payment_claim_note.strip()
        reference = payment_reference.strip() if payment_reference else None
        if not note:
            raise BillingError("请填写付款账号昵称或其他核对信息")
        with self._session() as db:
            order = (
                db.query(PaymentOrder)
                .filter(PaymentOrder.order_no == order_no, PaymentOrder.user_id == user_id)
                .with_for_update()
                .first()
            )
            if not order:
                raise BillingError("订单不存在")
            if order.provider not in {"manual", "manual_wechat", "manual_qq"}:
                raise BillingError("该订单不支持人工付款申报")
            if order.status != "pending_payment":
                raise BillingError("只有待支付订单可以申报付款")
            now = self._now()
            expires_at = order.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= now:
                self._transition(order, "closed")
                db.commit()
                raise BillingError("订单已超时关闭。请重新下单")

            order.payment_claim_note = note
            order.payment_reference = reference
            if order.payment_claimed_at is None:
                order.payment_claimed_at = now
                digest_payload = json.dumps(
                    {"note": note, "reference": reference},
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode()
                db.add(
                    PaymentEvent(
                        id=str(uuid4()),
                        order_id=order.id,
                        provider_event_id=f"manual-claim:{order.id}",
                        event_type="payment_claimed",
                        payload_digest=self.payload_digest(digest_payload),
                        verified=False,
                        processed_at=now,
                    )
                )
            db.commit()
            db.refresh(order)
            return self._order_dict(order)

    def process_payment(
        self,
        *,
        order_no: str,
        provider: str,
        provider_event_id: str,
        provider_transaction_id: str,
        amount_cents: int,
        currency: str,
        payload_digest: str,
        verified: bool,
        admin_user_id: str | None = None,
        reason: str = "支付成功到账",
    ) -> dict[str, Any]:
        if not verified:
            raise BillingError("支付通知验签失败")
        with self._session() as db:
            duplicate = db.query(PaymentEvent).filter(PaymentEvent.provider_event_id == provider_event_id).first()
            if duplicate:
                order = db.query(PaymentOrder).filter(PaymentOrder.id == duplicate.order_id).first()
                return self._order_dict(order)
            order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).with_for_update().first()
            if not order:
                raise BillingError("订单不存在")
            if order.provider != provider or order.amount_cents != amount_cents or order.currency != currency:
                raise BillingError("支付通知与订单信息不一致")
            event = PaymentEvent(
                id=str(uuid4()), order_id=order.id, provider_event_id=provider_event_id,
                event_type="payment_succeeded", payload_digest=payload_digest,
                verified=True, processed_at=self._now(),
            )
            db.add(event)
            if order.status == "paid":
                db.commit()
                return self._order_dict(order)
            if order.status == "closed":
                order.exception_note = "已关闭订单收到延迟支付成功通知。等待人工核对"
                db.commit()
                return self._order_dict(order)
            self._transition(order, "paid")
            order.provider_transaction_id = provider_transaction_id
            order.paid_at = self._now()
            self._grant_for_order(db, order, admin_user_id=admin_user_id, reason=reason)
            if admin_user_id:
                self._audit(db, admin_user_id, "order.confirm_payment", "payment_order", order.id, {}, self._order_dict(order), reason)
            db.commit()
            db.refresh(order)
            return self._order_dict(order)

    def grant_entitlement(self, *, user_id: str, plan_id: str, admin_user_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise BillingError("必须填写发放原因")
        with self._session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            plan = db.query(BillingPlan).filter(BillingPlan.id == plan_id, BillingPlan.is_active.is_(True)).first()
            if not user or not plan:
                raise BillingError("用户或套餐不存在")
            now = self._now()
            entitlement = UserEntitlement(
                id=str(uuid4()), user_id=user_id, plan_id=plan.id,
                plan_snapshot=self._plan_snapshot(plan), status="active",
                starts_at=now, ends_at=now + timedelta(days=plan.duration_days),
                granted_by_admin_id=admin_user_id, grant_reason=reason,
            )
            db.add(entitlement)
            db.flush()
            self._create_buckets(db, entitlement, plan.quotas, operator_id=admin_user_id, reason=reason)
            self._audit(db, admin_user_id, "entitlement.grant", "user", user_id, {}, {"plan_id": plan.id, "entitlement_id": entitlement.id}, reason)
            db.commit()
            return self._entitlement_dict(entitlement)

    def adjust_quota(self, *, user_id: str, resource_type: str, quantity: int, admin_user_id: str, reason: str) -> dict[str, Any]:
        if quantity == 0 or not reason.strip():
            raise BillingError("调整数量不能为 0。必须填写原因")
        with self._session() as db:
            now = self._now()
            bucket = (
                db.query(QuotaBucket)
                .filter(QuotaBucket.user_id == user_id, QuotaBucket.resource_type == resource_type, QuotaBucket.expires_at > now)
                .order_by(QuotaBucket.expires_at.asc()).with_for_update().first()
            )
            if not bucket:
                raise BillingError("没有可调整的有效额度桶。请先发放套餐")
            if bucket.granted + quantity < bucket.used + bucket.reserved:
                raise BillingError("扣回后额度不能小于已使用及预占数量")
            before = self._bucket_dict(bucket)
            bucket.granted += quantity
            db.add(QuotaLedger(
                id=str(uuid4()), user_id=user_id, bucket_id=bucket.id,
                resource_type=resource_type, operation="adjust", quantity=quantity,
                business_type="admin_adjustment", business_id=bucket.id,
                idempotency_key=f"admin-adjust:{uuid4()}", operator_id=admin_user_id, reason=reason,
            ))
            self._audit(db, admin_user_id, "quota.adjust", "quota_bucket", bucket.id, before, self._bucket_dict(bucket), reason)
            db.commit()
            return self._bucket_dict(bucket)

    def refund_order(self, *, order_no: str, admin_user_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise BillingError("必须填写退款原因")
        with self._session() as db:
            order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).with_for_update().first()
            if not order:
                raise BillingError("订单不存在")
            before = self._order_dict(order)
            self._transition(order, "refunding")
            entitlement = db.query(UserEntitlement).filter(UserEntitlement.order_id == order.id).first()
            if entitlement:
                entitlement.status = "refunded"
                for bucket in db.query(QuotaBucket).filter(QuotaBucket.entitlement_id == entitlement.id).with_for_update().all():
                    revoked = bucket.granted - bucket.used
                    bucket.reserved = 0
                    bucket.granted = bucket.used
                    db.add(QuotaLedger(
                        id=str(uuid4()), user_id=order.user_id, bucket_id=bucket.id,
                        resource_type=bucket.resource_type, operation="refund", quantity=-revoked,
                        business_type="payment_order", business_id=order.id,
                        idempotency_key=f"refund:{order.id}:{bucket.resource_type}",
                        operator_id=admin_user_id, reason=reason,
                    ))
            self._transition(order, "refunded")
            order.refunded_at = self._now()
            order.refunded_amount_cents = order.amount_cents
            order.refund_reason = reason
            self._audit(db, admin_user_id, "order.refund", "payment_order", order.id, before, self._order_dict(order), reason)
            db.commit()
            db.refresh(order)
            return self._order_dict(order)

    def billing_summary(self, *, user_id: str) -> dict[str, Any]:
        with self._session() as db:
            now = self._now()
            entitlements = db.query(UserEntitlement).filter(
                UserEntitlement.user_id == user_id,
                UserEntitlement.status == "active",
                UserEntitlement.ends_at > now,
            ).order_by(UserEntitlement.ends_at.asc()).all()
            buckets = db.query(QuotaBucket).filter(QuotaBucket.user_id == user_id, QuotaBucket.expires_at > now).all()
            totals: dict[str, dict[str, int]] = {}
            for bucket in buckets:
                item = totals.setdefault(bucket.resource_type, {"granted": 0, "used": 0, "reserved": 0, "remaining": 0})
                item["granted"] += bucket.granted
                item["used"] += bucket.used
                item["reserved"] += bucket.reserved
                item["remaining"] += bucket.granted - bucket.used - bucket.reserved
            active = [self._entitlement_dict(item) for item in entitlements]
            return {"entitlements": active, "current_plan": active[-1]["plan_snapshot"] if active else None, "expires_at": max((item.ends_at for item in entitlements), default=None), "quotas": totals}

    def update_plan(self, *, plan_id: str | None, values: dict[str, Any], admin_user_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise BillingError("必须填写变更原因")
        with self._session() as db:
            if plan_id:
                plan = db.query(BillingPlan).filter(BillingPlan.id == plan_id).first()
                if not plan:
                    raise BillingError("套餐不存在")
                before = self._plan_dict(plan)
                for key in ("name", "description", "price_cents", "duration_days", "quotas", "features", "is_active", "sort_order"):
                    if key in values:
                        setattr(plan, key, values[key])
                action = "billing_plan.update"
            else:
                required = {"code", "name", "price_cents", "duration_days"}
                if not required.issubset(values):
                    raise BillingError("缺少套餐必填字段")
                plan = BillingPlan(id=str(uuid4()), currency="CNY", quotas={}, features={}, **values)
                db.add(plan)
                before = {}
                action = "billing_plan.create"
            db.flush()
            after = self._plan_dict(plan)
            self._audit(db, admin_user_id, action, "billing_plan", plan.id, before, after, reason)
            db.commit()
            return after

    @staticmethod
    def payload_digest(payload: bytes) -> str:
        return sha256(payload).hexdigest()

    def _grant_for_order(self, db: Session, order: PaymentOrder, *, admin_user_id: str | None, reason: str) -> None:
        if db.query(UserEntitlement.id).filter(UserEntitlement.order_id == order.id).first():
            return
        now = self._now()
        snapshot = order.plan_snapshot
        entitlement = UserEntitlement(
            id=str(uuid4()), user_id=order.user_id, order_id=order.id, plan_id=order.plan_id,
            plan_snapshot=snapshot, status="active", starts_at=now,
            ends_at=now + timedelta(days=int(snapshot["duration_days"])),
            granted_by_admin_id=admin_user_id, grant_reason=reason,
        )
        db.add(entitlement)
        db.flush()
        self._create_buckets(db, entitlement, snapshot.get("quotas", {}), operator_id=admin_user_id, reason=reason)

    def _create_buckets(self, db: Session, entitlement: UserEntitlement, quotas: dict[str, Any], *, operator_id: str | None, reason: str) -> None:
        for resource_type, granted in quotas.items():
            if not isinstance(granted, int) or granted < 0:
                continue
            bucket = QuotaBucket(
                id=str(uuid4()), user_id=entitlement.user_id, entitlement_id=entitlement.id,
                resource_type=resource_type, granted=granted, used=0, reserved=0,
                starts_at=entitlement.starts_at, expires_at=entitlement.ends_at,
            )
            db.add(bucket)
            db.flush()
            db.add(QuotaLedger(
                id=str(uuid4()), user_id=entitlement.user_id, bucket_id=bucket.id,
                resource_type=resource_type, operation="grant", quantity=granted,
                business_type="entitlement", business_id=entitlement.id,
                idempotency_key=f"grant:{entitlement.id}:{resource_type}", operator_id=operator_id, reason=reason,
            ))

    def _transition(self, order: PaymentOrder, target: str) -> None:
        if target not in ORDER_TRANSITIONS.get(order.status, set()):
            raise BillingError(f"订单不能从 {order.status} 变更为 {target}")
        order.status = target

    def _audit(self, db: Session, admin_id: str, action: str, target_type: str, target_id: str, before: dict, after: dict, reason: str) -> None:
        db.add(AdminAuditLog(
            id=str(uuid4()), admin_user_id=admin_id, action=action,
            target_type=target_type, target_id=target_id,
            before_snapshot=before, after_snapshot=after, reason=reason,
        ))

    @staticmethod
    def _plan_snapshot(plan: BillingPlan) -> dict[str, Any]:
        return {"id": plan.id, "code": plan.code, "name": plan.name, "price_cents": plan.price_cents, "currency": plan.currency, "duration_days": plan.duration_days, "quotas": plan.quotas or {}, "features": plan.features or {}}

    @classmethod
    def _plan_dict(cls, plan: BillingPlan) -> dict[str, Any]:
        return {**cls._plan_snapshot(plan), "description": plan.description, "is_active": plan.is_active, "sort_order": plan.sort_order, "created_at": plan.created_at, "updated_at": plan.updated_at}

    @staticmethod
    def _order_dict(order: PaymentOrder) -> dict[str, Any]:
        return {"id": order.id, "order_no": order.order_no, "user_id": order.user_id, "plan_id": order.plan_id, "plan_snapshot": order.plan_snapshot, "amount_cents": order.amount_cents, "currency": order.currency, "provider": order.provider, "provider_transaction_id": order.provider_transaction_id, "payment_claimed_at": order.payment_claimed_at, "payment_claim_note": order.payment_claim_note, "payment_reference": order.payment_reference, "status": order.status, "expires_at": order.expires_at, "paid_at": order.paid_at, "refunded_at": order.refunded_at, "refunded_amount_cents": order.refunded_amount_cents, "refund_reason": order.refund_reason, "exception_note": order.exception_note, "created_at": order.created_at, "updated_at": order.updated_at}

    @staticmethod
    def _entitlement_dict(item: UserEntitlement) -> dict[str, Any]:
        return {"id": item.id, "user_id": item.user_id, "order_id": item.order_id, "plan_id": item.plan_id, "plan_snapshot": item.plan_snapshot, "status": item.status, "starts_at": item.starts_at, "ends_at": item.ends_at, "grant_reason": item.grant_reason}

    @staticmethod
    def _bucket_dict(bucket: QuotaBucket) -> dict[str, Any]:
        return {"id": bucket.id, "resource_type": bucket.resource_type, "granted": bucket.granted, "used": bucket.used, "reserved": bucket.reserved, "remaining": bucket.granted - bucket.used - bucket.reserved, "expires_at": bucket.expires_at}

    @staticmethod
    def _order_no(now: datetime) -> str:
        return f"E{now.strftime('%Y%m%d%H%M%S')}{token_hex(4).upper()}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

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
