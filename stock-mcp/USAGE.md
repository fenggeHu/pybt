# Stock MCP Server - 使用指南

## 安装

1. 确保已安装Python 3.10+
2. 安装依赖：

```bash
cd stock-mcp
pip install -e .
```

或者使用 uv:

```bash
cd stock-mcp
uv pip install -e .
```

## 运行服务器

### 使用stdio模式（默认，适合本地调用）

```bash
python -m stock_mcp
```

### 使用HTTP模式（适合远程访问）

```bash
python -m stock_mcp --transport http --port 8000
```

## 在OpenCode中配置MCP

在OpenCode的MCP配置文件中添加：

```json
{
  "mcpServers": {
    "stock_mcp": {
      "command": "python",
      "args": ["-m", "stock_mcp"]
    }
  }
}
```

如果使用HTTP模式：

```json
{
  "mcpServers": {
    "stock_mcp": {
      "transport": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## 可用工具

### 1. get_stock_list
获取所有A股股票列表

**参数：**
- `force_refresh` (bool, 可选): 强制从API刷新，即使缓存是最新的

**示例：**
```json
{
  "force_refresh": false
}
```

### 2. get_stock_history
获取单只股票的历史数据

**参数：**
- `symbol` (string, 必需): 股票代码 (如 "600519", "000001")
- `start_date` (string, 必需): 开始日期，格式 "YYYYMMDD" (如 "20240101")
- `end_date` (string, 必需): 结束日期，格式 "YYYYMMDD" (如 "20241231")
- `adjust` (string, 可选): 复权类型 ("hfq"=后复权, "qfq"=前复权, ""=不复权)
- `force_refresh` (bool, 可选): 强制从API获取，即使缓存中已有

**示例：**
```json
{
  "symbol": "600519",
  "start_date": "20241001",
  "end_date": "20241231",
  "adjust": "hfq",
  "force_refresh": false
}
```

### 3. analyze_volume_surge
分析股票的成交量激增情况

**参数：**
- `symbol` (string, 必需): 股票代码
- `start_date` (string, 必需): 开始日期
- `end_date` (string, 必需): 结束日期
- `recent_days` (int, 可选): 最近几天分析 (默认: 3)
- `compare_period` (int, 可选): 对比周期天数 (默认: 20)
- `force_refresh` (bool, 可选): 强制刷新

**返回：**
- volume_growth_rate: 成交量增长率 (%)
- amount_growth_rate: 成交额增长率 (%)
- recent_avg_volume: 最近平均成交量
- compare_avg_volume: 对比期平均成交量

### 4. analyze_amount_surge
分析股票的成交额激增情况

**参数：**
- 与 analyze_volume_surge 相同

**返回：**
- 重点显示成交额增长率

### 5. screen_stocks
根据条件筛选股票

**参数：**
- `start_date` (string, 必需): 开始日期
- `end_date` (string, 必需): 结束日期
- `criterion` (string, 可选): 筛选条件 ("volume_surge" 或 "amount_surge", 默认: "volume_surge")
- `threshold` (float, 可选): 增长率阈值 (%) (默认: 50.0)
- `recent_days` (int, 可选): 最近几天 (默认: 3)
- `compare_period` (int, 可选): 对比周期 (默认: 20)
- `limit` (int, 可选): 返回结果数量限制 (默认: 20)
- `force_refresh` (bool, 可选): 强制刷新

**返回：**
- 符合条件的股票列表，按增长率排序

### 6. update_cache
更新本地数据缓存

**参数：**
- `symbols` (string, 可选): 逗号分隔的股票代码 (如 "600519,000001")，如果为None则更新列表中的所有股票
- `start_date` (string, 必需): 开始日期
- `end_date` (string, 必需): 结束日期

**示例：**
```json
{
  "symbols": "600519,000001",
  "start_date": "20241001",
  "end_date": "20241231"
}
```

### 7. get_cache_status
获取缓存状态和统计信息

**参数：**
- `detailed` (bool, 可选): 是否返回详细信息 (默认: false)

**返回：**
- cached_stocks: 已缓存的股票数量
- stock_list_count: 股票列表中的股票数量
- date_range: 数据日期范围 (详细模式)
- database_size_bytes: 数据库大小 (详细模式)

## 使用示例

### 场景1：分析最近3月成交额增长50%以上的股票

```python
# 首先更新股票列表
get_stock_list()

# 然后筛选符合条件的股票
screen_stocks(
    start_date="20241001",
    end_date="20250101",
    criterion="amount_surge",
    threshold=50.0,
    recent_days=3,
    compare_period=20
)
```

### 场景2：分析特定股票的成交量激增

```python
analyze_volume_surge(
    symbol="600519",
    start_date="20241001",
    end_date="20250101",
    recent_days=3,
    compare_period=20
)
```

### 场景3：获取单只股票的历史数据

```python
get_stock_history(
    symbol="600519",
    start_date="20241001",
    end_date="20250101",
    adjust="hfq"
)
```

## 数据缓存

服务器使用SQLite数据库缓存数据，路径为：`data/cache.db`

缓存策略：
- 股票列表缓存1天
- 历史数据永久缓存（可手动刷新）
- 增量更新：仅获取新的交易日数据

## 注意事项

1. **首次使用**：需要先运行 `get_stock_list()` 和 `update_cache()` 来填充缓存
2. **性能优化**：批量操作时建议先更新缓存，再进行筛选
3. **API限制**：AKShare是免费API，建议在两次请求之间有1秒延迟（已内置）
4. **数据来源**：数据来自东方财富网，仅用于分析参考

## 故障排除

### 导入错误
如果遇到 "No module named 'mcp'" 错误：
```bash
pip install mcp
```

### AKShare安装错误
```bash
pip install akshare pandas numpy
```

### 数据库错误
确保 `data` 目录存在且可写：
```bash
mkdir -p data
```

## 许可证

MIT
