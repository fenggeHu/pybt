# Stock MCP Server - 完整使用指南

## 📋 项目概述

这是一个基于MCP (Model Context Protocol) 协议的A股分析服务器，可以集成到OpenCode中，为任何agent提供股票数据分析能力。

### 核心功能

- ✅ 获取A股股票列表和历史数据
- ✅ 分析成交量/成交额激增模式
- ✅ 根据多种条件筛选股票
- ✅ 本地SQLite缓存，提高性能
- ✅ 支持批量操作和增量更新

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd stock-mcp
pip install mcp akshare pandas numpy pydantic httpx
```

或使用安装脚本：

```bash
python install.py
```

### 2. 运行服务器

```bash
# stdio模式（推荐，用于本地集成）
python -m stock_mcp

# HTTP模式（用于远程访问）
python -m stock_mcp --transport http --port 8000
```

### 3. 在OpenCode中配置

在OpenCode的MCP配置文件中添加：

**Windows路径**: `%APPDATA%\OpenCode\User\globalStorage\mcp_config.json`

```json
{
  "mcpServers": {
    "stock_mcp": {
      "command": "python",
      "args": ["-m", "stock_mcp"],
      "cwd": "E:\\opencode\\aaa\\stock-mcp"
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

---

## 🛠️ 可用工具

### 1. get_stock_list
获取所有A股股票列表

**参数**:
- `force_refresh` (bool, 可选): 强制从API刷新

**返回**:
```json
{
  "source": "cache",
  "count": 5000,
  "stocks": [...]
}
```

### 2. get_stock_history
获取单只股票历史数据

**参数**:
- `symbol` (string, 必需): 股票代码，如 "600519"
- `start_date` (string, 必需): 开始日期 "YYYYMMDD"
- `end_date` (string, 必需): 结束日期 "YYYYMMDD"
- `adjust` (string, 可选): 复权类型 ("hfq"后复权, "qfq"前复权, ""不复权)
- `force_refresh` (bool, 可选): 强制刷新

**返回**:
```json
{
  "source": "api",
  "symbol": "600519",
  "count": 90,
  "data": [...]
}
```

### 3. analyze_volume_surge
分析成交量激增

**参数**:
- `symbol` (string, 必需): 股票代码
- `start_date` (string, 必需): 开始日期
- `end_date` (string, 必需): 结束日期
- `recent_days` (int, 可选): 最近几天，默认3
- `compare_period` (int, 可选): 对比周期，默认20天
- `force_refresh` (bool, 可选): 强制刷新

**返回**:
```json
{
  "symbol": "600519",
  "volume_growth_rate": 150.5,
  "amount_growth_rate": 145.2,
  "recent_avg_volume": 12500000,
  "compare_avg_volume": 5000000
}
```

### 4. analyze_amount_surge
分析成交额激增

参数与 analyze_volume_surge 相同

### 5. screen_stocks
筛选股票

**参数**:
- `start_date` (string, 必需): 开始日期
- `end_date` (string, 必需): 结束日期
- `criterion` (string, 可选): "volume_surge" 或 "amount_surge"
- `threshold` (float, 可选): 增长率阈值%，默认50
- `recent_days` (int, 可选): 最近几天，默认3
- `compare_period` (int, 可选): 对比周期，默认20
- `limit` (int, 可选): 返回数量限制，默认20

**返回**:
```json
{
  "criterion": "amount_surge",
  "threshold": 50.0,
  "total_checked": 200,
  "matching_stocks": 15,
  "results": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "amount_growth_rate": 145.2,
      "volume_growth_rate": 150.5
    }
  ]
}
```

### 6. update_cache
更新本地缓存

**参数**:
- `symbols` (string, 可选): 逗号分隔的股票代码
- `start_date` (string, 必需): 开始日期
- `end_date` (string, 必需): 结束日期

### 7. get_cache_status
获取缓存状态

**参数**:
- `detailed` (bool, 可选): 是否返回详细信息

---

## 📊 使用场景示例

### 场景1: 寻找成交额激增的热门股票

```
Step 1: 更新股票列表
  get_stock_list(force_refresh=True)

Step 2: 筛选最近3天成交额增长50%以上的股票
  screen_stocks(
    start_date="20241001",
    end_date="20250101",
    criterion="amount_surge",
    threshold=50.0,
    recent_days=3,
    compare_period=20
  )
```

### 场景2: 分析特定股票的交易活跃度

```
Step 1: 获取股票历史数据
  get_stock_history(
    symbol="600519",
    start_date="20241001",
    end_date="20250101"
  )

Step 2: 分析成交量激增
  analyze_volume_surge(
    symbol="600519",
    start_date="20241001",
    end_date="20250101",
    recent_days=3,
    compare_period=20
  )
```

### 场景3: 批量更新热门股票数据

```
update_cache(
  symbols="600519,000001,600036,600519",
  start_date="20241001",
  end_date="20250101"
)
```

---

## 💡 最佳实践

### 1. 数据缓存策略
- 股票列表缓存1天，避免频繁请求
- 历史数据永久缓存，节省带宽
- 定期使用 `update_cache` 更新最新数据

### 2. 性能优化
- 批量操作前先更新缓存
- 使用合理的 `limit` 参数限制结果数量
- 首次使用后，后续查询从缓存读取，速度极快

### 3. 参数选择建议
- `recent_days`: 通常使用 3-5 天
- `compare_period`: 使用 20-60 天的移动平均
- `threshold`: 成交量/额激增建议 50%-200%

---

## 📁 项目结构

```
stock-mcp/
├── stock_mcp/
│   ├── __init__.py      # 服务器入口
│   ├── config.py        # 配置设置
│   ├── cache.py         # SQLite缓存管理
│   ├── fetcher.py       # AKShare数据获取
│   ├── analyzer.py      # 股票分析逻辑
│   └── tools.py         # MCP工具注册
├── data/
│   └── cache.db         # SQLite数据库（自动创建）
├── pyproject.toml       # 项目配置
├── README.md            # 项目说明
├── USAGE.md             # 详细使用文档
├── install.py           # 安装脚本
├── test_installation.py # 测试脚本
└── demo.py              # 使用示例
```

---

## 🔍 故障排除

### 问题1: 导入错误
```
No module named 'mcp'
```
**解决**:
```bash
pip install mcp akshare pandas numpy pydantic httpx
```

### 问题2: AKShare连接失败
**解决**:
- 检查网络连接
- AKShare可能需要等待一段时间重试
- 确保没有触发反爬机制（内置了延迟）

### 问题3: 数据库错误
```
sqlite3.OperationalError: unable to open database file
```
**解决**:
```bash
mkdir -p data
```

### 问题4: 配置后OpenCode看不到MCP服务器
**解决**:
- 确保服务器正在运行
- 检查配置文件路径是否正确
- 重启OpenCode

---

## 🧪 测试安装

运行测试脚本验证安装：

```bash
python test_installation.py
```

运行示例查看使用方法：

```bash
python demo.py
```

---

## 📚 更多文档

- [README.md](README.md) - 项目概述
- [USAGE.md](USAGE.md) - 详细使用文档
- [OPENCODE_CONFIG.md](OPENCODE_CONFIG.md) - OpenCode配置指南

---

## 📄 许可证

MIT License

---

## 🙏 数据来源

本服务使用 [AKShare](https://github.com/akfamily/akshare) 获取东方财富网的数据。数据仅供分析参考，不构成投资建议。

---

## 🤝 支持

如有问题，请查看：
1. 本项目的README和文档
2. [AKShare官方文档](https://akshare.akfamily.xyz/)
3. [MCP协议文档](https://modelcontextprotocol.io/)

---

**注意**: 本工具仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
