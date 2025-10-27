# PyBT 回测示例

本目录包含使用 PyBT 框架进行量化回测的示例代码。

## 示例列表

### 1. simple_backtest.py - 基础回测示例
使用合成数据演示基本的回测流程，适合快速了解框架使用方法。

**运行:**
```bash
python examples/simple_backtest.py
```

### 2. detailed_report_demo.py - 详细报告示例
展示 `DetailedReporter` 的功能，包括交易明细、最大回撤等详细指标。

**运行:**
```bash
python examples/detailed_report_demo.py
```

**输出内容:**
- 完整的回测摘要（收益率、最大回撤、交易次数等）
- 详细的交易明细（每笔交易的时间、价格、持仓变化）
- 最终持仓状态

### 3. adata_backtest.py - 真实数据回测
使用 [adata](https://github.com/1nchaos/adata) 获取 A 股真实历史数据进行回测。

**特点:**
- 使用真实的 A 股日线数据
- 实现双均线交叉策略
- 对比买入持有策略的表现

**依赖安装:**
```bash
pip install adata
```

**运行:**
```bash
python examples/adata_backtest.py
```

**自定义参数:**
可以修改代码中的以下参数：
- `stock_code`: 股票代码（如 '000001' 平安银行）
- `start_date` / `end_date`: 回测时间范围
- `initial_cash`: 初始资金
- `short_window` / `long_window`: 均线周期

### 4. adata_multi_stock.py - 多股票轮动策略
使用 adata 获取多只股票数据，实现动量轮动策略。

**特点:**
- 多股票数据获取
- 动量轮动策略实现
- 定期调仓机制

**依赖安装:**
```bash
pip install adata pandas
```

**运行:**
```bash
python examples/adata_multi_stock.py
```

**策略说明:**
- 每隔一段时间（默认 20 天）重新评估股票池
- 计算每只股票的动量（过去 N 天的收益率）
- 持有动量最高的股票，卖出其他股票

## 关于 adata

[adata](https://github.com/1nchaos/adata) 是一个开源的 A 股数据获取工具，提供：
- 股票日线/分钟线数据
- 财务数据
- 指数数据
- 完全免费

**首次使用:**
```python
import adata
# 获取平安银行 2023 年的日线数据
df = adata.stock.market.get_market(
    stock_code='000001',
    start_date='2023-01-01',
    end_date='2023-12-31'
)
```

## 新功能：DetailedReporter

框架现在提供了增强的 `DetailedReporter`，相比基础的 `EquityCurveReporter`，它提供：

### 功能特性
- **交易记录**: 记录每笔交易的完整信息（时间、价格、数量、手续费等）
- **权益曲线**: 跟踪每个时间点的账户权益
- **最大回撤**: 自动计算最大回撤比例
- **详细统计**: 交易次数、买卖次数、总手续费等
- **格式化输出**: 提供美观的表格输出

### 使用方法
```python
from pybt import DetailedReporter

# 创建报告器
reporter = DetailedReporter(initial_cash=100_000.0)

# 在回测引擎中使用
engine = BacktestEngine(
    # ... 其他组件
    reporters=[reporter],
)

# 运行回测
engine.run()

# 打印详细摘要
reporter.print_summary()

# 打印交易明细（显示最近 30 笔）
reporter.print_trades(limit=30)

# 获取原始数据用于自定义分析
summary = reporter.get_summary()
trades = reporter.trades
equity_curve = reporter.equity_curve
```

### 输出示例
```
============================================================
                         回测摘要                          
============================================================

初始资金: 100,000.00
最终权益: 105,234.50
总收益: 5,234.50
收益率: 5.23%
最大回撤: 3.45%

交易统计:
  总交易次数: 24
  买入次数: 12
  卖出次数: 12
  总手续费: 120.00

最终状态:
  现金余额: 45,234.50
  持仓:
    000001: 500 股 (市值: 60,000.00)
============================================================
```

## 扩展建议

基于这些示例，你可以：

1. **实现自定义策略**: 继承 `Strategy` 接口，实现 `on_market` 方法
2. **添加更多指标**: 在策略中计算 RSI、MACD、布林带等技术指标
3. **优化风险管理**: 实现止损、止盈、仓位管理等风险控制
4. **自定义报告器**: 继承 `PerformanceReporter`，添加夏普比率、卡玛比率等指标
5. **使用分钟数据**: adata 支持分钟级数据，可用于日内策略
6. **导出数据**: 使用 `reporter.trades` 和 `reporter.equity_curve` 导出到 CSV 或数据库

## 常见问题

**Q: adata 获取数据失败？**
A: 首次使用需要联网下载数据，请确保网络连接正常。数据会缓存到本地。

**Q: 如何获取更多股票代码？**
A: 
- 深市股票: 000001-002999
- 沪市股票: 600000-603999
- 科创板: 688000-688999

**Q: 回测结果不理想？**
A: 这是正常的！示例策略仅用于演示，实际交易需要：
- 更复杂的策略逻辑
- 严格的风险管理
- 充分的回测和验证
- 考虑交易成本和滑点

## 技术支持

- PyBT 框架问题: 查看项目文档
- adata 使用问题: https://github.com/1nchaos/adata
