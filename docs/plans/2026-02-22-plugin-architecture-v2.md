# PyBT 插件化架构设计（V2，无兼容模式）

> 日期：2026-02-22  
> 状态：技术设计方案（Design Only）  
> 目标：将全链路核心节点统一为插件装配模式，配置简洁，扩展清晰。

---

## 1. 设计目标

1. 全链路核心节点支持插件化装配：
   - `data_feed`
   - `strategies[]`
   - `portfolio`
   - `execution`
   - `risk[]`
   - `reporters[]`
2. 插件统一通过 `plugin.jsonc` 注册。
3. 默认插件文件查找规则：`plugins/{plugin_name}.py`。
4. 插件接口简洁且必要：统一构造接口，不强行统一运行时业务接口。
5. 配置聚焦“少而清晰”，避免冗余与维度混乱。

---

## 2. 核心决策（最终确认）

### 2.1 `plugin` 与 `transport` 解耦

- `plugin`：供应商/能力扩展维度（如 `eastmoney_marketdata`、`sina_marketdata`）。
- `transport`：接入方式维度（如 `sse` / `websocket` / `api`），属于插件内部参数。
- **不再**把 `sse/websocket/api` 与 `plugin` 放在同一层级。

### 2.2 一个插件只声明一个 `kind`

- 每个插件在 `plugin.jsonc` 只能有一个 `kind`。
- 同名插件不能复用到多个 `kind`。
- 装配时强校验：槽位 `kind` 与插件声明不一致即启动失败。

### 2.3 不做兼容层

- 不保留旧 `type` 装配路径。
- 全部使用新插件装配设计。
- 启动入口只识别新配置 schema。

---

## 3. 术语与模型

- **插件注册中心**：由 `plugin.jsonc` 描述插件元数据。
- **插件装配接口**：每个插件暴露 `create(params, ctx)`。
- **运行时接口**：各 `kind` 仍遵循其领域接口（`DataFeed`、`Strategy` 等），不做硬统一。

---

## 4. 目录与发现规则

默认目录结构：

```text
plugins/
  plugin.jsonc
  eastmoney_marketdata.py
  sina_marketdata.py
  ma_cross.py
  ...
```

发现规则：

1. 读取 `plugins/plugin.jsonc`。
2. 按 `name` 查找插件定义。
3. 若未显式给 `module`，默认模块文件为 `plugins/{name}.py`。
4. 若未显式给 `entry`，默认入口函数为 `create`。

---

## 5. plugin.jsonc 规范

```jsonc
{
  "version": 1,
  "plugin_dir": "./plugins",
  "plugins": [
    {
      "name": "eastmoney_marketdata",
      "kind": "data_feed",
      "module": "eastmoney_marketdata",
      "entry": "create",
      "enabled": true,
      "defaults": {
        "transport": "sse",
        "symbol": "600000",
        "max_reconnects": 3,
        "backoff_seconds": 0.5
      },
      "capabilities": {
        "transports": ["sse", "websocket", "api"]
      }
    },
    {
      "name": "sina_marketdata",
      "kind": "data_feed",
      "defaults": {
        "transport": "api",
        "symbol_transform": "cn_prefix"
      },
      "capabilities": {
        "transports": ["api"]
      }
    },
    {
      "name": "ma_cross",
      "kind": "strategy",
      "defaults": {
        "short_window": 5,
        "long_window": 20
      }
    }
  ]
}
```

字段约束：

- `name`：插件唯一标识。
- `kind`：必填，且仅允许一个值。
- `module`：可选，默认等于 `name`。
- `entry`：可选，默认 `create`。
- `defaults`：可选，作为参数默认值。
- `capabilities`：可选，声明能力（如支持的 transport 列表）。
- `enabled`：可选，禁用时不可被装配。

---

## 6. 运行配置规范（新）

统一形态：`plugin + params`

```jsonc
{
  "name": "live-prod",
  "data_feed": {
    "plugin": "eastmoney_marketdata",
    "params": {
      "symbol": "600000",
      "transport": "sse"
    }
  },
  "strategies": [
    {
      "plugin": "ma_cross",
      "params": {
        "symbol": "600000"
      }
    }
  ],
  "portfolio": { "plugin": "naive_portfolio" },
  "execution": { "plugin": "immediate_execution" },
  "risk": [{ "plugin": "max_position_risk", "params": { "limit": 10000 } }],
  "reporters": [{ "plugin": "equity_reporter" }]
}
```

参数合并规则：

- 最终参数 = `plugin.defaults` 深合并 `runtime.params`（runtime 覆盖 defaults）。

---

## 7. 插件接口设计

### 7.1 统一构造接口（唯一强制）

```python
def create(params: dict, ctx) -> object:
    ...
```

`ctx` 最小建议：

- `plugin_name`
- `kind`
- `run_id`
- `logger`
- `engine_config`

### 7.2 运行时接口（按 kind 校验）

- `data_feed` -> `DataFeed`
- `strategy` -> `Strategy`
- `portfolio` -> `Portfolio`
- `execution` -> `ExecutionHandler`
- `risk` -> `RiskManager`
- `reporter` -> `PerformanceReporter`

> 说明：只统一“构造接口”，不统一业务生命周期接口。

---

## 8. 数据源插件设计原则

1. `data_feed` 由供应商插件承载（如 Eastmoney/Sina）。
2. `transport` 作为该插件参数（不是独立插件类型）。
3. 插件内部根据 `transport` 路由到对应适配器：
   - `transport=sse`
   - `transport=websocket`
   - `transport=api`
4. 若插件声明了 `capabilities.transports`，加载器需校验 `params.transport` 合法性。

示例：

```jsonc
{
  "plugin": "sina_marketdata",
  "params": {
    "symbol": "600000",
    "transport": "api",
    "url": "https://hq.sinajs.cn/list={symbol}",
    "response_mode": "sina_hq",
    "field_map": {
      "price": "3",
      "volume": "8",
      "amount": "9"
    }
  }
}
```

---

## 9. 装配与校验流程

1. 解析运行配置。
2. 对每个槽位读取 `plugin` 名称。
3. 在 `plugin.jsonc` 查找插件定义。
4. 校验：
   - 插件存在且启用。
   - 插件 `kind` 与槽位一致。
   - 若有能力声明，参数（如 `transport`）合法。
5. 加载模块与入口函数。
6. 合并参数并调用 `create(params, ctx)`。
7. 校验返回对象是否实现对应接口。
8. 任一失败立即终止启动并返回可读错误。

---

## 10. 错误语义（建议）

- `PLUGIN_NOT_FOUND`
- `PLUGIN_DISABLED`
- `PLUGIN_KIND_MISMATCH`
- `PLUGIN_ENTRY_NOT_FOUND`
- `PLUGIN_CREATE_FAILED`
- `PLUGIN_INTERFACE_MISMATCH`
- `PLUGIN_UNSUPPORTED_TRANSPORT`
- `PLUGIN_INVALID_PARAMS`

错误信息必须包含：`plugin_name`、`kind`、`slot`、关键参数（脱敏后）。

---

## 11. 安全与治理

- 仅允许从 `plugin_dir` 加载插件模块（禁止任意路径导入）。
- 不自动执行插件模块中的副作用代码以外逻辑（入口统一 `create`）。
- 建议提供插件白名单（生产环境可选）。

---

## 12. 非目标（明确）

- 不提供旧配置 `type` -> 新插件配置的自动兼容转换。
- 不支持一个插件声明多个 `kind`。
- 不将 `transport` 抽象为独立顶层插件类型。

---

## 13. 交付物（后续实现阶段）

1. `PluginRegistry`（读取/校验 `plugin.jsonc`）
2. `PluginLoader`（discover/load/create/validate）
3. `configuration.loader` 重构为插件驱动装配
4. `definitions` 改造为从注册中心导出
5. 最小示例插件与 E2E 测试样例

