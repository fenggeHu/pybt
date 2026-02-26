# Futu 行情桥接服务

基于 Futu OpenAPI（OpenD + `futu-api` Python SDK）提供两个基础能力：

- 实时行情查询（快照、实时报价、实时 K 线）
- 实时订阅推送（SSE，对应 Futu `subscribe(subscribe_push=True)`）
- 历史 K 线查询（支持分页）

## 1. 前置条件

1. 安装并启动 Futu OpenD（默认监听 `127.0.0.1:11111`）。
2. OpenD 已登录并具备对应市场行情权限。
3. Python 3.10+。

## 2. 独立部署（推荐）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r futu/requirements.txt
uvicorn futu.server:app --host 127.0.0.1 --port 8001 --reload
```

可选环境变量：

- `FUTU_OPEND_HOST`：默认 `127.0.0.1`
- `FUTU_OPEND_PORT`：默认 `11111`
- `FUTU_OPEND_IS_ENCRYPT`：`true/false`，默认不传

## 3. 接口

说明：Futu 为独立服务，接口无额外前缀。

OpenAPI 文档：`http://127.0.0.1:8001/docs`，接口已按 `FUTU` tag 分组。

### 健康检查

```bash
curl "http://127.0.0.1:8001/healthz"
```

### 实时快照

```bash
curl "http://127.0.0.1:8001/quote/realtime/snapshot?codes=SH.600000,SZ.000001"
```

### 实时报价（订阅 QUOTE 后拉取）

```bash
curl "http://127.0.0.1:8001/quote/realtime/stock?codes=SH.600000,SZ.000001&session=NONE"
```

### 实时 K 线

```bash
curl "http://127.0.0.1:8001/quote/realtime/kline?code=SH.600000&num=60&ktype=K_1M&autype=QFQ"
```

### 订阅查询（查看 OpenD 当前订阅）

```bash
curl "http://127.0.0.1:8001/quote/subscription/query?is_all_conn=false"
```

### 订阅推送（SSE）

```bash
curl -N "http://127.0.0.1:8001/quote/subscribe/sse?codes=SH.600000,SZ.000001&subtypes=QUOTE,K_1M&session=NONE"
```

返回为 `text/event-stream`，会持续推送 `event: quote` 事件；断开连接后自动取消订阅并关闭连接。

### 历史 K 线

```bash
curl "http://127.0.0.1:8001/quote/history/kline?code=SH.600000&start=2025-01-01&end=2025-02-26&ktype=K_DAY&autype=QFQ&all_pages=true"
```

## 4. 参考文档

- Futu OpenAPI 文档首页：<https://openapi.futunn.com/futu-api-doc/>
- Python 接口：`get_market_snapshot`、`subscribe`、`query_subscription`、`get_stock_quote`、`get_cur_kline`、`request_history_kline`
