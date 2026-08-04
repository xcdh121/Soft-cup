# 比赛演示收款码

将本人导出的原始收款码图片放在本目录，并使用以下文件名：

- `wechat.png`：微信收款码
- `qq.png`：QQ 收款码

本目录默认忽略二维码图片，避免个人收款码被误提交到公开 Git 仓库；部署时请通过私有发布流程复制图片。也可以把图片放在受控对象存储中，并把下方 URL 配置成对应的 HTTPS 地址。

然后在部署环境中配置：

```dotenv
BILLING_ENVIRONMENT=competition
BILLING_MANUAL_PAYMENT_ENABLED=true
BILLING_MANUAL_PAYMENT_RECIPIENT=你的收款昵称
BILLING_MANUAL_WECHAT_QR_URL=/payment-codes/wechat.png
BILLING_MANUAL_QQ_QR_URL=/payment-codes/qq.png
```

只配置实际存在的图片。未配置 URL 的渠道不会显示。

个人静态收款码没有服务端支付回调，用户点击“我已付款”只会提交待核对信息；必须由管理员在订单后台核对真实到账后确认，权益才会发放。正式商用时关闭此渠道并改接有验签回调的合规商户支付。
