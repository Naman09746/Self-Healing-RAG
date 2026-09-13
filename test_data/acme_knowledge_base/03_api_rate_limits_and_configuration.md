# AcmeCloud — API Specifications, Rate Limits & Gateway Configuration

## 1. Plan-Tier Rate Limits
To prevent service degradation and ensure fair resource distribution, the API gateway enforces token-bucket rate limits per client:

* **Starter Plan**: 100 requests per minute.
* **Professional Plan**: **1,000 requests per minute** per workspace API key.
* **Enterprise Plan**: **5,000 requests per minute** with burst capacity up to 7,500 requests per minute.

## 2. Request Timeout & Gateway Behavior
* **Default Request Timeout**: The default API gateway HTTP timeout is configured to **30 seconds**. If backend processing exceeds 30 seconds, a `504 Gateway Timeout` is emitted.
* *Note*: The 30-second timeout setting represents maximum gateway wait time, not a service-level latency guarantee for request execution.
