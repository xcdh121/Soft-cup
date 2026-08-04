"""User billing, orders and signed payment callback endpoints."""

import hashlib
import hmac
import json

from auth import get_current_user
from config import get_settings
from edu_core.schemas.users import UserDto
from edu_core.services import BillingError, BillingService
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    plan_code: str = Field(min_length=1, max_length=50)
    provider: str = Field(pattern="^(manual_wechat|manual_qq|wechat_pay|alipay)$")


class SubmitPaymentClaimRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    payment_claim_note: str = Field(min_length=2, max_length=120)
    payment_reference: str | None = Field(default=None, max_length=64)


class PaymentNotification(BaseModel):
    order_no: str
    event_id: str
    transaction_id: str
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    status: str = Field(pattern="^paid$")


def service() -> BillingService:
    settings = get_settings()
    return BillingService(order_expiry_minutes=settings.billing_order_expiry_minutes)


def manual_payment_allowed(provider: str | None = None) -> bool:
    settings = get_settings()
    enabled = (
        settings.billing_manual_payment_enabled
        and settings.billing_environment.casefold() != "production"
    )
    if not enabled or provider is None:
        return enabled
    return any(method["provider"] == provider for method in manual_payment_methods())


def manual_payment_methods() -> list[dict[str, str]]:
    if not manual_payment_allowed():
        return []
    settings = get_settings()
    recipient = settings.billing_manual_payment_recipient.strip()
    configured = (
        ("manual_wechat", "微信收款码", settings.billing_manual_wechat_qr_url),
        ("manual_qq", "QQ 收款码", settings.billing_manual_qq_qr_url),
    )
    return [
        {
            "provider": provider,
            "label": label,
            "qr_code_url": qr_url.strip(),
            "recipient": recipient,
            "instructions": "请支付订单显示的准确金额。付款后提交付款昵称和流水号尾号供管理员核对。",
        }
        for provider, label, qr_url in configured
        if qr_url.strip()
    ]


def payment_details(provider: str) -> dict[str, str]:
    method = next(
        (item for item in manual_payment_methods() if item["provider"] == provider),
        None,
    )
    if not method:
        raise HTTPException(status_code=503, detail="该人工收款方式尚未配置")
    return {
        "kind": "manual_qr",
        **method,
        "message": "扫码付款后请提交核对信息。权益仅在管理员确认到账后开通。",
    }


@router.get("/plans", response_model=list[dict])
def list_plans():
    return service().list_plans()


@router.get("/payment-methods", response_model=list[dict])
def list_payment_methods(current_user: UserDto = Depends(get_current_user)):
    del current_user
    return manual_payment_methods()


@router.get("/me", response_model=dict)
def get_my_billing(current_user: UserDto = Depends(get_current_user)):
    return service().billing_summary(user_id=current_user.id)


@router.get("/me/quotas", response_model=dict)
def get_my_quotas(current_user: UserDto = Depends(get_current_user)):
    return service().billing_summary(user_id=current_user.id)["quotas"]


@router.get("/orders", response_model=list[dict])
def list_my_orders(current_user: UserDto = Depends(get_current_user)):
    return service().list_orders(user_id=current_user.id)


@router.post("/orders", response_model=dict, status_code=201)
def create_order(payload: CreateOrderRequest, current_user: UserDto = Depends(get_current_user)):
    settings = get_settings()
    if payload.provider.startswith("manual_") and not manual_payment_allowed(payload.provider):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="演示支付渠道未启用")
    try:
        order = service().create_order(user_id=current_user.id, plan_code=payload.plan_code, provider=payload.provider)
    except BillingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    order["payment"] = (
        payment_details(payload.provider)
        if payload.provider.startswith("manual_")
        else {
            "kind": "provider_pending",
            "message": "支付渠道适配器尚未配置",
            "callback_url": f"{settings.payment_callback_base_url}/{payload.provider}",
        }
    )
    return order


@router.get("/orders/{order_no}", response_model=dict)
def get_order(order_no: str, current_user: UserDto = Depends(get_current_user)):
    try:
        order = service().get_order(user_id=current_user.id, order_no=order_no)
        if order["provider"].startswith("manual_"):
            order["payment"] = payment_details(order["provider"])
        return order
    except BillingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders/{order_no}/close", response_model=dict)
def close_order(order_no: str, current_user: UserDto = Depends(get_current_user)):
    try:
        return service().close_order(user_id=current_user.id, order_no=order_no)
    except BillingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/orders/{order_no}/payment-claim", response_model=dict)
def submit_payment_claim(
    order_no: str,
    payload: SubmitPaymentClaimRequest,
    current_user: UserDto = Depends(get_current_user),
):
    try:
        return service().submit_payment_claim(
            user_id=current_user.id,
            order_no=order_no,
            payment_claim_note=payload.payment_claim_note,
            payment_reference=payload.payment_reference,
        )
    except BillingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/payment-notify/{provider}", response_model=dict)
async def payment_notify(
    provider: str,
    request: Request,
    x_payment_signature: str | None = Header(default=None),
):
    """Handle a normalized provider callback using HMAC-SHA256 verification."""
    if provider not in {"wechat_pay", "alipay"}:
        raise HTTPException(status_code=404, detail="支付渠道不存在")
    secret = get_settings().payment_webhook_secret
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="支付回调密钥未配置")
    raw = await request.body()
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not x_payment_signature or not hmac.compare_digest(expected, x_payment_signature):
        raise HTTPException(status_code=401, detail="支付通知验签失败")
    try:
        payload = PaymentNotification.model_validate(json.loads(raw))
        return service().process_payment(
            order_no=payload.order_no,
            provider=provider,
            provider_event_id=f"{provider}:{payload.event_id}",
            provider_transaction_id=f"{provider}:{payload.transaction_id}",
            amount_cents=payload.amount_cents,
            currency=payload.currency,
            payload_digest=BillingService.payload_digest(raw),
            verified=True,
        )
    except (BillingError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
