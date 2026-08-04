import unittest
from unittest.mock import patch

from edu_core.services.billing import BillingError, BillingService
from edu_core.services.quota import QuotaService
from edu_db.base import Base
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class BillingServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                BillingPlan.__table__,
                PaymentOrder.__table__,
                PaymentEvent.__table__,
                UserEntitlement.__table__,
                QuotaBucket.__table__,
                QuotaLedger.__table__,
                AdminAuditLog.__table__,
            ],
        )
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            db.add(User(id="user-1", username="learner", name="Learner", is_active=True, is_admin=False))
            db.add(
                BillingPlan(
                    id="plan-1", code="test_plan", name="Test", price_cents=2990,
                    duration_days=30, currency="CNY", quotas={"agent_run": 3},
                    features={}, is_active=True, sort_order=1,
                )
            )
            db.commit()
        self.factory_patch = patch("edu_core.services.billing.get_session_factory", return_value=self.sessions)
        self.factory_patch.start()
        self.quota_factory_patch = patch("edu_core.services.quota.get_session_factory", return_value=self.sessions)
        self.quota_factory_patch.start()
        self.service = BillingService()

    def tearDown(self):
        self.factory_patch.stop()
        self.quota_factory_patch.stop()
        self.engine.dispose()

    def test_duplicate_payment_event_grants_entitlement_once(self):
        order = self.service.create_order(user_id="user-1", plan_code="test_plan", provider="manual")
        arguments = {
            "order_no": order["order_no"], "provider": "manual",
            "provider_event_id": "manual:event-1", "provider_transaction_id": "manual:tx-1",
            "amount_cents": 2990, "currency": "CNY", "payload_digest": "digest",
            "verified": True,
        }
        first = self.service.process_payment(**arguments)
        second = self.service.process_payment(**arguments)

        self.assertEqual(first["status"], "paid")
        self.assertEqual(second["status"], "paid")
        with self.sessions() as db:
            self.assertEqual(db.query(PaymentEvent).count(), 1)
            self.assertEqual(db.query(UserEntitlement).count(), 1)
            self.assertEqual(db.query(QuotaBucket).count(), 1)
            self.assertEqual(db.query(QuotaLedger).count(), 1)

    def test_paid_order_cannot_be_closed(self):
        order = self.service.create_order(user_id="user-1", plan_code="test_plan", provider="manual")
        self.service.process_payment(
            order_no=order["order_no"], provider="manual", provider_event_id="manual:event-2",
            provider_transaction_id="manual:tx-2", amount_cents=2990, currency="CNY",
            payload_digest="digest", verified=True,
        )
        with self.assertRaises(BillingError):
            self.service.close_order(user_id="user-1", order_no=order["order_no"])

    def test_payment_claim_does_not_grant_entitlement(self):
        order = self.service.create_order(
            user_id="user-1", plan_code="test_plan", provider="manual_wechat"
        )

        claimed = self.service.submit_payment_claim(
            user_id="user-1",
            order_no=order["order_no"],
            payment_claim_note="微信昵称 learner",
            payment_reference="123456",
        )

        self.assertEqual(claimed["status"], "pending_payment")
        self.assertEqual(claimed["payment_claim_note"], "微信昵称 learner")
        self.assertEqual(claimed["payment_reference"], "123456")
        self.assertIsNotNone(claimed["payment_claimed_at"])
        with self.sessions() as db:
            self.assertEqual(db.query(PaymentEvent).count(), 1)
            self.assertFalse(db.query(PaymentEvent).one().verified)
            self.assertEqual(db.query(UserEntitlement).count(), 0)

    def test_payment_claim_is_idempotent(self):
        order = self.service.create_order(
            user_id="user-1", plan_code="test_plan", provider="manual_qq"
        )
        arguments = {
            "user_id": "user-1",
            "order_no": order["order_no"],
            "payment_claim_note": "QQ 昵称 learner",
            "payment_reference": "654321",
        }

        self.service.submit_payment_claim(**arguments)
        self.service.submit_payment_claim(**arguments)

        with self.sessions() as db:
            self.assertEqual(db.query(PaymentEvent).count(), 1)
            self.assertEqual(db.query(UserEntitlement).count(), 0)

    def test_unverified_payment_is_rejected(self):
        with self.assertRaises(BillingError):
            self.service.process_payment(
                order_no="missing", provider="manual", provider_event_id="event",
                provider_transaction_id="tx", amount_cents=1, currency="CNY",
                payload_digest="digest", verified=False,
            )

    def test_quota_consume_is_idempotent(self):
        order = self.service.create_order(user_id="user-1", plan_code="test_plan", provider="manual")
        self.service.process_payment(
            order_no=order["order_no"], provider="manual", provider_event_id="manual:event-3",
            provider_transaction_id="manual:tx-3", amount_cents=2990, currency="CNY",
            payload_digest="digest", verified=True,
        )
        quota = QuotaService()
        arguments = {
            "user_id": "user-1", "resource_type": "agent_run",
            "idempotency_key": "agent:test-operation", "business_type": "test",
            "business_id": "operation-1",
        }
        first = quota.consume(**arguments)
        second = quota.consume(**arguments)

        self.assertEqual(first["used"], 1)
        self.assertEqual(second["used"], 1)
        with self.sessions() as db:
            bucket = db.query(QuotaBucket).one()
            self.assertEqual(bucket.used, 1)
            self.assertEqual(bucket.reserved, 0)


if __name__ == "__main__":
    unittest.main()
