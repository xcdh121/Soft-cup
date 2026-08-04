"""Administrator API. Every endpoint is denied by default to non-admin users."""

from auth import require_admin
from config import get_settings
from edu_core.schemas.users import UserDto
from edu_core.services import AdminService, BillingError, BillingService
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from security import hash_password

from routers.billing import manual_payment_allowed

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class ReasonRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: str = Field(min_length=2, max_length=500)


class UpdateUserRequest(ReasonRequest):
    is_active: bool | None = None
    is_admin: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class EntitlementRequest(ReasonRequest):
    plan_id: str


class QuotaAdjustmentRequest(ReasonRequest):
    resource_type: str = Field(min_length=1, max_length=80)
    quantity: int


class PlanRequest(ReasonRequest):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    quotas: dict[str, int] | None = None
    features: dict | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class HandlingRequest(ReasonRequest):
    handled: bool = True


class CourseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = None


class CourseUpdateRequest(ReasonRequest):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = None
    cover_url: str | None = Field(default=None, max_length=2000)


def admin_service() -> AdminService:
    return AdminService()


def billing_service() -> BillingService:
    return BillingService(order_expiry_minutes=get_settings().billing_order_expiry_minutes)


def translate_error(exc: BillingError, *, not_found: bool = False):
    raise HTTPException(status_code=404 if not_found else 409, detail=str(exc)) from exc


@router.get("/overview", response_model=dict)
def overview():
    return admin_service().overview()


@router.get("/users", response_model=dict)
def users(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str | None = None, is_active: bool | None = None,
):
    return admin_service().list_users(page=page, page_size=page_size, search=search, is_active=is_active)


@router.get("/users/{user_id}", response_model=dict)
def user_detail(user_id: str):
    try:
        return admin_service().user_detail(user_id)
    except BillingError as exc:
        translate_error(exc, not_found=True)


@router.patch("/users/{user_id}", response_model=dict)
def update_user(user_id: str, payload: UpdateUserRequest, admin: UserDto = Depends(require_admin)):
    values = payload.model_dump(exclude={"reason", "new_password"}, exclude_none=True)
    if payload.new_password:
        values["password_hash"] = hash_password(payload.new_password)
    try:
        return admin_service().update_user(user_id=user_id, admin_id=admin.id, values=values, reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.post("/users/{user_id}/entitlements", response_model=dict, status_code=201)
def grant_entitlement(user_id: str, payload: EntitlementRequest, admin: UserDto = Depends(require_admin)):
    try:
        return billing_service().grant_entitlement(user_id=user_id, plan_id=payload.plan_id, admin_user_id=admin.id, reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.post("/users/{user_id}/quota-adjustments", response_model=dict)
def adjust_quota(user_id: str, payload: QuotaAdjustmentRequest, admin: UserDto = Depends(require_admin)):
    try:
        return billing_service().adjust_quota(user_id=user_id, resource_type=payload.resource_type, quantity=payload.quantity, admin_user_id=admin.id, reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.get("/orders", response_model=dict)
def orders(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str | None = None, status: str | None = None, provider: str | None = None,
):
    return admin_service().list_orders(page=page, page_size=page_size, search=search, status=status, provider=provider)


@router.get("/orders/{order_no}", response_model=dict)
def order_detail(order_no: str):
    try:
        return admin_service().order_detail(order_no)
    except BillingError as exc:
        translate_error(exc, not_found=True)


@router.post("/orders/{order_no}/confirm-payment", response_model=dict)
def confirm_manual_payment(order_no: str, payload: ReasonRequest, admin: UserDto = Depends(require_admin)):
    if not manual_payment_allowed():
        raise HTTPException(status_code=403, detail="人工支付确认未启用")
    try:
        order = admin_service().order_detail(order_no)
        if order["provider"] not in {"manual", "manual_wechat", "manual_qq"}:
            raise BillingError("仅人工收款订单可确认")
        return billing_service().process_payment(
            order_no=order_no, provider=order["provider"], provider_event_id=f"manual:{order_no}",
            provider_transaction_id=f"manual:{order_no}", amount_cents=order["amount_cents"],
            currency=order["currency"], payload_digest=BillingService.payload_digest(order_no.encode()),
            verified=True, admin_user_id=admin.id, reason=payload.reason,
        )
    except BillingError as exc:
        translate_error(exc)


@router.post("/orders/{order_no}/refund", response_model=dict)
def refund_order(order_no: str, payload: ReasonRequest, admin: UserDto = Depends(require_admin)):
    try:
        return billing_service().refund_order(order_no=order_no, admin_user_id=admin.id, reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.get("/billing-plans", response_model=list[dict])
def plans():
    return billing_service().list_plans(include_inactive=True)


@router.post("/billing-plans", response_model=dict, status_code=201)
def create_plan(payload: PlanRequest, admin: UserDto = Depends(require_admin)):
    values = payload.model_dump(exclude={"reason"}, exclude_none=True)
    try:
        return billing_service().update_plan(plan_id=None, values=values, admin_user_id=admin.id, reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.patch("/billing-plans/{plan_id}", response_model=dict)
def update_plan(plan_id: str, payload: PlanRequest, admin: UserDto = Depends(require_admin)):
    values = payload.model_dump(exclude={"reason", "code"}, exclude_none=True)
    try:
        return billing_service().update_plan(plan_id=plan_id, values=values, admin_user_id=admin.id, reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.get("/agent-runs", response_model=dict)
def agent_runs(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str | None = None, search: str | None = None, suspected_stuck: bool | None = None,
):
    return admin_service().list_agent_runs(page=page, page_size=page_size, status=status, search=search, suspected_stuck=suspected_stuck)


@router.get("/agent-runs/{run_id}", response_model=dict)
def agent_run_detail(run_id: str):
    try:
        return admin_service().agent_run_detail(run_id)
    except BillingError as exc:
        translate_error(exc, not_found=True)


@router.patch("/agent-runs/{run_id}/handling", response_model=dict)
def handle_run(run_id: str, payload: HandlingRequest, admin: UserDto = Depends(require_admin)):
    try:
        return admin_service().update_run(run_id=run_id, admin_id=admin.id, action="handling", handled=payload.handled, reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.post("/agent-runs/{run_id}/cancel", response_model=dict)
def cancel_run(run_id: str, payload: ReasonRequest, admin: UserDto = Depends(require_admin)):
    try:
        return admin_service().update_run(run_id=run_id, admin_id=admin.id, action="cancel", reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.post("/agent-runs/{run_id}/retry", response_model=dict, status_code=201)
def retry_run(run_id: str, payload: ReasonRequest, admin: UserDto = Depends(require_admin)):
    try:
        return admin_service().update_run(run_id=run_id, admin_id=admin.id, action="retry", reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.get("/courses", response_model=dict)
def courses(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str | None = None, search: str | None = None,
):
    return admin_service().list_courses(page=page, page_size=page_size, status=status, search=search)


@router.post("/courses", response_model=dict, status_code=201)
def create_course(payload: CourseCreateRequest, admin: UserDto = Depends(require_admin)):
    return admin_service().create_course(admin_id=admin.id, name=payload.name, code=payload.code, description=payload.description)


@router.patch("/courses/{course_id}", response_model=dict)
def update_course(
    course_id: str,
    payload: CourseUpdateRequest,
    admin: UserDto = Depends(require_admin),
):
    try:
        return admin_service().update_course(
            course_id=course_id,
            admin_id=admin.id,
            values=payload.model_dump(exclude={"reason"}, exclude_unset=True),
            reason=payload.reason,
        )
    except BillingError as exc:
        translate_error(exc)


@router.post("/courses/{course_id}/{action}", response_model=dict)
def course_action(course_id: str, action: str, payload: ReasonRequest, admin: UserDto = Depends(require_admin)):
    mapping = {"publish": "published", "unpublish": "unpublished", "archive": "archived"}
    if action not in mapping:
        raise HTTPException(status_code=404, detail="课程操作不存在")
    try:
        return admin_service().change_course_status(course_id=course_id, admin_id=admin.id, target=mapping[action], reason=payload.reason)
    except BillingError as exc:
        translate_error(exc)


@router.get("/audit-logs", response_model=dict)
def audit_logs(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), action: str | None = None,
):
    return admin_service().audit_logs(page=page, page_size=page_size, action=action)
