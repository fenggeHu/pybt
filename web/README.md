# pybt 前端控制台

Vue 3 + Vite + TypeScript 构建的量化回测控制台，可对接后端 REST/SSE API。

## 快速开始

```bash
cd web
npm install   # 或 pnpm install / yarn install
npm run dev   # 默认 http://localhost:5173
```

- 默认将 `/api` 代理到 `http://localhost:8000`（参考 `vite.config.ts`）。
- 创建 `.env.local` 可覆盖 `VITE_API_BASE_URL` 等配置。

## 目录结构

```
src/
  assets/         静态资源
  components/     可复用组件（图表、表单）
  layouts/        布局组件
  router/         Vue Router 配置
  services/       Axios 请求封装
  store/          Pinia 状态管理
  views/          页面：仪表盘、数据、策略、回测、历史、详情
  styles/         全局样式（含 Element Plus 主题定制）
  types/          类型定义
```

## 主要页面

- 仪表盘：概览指标、最新权益曲线、任务时间线。
- 数据管理：上传/删除 CSV 数据集。
- 策略配置：维护 SMA / Breakout / Weighted 策略模板。
- 回测执行：参数表单、风控与 allocator 设置、近期结果。
- 回测历史：历史任务列表、导出指标/权益/交易。
- 回测详情：指标卡片、权益图、交易列表。

## API 约定

- `GET /api/datasets`、`POST /api/datasets`
- `GET /api/strategies`、`POST /api/strategies`
- `POST /api/backtests` -> `{ task_id }`
- `GET /api/backtests` / `GET /api/backtests/:id`
- `GET /api/backtests/:id/download?type=metrics|equity|trades`

根据实际后端实现调整 `services/api.ts` 即可。
