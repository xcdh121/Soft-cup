import unittest
from unittest.mock import patch

from edu_core.exceptions import UsageLimitExceededError
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
            self.assertEqual(db.query(QuotaBucket).count(), 0)
            self.assertEqual(db.query(QuotaLedger).count(), 0)

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

    def test_agent_run_quota_is_unlimited(self):
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

        self.assertTrue(first["unlimited"])
        self.assertTrue(second["unlimited"])
        self.assertEqual(first["remaining"], -1)
        with self.sessions() as db:
            self.assertEqual(db.query(QuotaBucket).count(), 0)
            self.assertEqual(db.query(QuotaLedger).count(), 0)

        plan = self.service.list_plans()[0]
        summary = self.service.billing_summary(user_id="user-1")
        self.assertEqual(plan["quotas"]["agent_run"], -1)
        self.assertEqual(summary["quotas"]["agent_run"]["remaining"], -1)

    def test_quota_limit_reports_reserved_usage(self):
        order = self.service.create_order(
            user_id="user-1", plan_code="test_plan", provider="manual"
        )
        self.service.process_payment(
            order_no=order["order_no"],
            provider="manual",
            provider_event_id="manual:event-reserved",
            provider_transaction_id="manual:tx-reserved",
            amount_cents=2990,
            currency="CNY",
            payload_digest="digest",
            verified=True,
        )
        with self.sessions() as db:
            entitlement = db.query(UserEntitlement).one()
            db.add(
                QuotaBucket(
                    id="quiz-bucket",
                    user_id="user-1",
                    entitlement_id=entitlement.id,
                    resource_type="quiz_generation",
                    granted=3,
                    used=0,
                    reserved=0,
                    starts_at=entitlement.starts_at,
                    expires_at=entitlement.ends_at,
                )
            )
            db.commit()
        quota = QuotaService()
        for index in range(3):
            quota.reserve(
                user_id="user-1",
                resource_type="quiz_generation",
                quantity=1,
                idempotency_key=f"agent:reserved:{index}",
                business_type="test",
                business_id=f"operation-{index}",
            )

        with self.assertRaises(UsageLimitExceededError) as raised:
            quota.reserve(
                user_id="user-1",
                resource_type="quiz_generation",
                quantity=1,
                idempotency_key="agent:reserved:overflow",
                business_type="test",
                business_id="operation-overflow",
            )

        self.assertEqual(raised.exception.current_count, 3)
        self.assertEqual(raised.exception.limit, 3)


if __name__ == "__main__":
    unittest.main()
