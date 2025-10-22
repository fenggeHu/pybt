from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pybt.data.bar import Bar
from pybt.data.loader import DataSpec, generate_synthetic, load_csv
from pybt.engine.backtester import run_backtest as run_single_backtest
from pybt.engine.multi import run_backtest_multi
from pybt.execution.broker import SimBroker
from pybt.portfolio.multi import MultiPortfolio
from pybt.portfolio.portfolio import Portfolio
from pybt.risk.rules import RiskConfig, RiskManager
from pybt.strategy.base import Strategy
from pybt.strategy.breakout import DonchianBreakout
from pybt.strategy.sma_crossover import SmaCrossStrategy
from pybt.strategy.weight import SmaTrendWeightStrategy
from pybt.allocation.weights import WeightAllocator
from .schemas import (
    AllocatorConfigPayload,
    BacktestRequest,
    BacktestResponse,
    BacktestResult,
    BacktestSummary,
    DatasetInfo,
    StrategyConfig,
    StrategyPayload,
    EquityPoint,
    TradeRecord,
)

DATA_DIR = Path("data")
STRATEGY_FILE = DATA_DIR / "strategies.json"

app = FastAPI(title="pybt API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"] ,
    allow_headers=["*"],
)


class StrategyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._strategies: Dict[str, StrategyConfig] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._strategies = self._default_strategies()
            self._persist()
            return
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self._strategies = {
            item["id"]: StrategyConfig(
                **item,
                updatedAt=datetime.fromisoformat(item["updatedAt"])
            )
            for item in data
        }

    def _persist(self) -> None:
        payload = [
            {
                **cfg.dict(),
                "updatedAt": cfg.updatedAt.isoformat(),
            }
            for cfg in self._strategies.values()
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _default_strategies(self) -> Dict[str, StrategyConfig]:
        now = datetime.utcnow()
        defaults = [
            StrategyConfig(
                id="sma-default",
                name="SMA Crossover",
                type="sma",
                params={"fast": 10, "slow": 30, "allow_short": False},
                updatedAt=now,
            ),
            StrategyConfig(
                id="breakout-default",
                name="Donchian Breakout",
                type="breakout",
                params={"lookback": 20, "qty": 1, "allow_short": True},
                updatedAt=now,
            ),
            StrategyConfig(
                id="weighted-default",
                name="Weighted SMA Trend",
                type="weighted",
                params={"symbol": "AAPL", "fast": 10, "slow": 30, "long_weight": 0.5, "short_weight": -0.5},
                updatedAt=now,
            ),
        ]
        return {cfg.id: cfg for cfg in defaults}

    def list(self) -> List[StrategyConfig]:
        return sorted(self._strategies.values(), key=lambda x: x.updatedAt, reverse=True)

    def upsert(self, payload: StrategyPayload) -> StrategyConfig:
        now = datetime.utcnow()
        strategy_id = payload.id or f"strategy-{uuid4().hex[:8]}"
        cfg = StrategyConfig(
            id=strategy_id,
            name=payload.name,
            type=payload.type,
            params=payload.params,
            updatedAt=now,
        )
        self._strategies[strategy_id] = cfg
        self._persist()
        return cfg

    def get(self, strategy_id: str) -> StrategyConfig:
        if strategy_id not in self._strategies:
            raise KeyError(strategy_id)
        return self._strategies[strategy_id]


strategy_store = StrategyStore(STRATEGY_FILE)


class TaskState:
    def __init__(self) -> None:
        self.tasks: Dict[str, BacktestResult] = {}
        self.summaries: Dict[str, BacktestSummary] = {}

    def create(self, name: str) -> str:
        task_id = uuid4().hex
        summary = BacktestSummary(
            id=task_id,
            name=name,
            status="queued",
            startedAt=datetime.utcnow(),
        )
        self.summaries[task_id] = summary
        return task_id

    def update_status(self, task_id: str, status: str) -> None:
        summary = self.summaries[task_id]
        summary.status = status
        if status in {"success", "failed"}:
            summary.finishedAt = datetime.utcnow()
        self.summaries[task_id] = summary

    def store_result(self, task_id: str, result: BacktestResult) -> None:
        self.tasks[task_id] = result
        summary = result.summary
        self.summaries[task_id] = summary

    def get_summary(self, task_id: str) -> BacktestSummary:
        return self.summaries[task_id]

    def get_result(self, task_id: str) -> BacktestResult:
        if task_id not in self.tasks:
            summary = self.summaries.get(task_id)
            if summary is None:
                raise KeyError(task_id)
            return BacktestResult(summary=summary, metrics={}, equity=[], trades=[], logs=[])
        return self.tasks[task_id]

    def list_summaries(self) -> List[BacktestSummary]:
        return sorted(self.summaries.values(), key=lambda s: s.startedAt, reverse=True)


tasks = TaskState()


def get_dataset_path(dataset_id: str) -> Path:
    """Resolve dataset id to actual path."""
    if dataset_id.startswith("bundle:"):
        # Entire directory
        folder = dataset_id.split(":", 1)[1]
        return (DATA_DIR / folder).resolve()
    path = (DATA_DIR / dataset_id).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")
    return path


def read_dataset_metadata(path: Path) -> DatasetInfo:
    if path.is_dir():
        csv_files = sorted(path.glob("*.csv"))
        symbols: List[str] = []
        rows = 0
        start: Optional[datetime] = None
        end: Optional[datetime] = None
        for csv_file in csv_files:
            spec = DataSpec(path=csv_file)
            bars = load_csv(spec)
            if not bars:
                continue
            symbols.append(csv_file.stem.upper())
            rows += len(bars)
            start = min(start, bars[0].dt) if start else bars[0].dt
            end = max(end, bars[-1].dt) if end else bars[-1].dt
        return DatasetInfo(
            id=f"bundle:{path.name}",
            name=path.name,
            path=str(path),
            symbols=symbols,
            rows=rows,
            start=start,
            end=end,
        )

    spec = DataSpec(path=path)
    bars = load_csv(spec)
    symbols = [path.stem.upper()]
    start = bars[0].dt if bars else None
    end = bars[-1].dt if bars else None
    return DatasetInfo(
        id=path.name,
        name=path.stem,
        path=str(path),
        symbols=symbols,
        rows=len(bars),
        start=start,
        end=end,
    )


def list_available_datasets() -> List[DatasetInfo]:
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    datasets: List[DatasetInfo] = []
    root_file_infos: List[DatasetInfo] = []
    for item in DATA_DIR.iterdir():
        if item.is_file() and item.suffix.lower() == ".csv":
            info = read_dataset_metadata(item)
            datasets.append(info)
            root_file_infos.append(info)
        elif item.is_dir():
            csv_count = len(list(item.glob("*.csv")))
            if csv_count:
                datasets.append(read_dataset_metadata(item))
    if root_file_infos:
        start_candidates = [info.start for info in root_file_infos if info.start]
        end_candidates = [info.end for info in root_file_infos if info.end]
        datasets.append(
            DatasetInfo(
                id="bundle:root",
                name="All CSVs",
                path=str(DATA_DIR.resolve()),
                symbols=[info.name.upper() for info in root_file_infos],
                rows=sum(info.rows for info in root_file_infos),
                start=min(start_candidates) if start_candidates else None,
                end=max(end_candidates) if end_candidates else None,
            )
        )
    # Provide synthetic dataset entry
    datasets.append(
        DatasetInfo(
            id="synthetic",
            name="Synthetic",
            path="synthetic",
            symbols=["SYN"],
            rows=500,
            start=datetime(2020, 1, 1),
            end=datetime(2021, 5, 15),
        )
    )
    return datasets


def load_dataset(dataset_id: str) -> Dict[str, List[Bar]] | List[Bar]:
    if dataset_id == "synthetic":
        return generate_synthetic(days=500)
    path = get_dataset_path(dataset_id)
    if path.is_dir():
        data: Dict[str, List[Bar]] = {}
        for csv_file in path.glob("*.csv"):
            bars = load_csv(DataSpec(path=csv_file))
            if bars:
                data[csv_file.stem.upper()] = bars
        if not data:
            raise HTTPException(status_code=400, detail="Dataset directory has no CSV files")
        return data
    return load_csv(DataSpec(path=path))


def build_strategy(cfg: StrategyConfig) -> Strategy:
    params = cfg.params
    stype = cfg.type.lower()
    if stype == "sma":
        return SmaCrossStrategy(
            fast=int(params.get("fast", 10)),
            slow=int(params.get("slow", 30)),
            allow_short=bool(params.get("allow_short", False))
        )
    if stype == "breakout":
        return DonchianBreakout(
            symbol=str(params.get("symbol", "SYMBOL")),
            lookback=int(params.get("lookback", 20)),
            qty=int(params.get("qty", 1)),
            allow_short=bool(params.get("allow_short", True)),
        )
    if stype == "weighted":
        return SmaTrendWeightStrategy(
            symbol=str(params.get("symbol", "SYMBOL")),
            fast=int(params.get("fast", 10)),
            slow=int(params.get("slow", 30)),
            long_weight=float(params.get("long_weight", 0.5)),
            short_weight=float(params.get("short_weight", 0.0)),
            neutral_weight=float(params.get("neutral_weight", 0.0)),
        )
    raise HTTPException(status_code=400, detail=f"Unsupported strategy type: {cfg.type}")


def run_backtest_task(task_id: str, request: BacktestRequest) -> None:
    summary = tasks.get_summary(task_id)
    tasks.update_status(task_id, "running")
    logs: List[str] = [f"Task {task_id} started at {datetime.utcnow().isoformat()}"]
    try:
        raw_dataset = load_dataset(request.datasetId)
        strategy_configs = [strategy_store.get(sid) for sid in request.strategyIds]
        strategies = [build_strategy(cfg) for cfg in strategy_configs]

        broker = SimBroker(
            slippage_bps=request.slipBps,
            commission_per_share=request.commission,
            commission_rate=request.commissionRate,
            volume_limit_pct=request.volumeLimit,
        )

        if isinstance(raw_dataset, list):
            if not strategies:
                raise HTTPException(status_code=400, detail="No strategy selected")
            strat = strategies[0]
            portfolio = Portfolio(initial_cash=request.cash)
            result = run_single_backtest(raw_dataset, strat, portfolio=portfolio, broker=broker)
        else:
            strat_map: Dict[str, Strategy] = {}
            symbols = list(raw_dataset.keys())
            for idx, strat in enumerate(strategies):
                symbol = getattr(strat, "symbol", None)
                if symbol and symbol in raw_dataset:
                    strat_map[symbol] = strat
                else:
                    target_symbol = symbols[idx % len(symbols)]
                    strat_map[target_symbol] = strat
            # Fill missing symbols with first strategy clone
            if not strat_map:
                symbol = symbols[0]
                strat_map[symbol] = strategies[0]

            risk_cfg = RiskConfig(max_units_per_symbol=request.risk.maxUnits, stop_loss_pct=request.risk.stopLossPct)
            risk_manager = RiskManager(risk_cfg)
            allocator = None
            if request.allocator:
                allocator = WeightAllocator(
                    max_leverage=request.allocator.maxLeverage,
                    lot_size=request.allocator.lotSize,
                    rounding=request.allocator.rounding,
                )
            portfolio = MultiPortfolio(initial_cash=request.cash)
            result = run_backtest_multi(
                raw_dataset,
                strat_map,
                portfolio=portfolio,
                broker=broker,
                risk=risk_manager,
                allocator=allocator,
            )

        equity_points = [
            {"dt": dt, "equity": eq}
            for dt, eq in result.equity_curve
        ]
        summary = BacktestSummary(
            id=task_id,
            name=summary.name,
            status="success",
            startedAt=summary.startedAt,
            finishedAt=datetime.utcnow(),
            totalReturn=result.metrics.get("total_return"),
            sharpe=result.metrics.get("sharpe"),
            maxDrawdown=result.metrics.get("max_drawdown"),
        )

        trade_records: List[TradeRecord] = []
        for tr in result.trades:
            trade_records.append(
                TradeRecord(
                    symbol=str(tr.get("symbol", "")),
                    side=str(tr.get("side", "")),
                    qty=int(tr.get("qty", 0)),
                    entry_dt=str(tr.get("entry_dt", "")),
                    exit_dt=str(tr.get("exit_dt", "")),
                    pnl=float(tr.get("pnl", 0.0)),
                    ret=tr.get("ret"),
                    tag=tr.get("tag"),
                )
            )

        backtest_result = BacktestResult(
            summary=summary,
            metrics=result.metrics,
            equity=[EquityPoint(**pt) for pt in equity_points],
            trades=trade_records,
            logs=logs,
        )
        logs.append(f"Task {task_id} finished successfully")
        tasks.store_result(task_id, backtest_result)
    except Exception as exc:  # noqa: BLE001
        summary.status = "failed"
        summary.finishedAt = datetime.utcnow()
        tasks.summaries[task_id] = summary
        logs.append(f"Error: {exc}")
        failure_result = BacktestResult(
            summary=summary,
            metrics={},
            equity=[],
            trades=[],
            logs=logs,
        )
        tasks.tasks[task_id] = failure_result
    finally:
        tasks.update_status(task_id, tasks.get_summary(task_id).status)


@app.get("/api/datasets", response_model=List[DatasetInfo])
def api_list_datasets() -> List[DatasetInfo]:
    return list_available_datasets()


@app.post("/api/datasets", response_model=DatasetInfo)
def api_upload_dataset(file: UploadFile = File(...)) -> DatasetInfo:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Missing filename")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / file.filename
    content = file.file.read()
    target.write_bytes(content)
    return read_dataset_metadata(target)


@app.delete("/api/datasets/{dataset_id}")
def api_delete_dataset(dataset_id: str) -> None:
    path = (DATA_DIR / dataset_id)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Dataset not found")
    path.unlink()


@app.get("/api/strategies", response_model=List[StrategyConfig])
def api_list_strategies() -> List[StrategyConfig]:
    return strategy_store.list()


@app.post("/api/strategies", response_model=StrategyConfig)
def api_upsert_strategy(payload: StrategyPayload) -> StrategyConfig:
    return strategy_store.upsert(payload)


@app.post("/api/backtests", response_model=BacktestResponse)
def api_launch_backtest(request: BacktestRequest, background_tasks: BackgroundTasks) -> BacktestResponse:
    if not request.strategyIds:
        raise HTTPException(status_code=400, detail="strategyIds cannot be empty")
    name = f"{request.datasetId} / {', '.join(request.strategyIds)}"
    task_id = tasks.create(name)
    background_tasks.add_task(run_backtest_task, task_id, request)
    return BacktestResponse(task_id=task_id)


@app.get("/api/backtests", response_model=List[BacktestSummary])
def api_list_backtests() -> List[BacktestSummary]:
    return tasks.list_summaries()


@app.get("/api/backtests/{task_id}", response_model=BacktestResult)
def api_get_backtest(task_id: str) -> BacktestResult:
    try:
        return tasks.get_result(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")


@app.get("/api/backtests/{task_id}/download")
def api_download_artifact(task_id: str, type: str) -> FileResponse:
    result = tasks.get_result(task_id)
    if result.summary.status != "success":
        raise HTTPException(status_code=400, detail="Backtest not completed")
    folder = Path(".artifacts")
    folder.mkdir(exist_ok=True)
    if type == "metrics":
        target = folder / f"{task_id}-metrics.json"
        target.write_text(json.dumps(result.metrics, indent=2), encoding="utf-8")
    elif type == "equity":
        target = folder / f"{task_id}-equity.csv"
        with target.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["dt", "equity"])
            for point in result.equity:
                writer.writerow([point.dt, f"{point.equity:.6f}"])
    elif type == "trades":
        target = folder / f"{task_id}-trades.csv"
        with target.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["symbol", "side", "qty", "entry_dt", "exit_dt", "pnl", "ret", "tag"])
            for trade in result.trades:
                writer.writerow([
                    trade.symbol,
                    trade.side,
                    trade.qty,
                    trade.entry_dt,
                    trade.exit_dt,
                    f"{trade.pnl:.6f}",
                    f"{(trade.ret or 0.0):.6f}",
                    trade.tag or "",
                ])
    else:
        raise HTTPException(status_code=400, detail="Invalid artifact type")
    return FileResponse(target)
