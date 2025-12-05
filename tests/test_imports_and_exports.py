import pybt


def test_top_level_imports() -> None:
    # 包可正常导入且关键组件已暴露
    assert hasattr(pybt, "BacktestEngine")
    assert hasattr(pybt.strategies, "MovingAverageCrossStrategy")
    assert hasattr(pybt.strategies, "UptrendBreakoutStrategy")
