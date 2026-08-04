"""Read-optimized administrator operations with immutable audit records."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from math import ceil
from typing import Any
from uuid import UUID, uuid4

from edu_db.models import (
    AdminAuditLog,
    AgentArtifact,
    AgentEvent,
    AgentRun,
    AgentToolCall,
    Course,
    CourseChapter,
    Document,
    PaymentEvent,
    PaymentOrder,
    Project,
    QuotaBucket,
    SkillExecution,
    User,
    UserEntitlement,
)
from edu_db.session import get_session_factory
from sqlalchemy import case, func, or_

from edu_core.services.billing import BillingError


class AdminService:
    def overview(self) -> dict[str, Any]:
        with self._session() as db:
            now = self._now()
            today = datetime(now.year, now.month, now.day, tzinfo=UTC)
            trend_days = 14
            trend_start = today - timedelta(days=trend_days - 1)
            total_users = db.query(func.count(User.id)).scalar() or 0
            active_users = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
            paid_users = db.query(func.count(func.distinct(PaymentOrder.user_id))).filter(PaymentOrder.status.in_(("paid", "refunding", "refunded"))).scalar() or 0
            new_users_today = db.query(func.count(User.id)).filter(User.created_at >= today).scalar() or 0
            active_entitlements = db.query(func.count(UserEntitlement.id)).filter(
                UserEntitlement.status == "active", UserEntitlement.ends_at > now
            ).scalar() or 0
            today_orders = db.query(func.count(PaymentOrder.id)).filter(PaymentOrder.created_at >= today).scalar() or 0
            today_revenue = db.query(func.coalesce(func.sum(PaymentOrder.amount_cents), 0)).filter(
                PaymentOrder.paid_at >= today,
                PaymentOrder.status.in_(("paid", "refunding", "refunded")),
            ).scalar() or 0
            today_refunds = db.query(func.coalesce(func.sum(PaymentOrder.refunded_amount_cents), 0)).filter(
                PaymentOrder.refunded_at >= today
            ).scalar() or 0
            pending_payment = db.query(func.count(PaymentOrder.id)).filter(
                PaymentOrder.status.in_(("created", "pending_payment"))
            ).scalar() or 0
            run_metrics = db.query(
                func.count(AgentRun.id),
                func.coalesce(func.sum(case((AgentRun.status == "completed", 1), else_=0)), 0),
                func.coalesce(func.sum(case((AgentRun.status == "failed", 1), else_=0)), 0),
                func.coalesce(func.avg(AgentRun.duration_ms), 0),
                func.coalesce(func.sum(AgentRun.input_tokens), 0),
                func.coalesce(func.sum(AgentRun.output_tokens), 0),
                func.coalesce(func.sum(AgentRun.estimated_cost_micros), 0),
            ).filter(AgentRun.created_at >= today).one()
            stuck_before = now - timedelta(minutes=2)
            suspected_stuck = db.query(func.count(AgentRun.id)).filter(
                AgentRun.status == "running",
                or_(AgentRun.heartbeat_at.is_(None), AgentRun.heartbeat_at < stuck_before),
            ).scalar() or 0
            course_counts = dict(db.query(Course.publish_status, func.count(Course.id)).group_by(Course.publish_status).all())
            order_status_distribution = [
                {"status": status, "count": int(count)}
                for status, count in db.query(PaymentOrder.status, func.count(PaymentOrder.id)).group_by(PaymentOrder.status).all()
            ]
            plan_distribution = [
                {"plan": name or "未命名套餐", "count": int(count)}
                for name, count in db.query(
                    UserEntitlement.plan_snapshot["name"].as_string(), func.count(UserEntitlement.id)
                ).filter(
                    UserEntitlement.status == "active", UserEntitlement.ends_at > now
                ).group_by(UserEntitlement.plan_snapshot["name"].as_string()).all()
            ]
            run_count = int(run_metrics[0])
            completed_runs = int(run_metrics[1])
            failed_runs = int(run_metrics[2])
            terminal_runs = completed_runs + failed_runs

            daily = {
                (trend_start + timedelta(days=offset)).date().isoformat(): {
                    "date": (trend_start + timedelta(days=offset)).date().isoformat(),
                    "new_users": 0,
                    "orders": 0,
                    "revenue_cents": 0,
                    "refund_cents": 0,
                    "agent_runs": 0,
                    "agent_completed": 0,
                    "agent_failed": 0,
                    "tokens": 0,
                    "estimated_cost_micros": 0,
                }
                for offset in range(trend_days)
            }

            for (created_at,) in db.query(User.created_at).filter(User.created_at >= trend_start).all():
                key = created_at.date().isoformat()
                if key in daily:
                    daily[key]["new_users"] += 1
            for created_at, in db.query(PaymentOrder.created_at).filter(PaymentOrder.created_at >= trend_start).all():
                key = created_at.date().isoformat()
                if key in daily:
                    daily[key]["orders"] += 1
            for paid_at, amount_cents in db.query(PaymentOrder.paid_at, PaymentOrder.amount_cents).filter(
                PaymentOrder.paid_at >= trend_start,
                PaymentOrder.status.in_(("paid", "refunding", "refunded")),
            ).all():
                key = paid_at.date().isoformat()
                if key in daily:
                    daily[key]["revenue_cents"] += int(amount_cents or 0)
            for refunded_at, amount_cents in db.query(PaymentOrder.refunded_at, PaymentOrder.refunded_amount_cents).filter(
                PaymentOrder.refunded_at >= trend_start
            ).all():
                key = refunded_at.date().isoformat()
                if key in daily:
                    daily[key]["refund_cents"] += int(amount_cents or 0)
            run_status_distribution: dict[str, int] = {}
            for created_at, status, input_tokens, output_tokens, estimated_cost in db.query(
                AgentRun.created_at,
                AgentRun.status,
                AgentRun.input_tokens,
                AgentRun.output_tokens,
                AgentRun.estimated_cost_micros,
            ).filter(AgentRun.created_at >= trend_start).all():
                key = created_at.date().isoformat()
                if key not in daily:
                    continue
                daily[key]["agent_runs"] += 1
                daily[key]["agent_completed"] += int(status == "completed")
                daily[key]["agent_failed"] += int(status == "failed")
                daily[key]["tokens"] += int(input_tokens or 0) + int(output_tokens or 0)
                daily[key]["estimated_cost_micros"] += int(estimated_cost or 0)
                run_status_distribution[status] = run_status_distribution.get(status, 0) + 1

            project_count = db.query(func.count(Project.id)).scalar() or 0
            document_metrics = db.query(
                func.count(Document.id), func.coalesce(func.sum(Document.file_size), 0)
            ).one()
            return {
                "users": {
                    "registered": int(total_users), "active": int(active_users), "paid": int(paid_users),
                    "new_today": int(new_users_today), "active_entitlements": int(active_entitlements),
                    "paid_conversion_rate": round(int(paid_users) / int(total_users), 4) if total_users else 0,
                },
                "orders": {
                    "today": int(today_orders), "revenue_cents": int(today_revenue),
                    "refund_cents": int(today_refunds), "pending_payment": int(pending_payment),
                    "status_distribution": order_status_distribution,
                    "plan_distribution": plan_distribution,
                },
                "agent_runs": {
                    "today": run_count,
                    "completed": completed_runs, "failed": failed_runs,
                    "success_rate": round(completed_runs / terminal_runs, 4) if terminal_runs else 0,
                    "failure_rate": round(failed_runs / terminal_runs, 4) if terminal_runs else 0,
                    "average_duration_ms": int(run_metrics[3] or 0),
                    "input_tokens": int(run_metrics[4]), "output_tokens": int(run_metrics[5]),
                    "estimated_cost_micros": int(run_metrics[6]), "suspected_stuck": suspected_stuck,
                    "status_distribution": [
                        {"status": status, "count": count}
                        for status, count in sorted(run_status_distribution.items())
                    ],
                },
                "courses": {
                    "published": course_counts.get("published", 0), "draft": course_counts.get("draft", 0),
                    "unpublished": course_counts.get("unpublished", 0), "archived": course_counts.get("archived", 0),
                },
                "content": {
                    "projects": int(project_count), "documents": int(document_metrics[0]),
                    "storage_bytes": int(document_metrics[1] or 0),
                },
                "trends": {"period_days": trend_days, "daily": list(daily.values())},
                "generated_at": now,
            }

    def list_users(self, *, page: int, page_size: int, search: str | None, is_active: bool | None) -> dict[str, Any]:
        with self._session() as db:
            query = db.query(User)
            if search:
                needle = f"%{search.strip()}%"
                query = query.filter(or_(User.username.ilike(needle), User.name.ilike(needle), User.email.ilike(needle)))
            if is_active is not None:
                query = query.filter(User.is_active.is_(is_active))
            total = query.count()
            rows = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
            items = []
            now = self._now()
            for user in rows:
                entitlement = db.query(UserEntitlement).filter(UserEntitlement.user_id == user.id, UserEntitlement.status == "active", UserEntitlement.ends_at > now).order_by(UserEntitlement.ends_at.desc()).first()
                items.append({**self._user_dict(user), "current_plan": entitlement.plan_snapshot.get("name") if entitlement else None, "plan_expires_at": entitlement.ends_at if entitlement else None})
            return self._page(items, total, page, page_size)

    def user_detail(self, user_id: str) -> dict[str, Any]:
        with self._session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise BillingError("用户不存在")
            projects = db.query(func.count(Project.id)).filter(Project.owner_id == user_id).scalar() or 0
            storage = db.query(func.coalesce(func.sum(Document.file_size), 0)).filter(Document.owner_id == user_id).scalar() or 0
            entitlements = db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).order_by(UserEntitlement.created_at.desc()).all()
            quotas = db.query(QuotaBucket).filter(QuotaBucket.user_id == user_id, QuotaBucket.expires_at > self._now()).all()
            orders = db.query(PaymentOrder).filter(PaymentOrder.user_id == user_id).order_by(PaymentOrder.created_at.desc()).limit(10).all()
            runs = db.query(AgentRun).filter(AgentRun.user_id == user_id).order_by(AgentRun.created_at.desc()).limit(10).all()
            return {
                **self._user_dict(user), "project_count": projects, "storage_bytes": int(storage),
                "entitlements": [self._entitlement_dict(item) for item in entitlements],
                "quotas": [self._bucket_dict(item) for item in quotas],
                "orders": [self._order_dict(item) for item in orders],
                "recent_agent_runs": [self._run_dict(item, db=db) for item in runs],
            }

    def update_user(self, *, user_id: str, admin_id: str, values: dict[str, Any], reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise BillingError("必须填写变更原因")
        with self._session() as db:
            user = db.query(User).filter(User.id == user_id).with_for_update().first()
            if not user:
                raise BillingError("用户不存在")
            if user.id == admin_id and values.get("is_active") is False:
                raise BillingError("管理员不能停用自己")
            before = self._user_dict(user)
            for key in ("is_active", "is_admin"):
                if key in values:
                    setattr(user, key, values[key])
            if "password_hash" in values:
                user.password_hash = values["password_hash"]
            db.flush()
            after = self._user_dict(user)
            if "password_hash" in values:
                after["password_reset"] = True
            self._audit(db, admin_id, "user.update", "user", user.id, before, after, reason)
            db.commit()
            return after

    def list_orders(self, *, page: int, page_size: int, search: str | None, status: str | None, provider: str | None) -> dict[str, Any]:
        with self._session() as db:
            query = db.query(PaymentOrder, User.username).join(User, User.id == PaymentOrder.user_id)
            if search:
                needle = f"%{search.strip()}%"
                query = query.filter(or_(PaymentOrder.order_no.ilike(needle), PaymentOrder.provider_transaction_id.ilike(needle), PaymentOrder.payment_reference.ilike(needle), PaymentOrder.payment_claim_note.ilike(needle), User.username.ilike(needle)))
            if status:
                query = query.filter(PaymentOrder.status == status)
            if provider:
                query = query.filter(PaymentOrder.provider == provider)
            total = query.count()
            rows = query.order_by(PaymentOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
            return self._page([{**self._order_dict(order), "username": username} for order, username in rows], total, page, page_size)

    def order_detail(self, order_no: str) -> dict[str, Any]:
        with self._session() as db:
            order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
            if not order:
                raise BillingError("订单不存在")
            events = db.query(PaymentEvent).filter(PaymentEvent.order_id == order.id).order_by(PaymentEvent.created_at).all()
            return {**self._order_dict(order), "events": [{"id": event.id, "provider_event_id": event.provider_event_id, "event_type": event.event_type, "payload_digest": event.payload_digest, "verified": event.verified, "processed_at": event.processed_at, "created_at": event.created_at} for event in events]}

    def list_agent_runs(self, *, page: int, page_size: int, status: str | None, search: str | None, suspected_stuck: bool | None) -> dict[str, Any]:
        with self._session() as db:
            query = db.query(AgentRun)
            if status:
                query = query.filter(AgentRun.status == status)
            if search:
                needle = f"%{search.strip()}%"
                query = query.join(User, User.id == AgentRun.user_id).filter(or_(AgentRun.id.ilike(needle), AgentRun.goal.ilike(needle), AgentRun.trace_id.ilike(needle), User.username.ilike(needle)))
            if suspected_stuck is not None:
                stuck = or_(AgentRun.heartbeat_at.is_(None), AgentRun.heartbeat_at < self._now() - timedelta(minutes=2))
                query = query.filter(AgentRun.status == "running", stuck) if suspected_stuck else query.filter(~stuck)
            total = query.count()
            rows = query.order_by(AgentRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
            return self._page([self._run_dict(row, db=db) for row in rows], total, page, page_size)

    def agent_run_detail(self, run_id: str) -> dict[str, Any]:
        with self._session() as db:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if not run:
                raise BillingError("Agent 运行不存在")
            events = db.query(AgentEvent).filter(AgentEvent.run_id == run_id).order_by(AgentEvent.created_at).all()
            skills = db.query(SkillExecution).filter(SkillExecution.run_id == run_id).all()
            calls = db.query(AgentToolCall).filter(AgentToolCall.run_id == run_id).all()
            artifacts = db.query(AgentArtifact).filter(AgentArtifact.run_id == run_id).all()
            return {
                **self._run_dict(run, db=db),
                "context_summary": self._redact(run.context_snapshot),
                "events": [{"id": e.id, "event_type": e.event_type, "agent_name": e.agent_name, "status": e.status, "summary": self._safe_text(e.summary), "created_at": e.created_at} for e in events],
                "skill_executions": [{"id": s.id, "agent_name": s.agent_name, "skill_id": s.skill_id, "status": s.status, "duration_ms": s.duration_ms, "fallback_used": s.fallback_used, "error_code": s.error_code, "error_message": self._safe_text(s.error_message)} for s in skills],
                "tool_calls": [{"id": c.id, "agent_name": c.agent_name, "tool_name": c.tool_name, "status": c.status, "duration_ms": c.duration_ms, "result_summary": self._redact(c.result_summary), "error_code": c.error_code} for c in calls],
                "artifacts": [{"id": a.id, "agent_name": a.agent_name, "artifact_key": a.artifact_key, "summary": self._redact(a.artifact)} for a in artifacts],
            }

    def update_run(self, *, run_id: str, admin_id: str, action: str, reason: str, handled: bool | None = None) -> dict[str, Any]:
        if not reason.strip():
            raise BillingError("必须填写操作原因")
        with self._session() as db:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).with_for_update().first()
            if not run:
                raise BillingError("Agent 运行不存在")
            before = self._run_dict(run, db=db)
            if action == "handling":
                run.handled_at = self._now() if handled else None
                run.handled_by = admin_id if handled else None
            elif action == "cancel":
                if run.status not in {"queued", "running"}:
                    raise BillingError("仅排队中或运行中的任务可请求取消")
                run.cancellation_requested_at = self._now()
            elif action == "retry":
                if run.status != "failed":
                    raise BillingError("仅失败任务可重试")
                retry = AgentRun(
                    id=str(uuid4()), project_id=run.project_id, user_id=run.user_id,
                    goal=run.goal, status="queued", trigger={**(run.trigger or {}), "admin_retry": True},
                    context_snapshot=run.context_snapshot or {}, final_result={}, retry_of_run_id=run.id,
                    trace_id=str(uuid4()),
                )
                db.add(retry)
                db.flush()
                self._audit(db, admin_id, "agent_run.retry", "agent_run", run.id, before, {"retry_run_id": retry.id}, reason)
                db.commit()
                return self._run_dict(retry, db=db)
            else:
                raise BillingError("未知操作")
            db.flush()
            after = self._run_dict(run, db=db)
            self._audit(db, admin_id, f"agent_run.{action}", "agent_run", run.id, before, after, reason)
            db.commit()
            return after

    def list_courses(self, *, page: int, page_size: int, status: str | None, search: str | None) -> dict[str, Any]:
        with self._session() as db:
            query = db.query(Course)
            if status:
                query = query.filter(Course.publish_status == status)
            if search:
                query = query.filter(or_(Course.name.ilike(f"%{search}%"), Course.code.ilike(f"%{search}%")))
            total = query.count()
            rows = query.order_by(Course.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
            items = [{**self._course_dict(row), "chapter_count": db.query(func.count(CourseChapter.id)).filter(CourseChapter.course_id == row.id).scalar() or 0, "project_count": db.query(func.count(Project.id)).filter(Project.course_id == row.id).scalar() or 0} for row in rows]
            return self._page(items, total, page, page_size)

    def create_course(self, *, admin_id: str, name: str, code: str | None, description: str | None) -> dict[str, Any]:
        with self._session() as db:
            course = Course(id=str(uuid4()), owner_id=admin_id, name=name, code=code, description=description, status="active", visibility="platform", publish_status="draft", version=1)
            db.add(course)
            db.flush()
            after = self._course_dict(course)
            self._audit(db, admin_id, "course.create", "course", course.id, {}, after, "创建平台课程")
            db.commit()
            return after

    def update_course(
        self,
        *,
        course_id: str,
        admin_id: str,
        values: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise BillingError("必须填写变更原因")
        with self._session() as db:
            course = db.query(Course).filter(Course.id == course_id).with_for_update().first()
            if not course:
                raise BillingError("课程不存在")
            before = self._course_dict(course)
            for key in ("name", "code", "description", "cover_url"):
                if key in values:
                    setattr(course, key, values[key])
            course.version += 1
            db.flush()
            after = self._course_dict(course)
            self._audit(db, admin_id, "course.update", "course", course.id, before, after, reason)
            db.commit()
            return after

    def change_course_status(self, *, course_id: str, admin_id: str, target: str, reason: str) -> dict[str, Any]:
        if target not in {"published", "unpublished", "archived"} or not reason.strip():
            raise BillingError("课程状态或原因无效")
        with self._session() as db:
            course = db.query(Course).filter(Course.id == course_id).with_for_update().first()
            if not course:
                raise BillingError("课程不存在")
            if target == "published":
                chapter_count = db.query(func.count(CourseChapter.id)).filter(CourseChapter.course_id == course_id).scalar() or 0
                if chapter_count < 1:
                    raise BillingError("发布前至少需要一个章节")
            before = self._course_dict(course)
            course.visibility = "platform"
            course.publish_status = target
            course.published_at = self._now() if target == "published" else course.published_at
            course.published_by = admin_id if target == "published" else course.published_by
            course.version += 1
            db.flush()
            after = self._course_dict(course)
            self._audit(db, admin_id, f"course.{target}", "course", course.id, before, after, reason)
            db.commit()
            return after

    def audit_logs(self, *, page: int, page_size: int, action: str | None) -> dict[str, Any]:
        with self._session() as db:
            query = db.query(AdminAuditLog)
            if action:
                query = query.filter(AdminAuditLog.action == action)
            total = query.count()
            rows = query.order_by(AdminAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
            items = [{"id": row.id, "admin_user_id": row.admin_user_id, "action": row.action, "target_type": row.target_type, "target_id": row.target_id, "before_snapshot": row.before_snapshot, "after_snapshot": row.after_snapshot, "reason": row.reason, "request_id": row.request_id, "ip_address": row.ip_address, "created_at": row.created_at} for row in rows]
            return self._page(items, total, page, page_size)

    @staticmethod
    def _page(items: list[dict], total: int, page: int, page_size: int) -> dict[str, Any]:
        return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

    @staticmethod
    def _user_dict(user: User) -> dict[str, Any]:
        return {"id": user.id, "username": user.username, "name": user.name, "email": user.email, "is_active": user.is_active, "is_admin": user.is_admin, "created_at": user.created_at, "updated_at": user.updated_at}

    @staticmethod
    def _order_dict(order: PaymentOrder) -> dict[str, Any]:
        return {"id": order.id, "order_no": order.order_no, "user_id": order.user_id, "plan_id": order.plan_id, "plan_snapshot": order.plan_snapshot, "amount_cents": order.amount_cents, "currency": order.currency, "provider": order.provider, "provider_transaction_id": order.provider_transaction_id, "payment_claimed_at": order.payment_claimed_at, "payment_claim_note": order.payment_claim_note, "payment_reference": order.payment_reference, "status": order.status, "expires_at": order.expires_at, "paid_at": order.paid_at, "refunded_at": order.refunded_at, "refunded_amount_cents": order.refunded_amount_cents, "refund_reason": order.refund_reason, "exception_note": order.exception_note, "created_at": order.created_at, "updated_at": order.updated_at}

    @staticmethod
    def _entitlement_dict(item: UserEntitlement) -> dict[str, Any]:
        return {"id": item.id, "plan_snapshot": item.plan_snapshot, "status": item.status, "starts_at": item.starts_at, "ends_at": item.ends_at, "grant_reason": item.grant_reason}

    @staticmethod
    def _bucket_dict(item: QuotaBucket) -> dict[str, Any]:
        return {"id": item.id, "resource_type": item.resource_type, "granted": item.granted, "used": item.used, "reserved": item.reserved, "remaining": item.granted - item.used - item.reserved, "expires_at": item.expires_at}

    def _run_dict(self, run: AgentRun, *, db) -> dict[str, Any]:
        user = db.query(User.username).filter(User.id == run.user_id).scalar()
        now = self._now()
        heartbeat = run.heartbeat_at or run.started_at or run.created_at
        stuck = run.status == "running" and heartbeat and heartbeat < now - timedelta(minutes=2)
        duration = run.duration_ms
        if duration is None and run.started_at:
            duration = int(((run.completed_at or now) - run.started_at).total_seconds() * 1000)
        return {"id": run.id, "trace_id": run.trace_id, "user_id": run.user_id, "username": user, "project_id": run.project_id, "goal": run.goal, "current_agent_name": run.current_agent_name, "status": run.status, "started_at": run.started_at, "completed_at": run.completed_at, "created_at": run.created_at, "heartbeat_at": run.heartbeat_at, "duration_ms": duration, "input_tokens": run.input_tokens, "output_tokens": run.output_tokens, "estimated_cost_micros": run.estimated_cost_micros, "error_summary": self._safe_text(run.error_message), "suspected_stuck": bool(stuck), "handled_at": run.handled_at, "cancellation_requested_at": run.cancellation_requested_at, "retry_of_run_id": run.retry_of_run_id}

    @staticmethod
    def _course_dict(course: Course) -> dict[str, Any]:
        return {"id": course.id, "owner_id": course.owner_id, "code": course.code, "name": course.name, "description": course.description, "visibility": course.visibility, "publish_status": course.publish_status, "published_at": course.published_at, "published_by": course.published_by, "version": course.version, "cover_url": course.cover_url, "created_at": course.created_at, "updated_at": course.updated_at}

    @staticmethod
    def _safe_text(value: str | None) -> str | None:
        if not value:
            return value
        return value.replace("Authorization", "[REDACTED]").replace("api_key", "[REDACTED]")[:500]

    def _redact(self, value: Any) -> Any:
        sensitive = {"password", "authorization", "api_key", "api_secret", "token", "content", "prompt"}
        if isinstance(value, dict):
            return {key: "[REDACTED]" if key.casefold() in sensitive else self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value[:20]]
        if isinstance(value, str):
            return value[:500]
        return value

    @staticmethod
    def _audit(db, admin_id: str, action: str, target_type: str, target_id: str, before: dict, after: dict, reason: str) -> None:
        db.add(
            AdminAuditLog(
                id=str(uuid4()),
                admin_user_id=admin_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                before_snapshot=AdminService._json_safe(before),
                after_snapshot=AdminService._json_safe(after),
                reason=reason,
            )
        )

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """Convert an audit snapshot into values accepted by SQL JSON columns."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Enum):
            return AdminService._json_safe(value.value)
        if isinstance(value, dict):
            return {
                str(key): AdminService._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [AdminService._json_safe(item) for item in value]
        return str(value)

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
