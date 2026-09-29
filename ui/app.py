import os
from typing import Optional
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core.config import config, DEFAULT_ASSETS
from core.coordinator import coordinator
from core.data_loader import load_market_data
from core.live_stream import live_streamer
from learning.calibrator import calibrator
from learning.movement_model import get_or_create_model
from learning.journal_learner import JournalLearner
from learning.auto_trainer import auto_trainer
from execution.paper_broker import paper_broker
from execution.journal import journal_db
from screener.apex_screener import ApexPredatorScreener
from risk.news_manager import news_manager

app = FastAPI(title=config.app_name, version=config.version)

@app.on_event("startup")
async def startup_event():
    # Start live market background polling and streaming
    live_streamer.start(poll_interval_sec=3.0)
    # Start autonomous continuous learning engine (background daemon)
    auto_trainer.start(poll_interval_sec=60.0)

@app.on_event("shutdown")
async def shutdown_event():
    auto_trainer.stop()
    live_streamer.stop()

# Static and templates paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

class TradeRequest(BaseModel):
    symbol: str
    action: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    position_size: float
    pattern: str

class CalibrateRequest(BaseModel):
    symbol: str
    timeframe: str = "15m"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "assets": DEFAULT_ASSETS,
            "default_symbol": config.default_symbol,
            "risk_config": config.risk
        }
    )

@app.get("/api/analysis")
async def get_analysis(symbol: str = "EURUSD=X", timeframe: str = "15m", capital: float = 10000.0, risk_pct: float = 0.0025):
    try:
        data = coordinator.analyze_asset(symbol=symbol, timeframe=timeframe, capital=capital, risk_pct=risk_pct)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/calibrate")
async def calibrate_asset(req: CalibrateRequest):
    try:
        df = load_market_data(req.symbol, req.timeframe, force_refresh=True)
        new_params = calibrator.calibrate_symbol(df, req.symbol)
        # Train movement model as well
        model = get_or_create_model(req.symbol)
        train_res = model.train(df, epochs=20)
        return JSONResponse(content={
            "status": "success",
            "calibration": new_params.model_dump(),
            "model_training": train_res
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/screener")
async def get_screener():
    try:
        results = ApexPredatorScreener.scan_market()
        return JSONResponse(content={"items": results})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/broker")
async def get_broker_status():
    try:
        summary = paper_broker.get_summary()
        return JSONResponse(content=summary)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/execute-trade")
async def execute_trade(req: TradeRequest):
    try:
        from core.models import TradeSignal, ActionType, PatternType
        sig = TradeSignal(
            symbol=req.symbol,
            timestamp="Live Execution",
            action=ActionType(req.action),
            pattern=PatternType(req.pattern) if req.pattern in [p.value for p in PatternType] else PatternType.ABCD,
            entry_price=req.entry_price,
            stop_loss=req.stop_loss,
            target_1=req.target_1,
            target_2=req.target_2,
            risk_per_trade_usd=abs(req.entry_price - req.stop_loss) * req.position_size,
            position_size=req.position_size,
            units_label="Units",
            confidence=0.85,
            payout_ratio=round(abs(req.target_1 - req.entry_price) / max(1e-5, abs(req.entry_price - req.stop_loss)), 2),
            rationale="Executed via Web Dashboard"
        )
        pos = paper_broker.open_position_from_signal(sig)
        if pos:
            return JSONResponse(content={"status": "opened", "position": pos.model_dump()})
        else:
            return JSONResponse(status_code=400, content={"status": "rejected", "reason": paper_broker.circuit_breaker.halt_reason or "Risk filter rejected"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await live_streamer.connect(websocket)
    try:
        while True:
            # Keep alive and listen for client commands (e.g. switch symbol)
            data = await websocket.receive_text()
            if data.startswith("SUBSCRIBE:"):
                parts = data.split(":")
                sym = parts[1]
                tf = parts[2] if len(parts) > 2 else "15m"
                live_streamer.set_active_symbol(sym, tf)
    except WebSocketDisconnect:
        live_streamer.disconnect(websocket)
    except Exception:
        live_streamer.disconnect(websocket)

class ActiveSymbolRequest(BaseModel):
    symbol: str
    timeframe: str = "15m"

@app.post("/api/set-active-symbol")
async def set_active_symbol_endpoint(req: ActiveSymbolRequest):
    live_streamer.set_active_symbol(req.symbol, req.timeframe)
    return JSONResponse(content={"status": "ok", "active_symbol": req.symbol})

@app.get("/api/journal")
async def get_journal():
    try:
        trades = journal_db.get_all_trades()
        analysis = JournalLearner.analyze_journal(trades)
        return JSONResponse(content={
            "trades": [t.model_dump() for t in trades],
            "analysis": analysis
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

class AutoTrainerToggleRequest(BaseModel):
    enabled: bool

class AutoTrainerTrainRequest(BaseModel):
    symbol: Optional[str] = None
    force: bool = True

@app.get("/api/auto-trainer/status")
async def get_auto_trainer_status():
    try:
        status = auto_trainer.get_status()
        return JSONResponse(content=status)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/auto-trainer/toggle")
async def toggle_auto_trainer(req: AutoTrainerToggleRequest):
    try:
        auto_trainer.set_enabled(req.enabled)
        return JSONResponse(content={"status": "ok", "enabled": auto_trainer.enabled})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/auto-trainer/train-now")
async def train_now_endpoint(req: AutoTrainerTrainRequest):
    try:
        if not req.symbol or req.symbol.upper() == "ALL":
            auto_trainer.train_all_assets_async(force=req.force)
            return JSONResponse(content={"status": "started", "target": "ALL", "message": "Autonomous background training initiated for all watched assets"})
        else:
            import threading
            threading.Thread(
                target=auto_trainer.train_symbol,
                args=(req.symbol, req.force),
                daemon=True,
                name=f"ManualTrain-{req.symbol}"
            ).start()
            return JSONResponse(content={"status": "started", "target": req.symbol, "message": f"Autonomous background training initiated for {req.symbol}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

class NewsToggleRequest(BaseModel):
    enabled: bool

class NewsSimulateRequest(BaseModel):
    action: str = "start"  # "start" or "clear"
    title: str = "US Non-Farm Payrolls (NFP) Shock"
    duration_minutes: int = 15
    currency: str = "USD"

@app.get("/api/news/status")
async def get_news_status(symbol: str = "EURUSD=X"):
    try:
        asset_meta = DEFAULT_ASSETS.get(symbol, DEFAULT_ASSETS["EURUSD=X"])
        status = news_manager.get_status(symbol, asset_meta.asset_type)
        return JSONResponse(content=status)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/news/toggle")
async def toggle_news_lockout(req: NewsToggleRequest):
    try:
        news_manager.set_lockout_enabled(req.enabled)
        return JSONResponse(content={"status": "ok", "lockout_enabled": news_manager.lockout_enabled})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/news/simulate")
async def simulate_news_endpoint(req: NewsSimulateRequest):
    try:
        if req.action == "clear":
            news_manager.clear_simulated_event()
            return JSONResponse(content={"status": "cleared", "message": "Simulated news blackout cleared."})
        else:
            event = news_manager.simulate_news_event(
                title=req.title,
                duration_minutes=req.duration_minutes,
                currency=req.currency
            )
            return JSONResponse(content={"status": "active", "event": event})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


