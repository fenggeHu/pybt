## 前端（Vue 3 + Vite + Naive UI）

### 运行
```bash
cd frontend
npm install
# 如后端地址不同可设置环境变量
# export VITE_API_BASE=http://127.0.0.1:8000/api
npm run dev
```
访问 http://127.0.0.1:5173 （无 token 会跳到 /login）。

### 功能
- 登录鉴权：登录获取 JWT，401 自动登出。
- 菜单：概览、配置、数据源、任务、任务详情（SSE/WS）、组件定义、审计、设置。
- 配置：列表、创建、JSON 校验、删除。
- 数据源：列表、创建、探测。
- 任务：列表、创建（选 config_id 或粘贴 JSON）、取消；详情实时进度/事件。
- 审计：查看最近操作。
- 主题/语言：亮/暗/跟随系统；中/英。

### 注意
- 需后端 `uvicorn backend.app:app --reload` 已启动并可访问。
- 登录使用后端 `/auth/login` 简单校验，返回的 token 会自动附加在请求头。
