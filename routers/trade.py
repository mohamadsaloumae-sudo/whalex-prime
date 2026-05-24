from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.database import get_session, Trade, User
from routers.auth import get_current_user
from core.config import get_settings

router = APIRouter(prefix="/api/trade", tags=["Trade"])

class TradeBody(BaseModel):
    symbol: str
    direction: str
    amount: float
    leverage: int = 1
    sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    chain: str = "sol"
    trade_type: str = "futures"
    account_type: str = "demo"
    entry_price: Optional[float] = None

@router.post("/execute")
def execute_trade(body: TradeBody, user=Depends(get_current_user)):
    s = get_settings()
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        gas = round(body.amount * s.gas_fee_pct, 4)
        total = body.amount + gas

        if body.account_type == "demo":
            if u and u.demo_balance < total:
                raise HTTPException(400, "Insufficient demo balance")
            if u:
                u.demo_balance -= total
                db.commit()
        
        trade = Trade(
            user_id=user["sub"],
            symbol=body.symbol,
            direction=body.direction.upper(),
            trade_type=body.trade_type,
            account_type=body.account_type,
            entry_price=body.entry_price or 0,
            amount=body.amount,
            leverage=body.leverage,
            sl=body.sl,
            tp1=body.tp1,
            tp2=body.tp2,
            tp3=body.tp3,
            gas_fee=gas,
            chain=body.chain,
        )
        db.add(trade); db.commit(); db.refresh(trade)
        return {"status": "executed", "trade_id": trade.id, "gas_fee": gas, "total": total}
    finally:
        db.close()

@router.post("/close/{trade_id}")
def close_trade(trade_id: str, close_price: float, user=Depends(get_current_user)):
    db = get_session()
    try:
        trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == user["sub"]).first()
        if not trade:
            raise HTTPException(404, "Trade not found")
        if trade.status != "open":
            raise HTTPException(400, "Trade already closed")
        
        if trade.direction == "LONG":
            pnl = (close_price - trade.entry_price) / trade.entry_price * trade.amount * trade.leverage
        else:
            pnl = (trade.entry_price - close_price) / trade.entry_price * trade.amount * trade.leverage
        
        trade.close_price = close_price
        trade.pnl = round(pnl, 4)
        trade.status = "closed"
        trade.closed_at = datetime.utcnow()
        
        if trade.account_type == "demo":
            u = db.query(User).filter(User.id == user["sub"]).first()
            if u:
                u.demo_balance += trade.amount + pnl
                db.commit()
        
        db.commit()
        return {"status": "closed", "pnl": pnl}
    finally:
        db.close()

@router.get("/history")
def trade_history(user=Depends(get_current_user)):
    db = get_session()
    try:
        trades = db.query(Trade).filter(Trade.user_id == user["sub"]).order_by(Trade.opened_at.desc()).limit(50).all()
        return {"trades": [{
            "id": t.id, "symbol": t.symbol, "direction": t.direction,
            "trade_type": t.trade_type, "account_type": t.account_type,
            "amount": t.amount, "leverage": t.leverage, "entry_price": t.entry_price,
            "close_price": t.close_price, "pnl": t.pnl, "status": t.status,
            "gas_fee": t.gas_fee, "opened_at": str(t.opened_at),
        } for t in trades]}
    finally:
        db.close()

@router.get("/stats")
def trade_stats(user=Depends(get_current_user)):
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        trades = db.query(Trade).filter(Trade.user_id == user["sub"], Trade.status == "closed").all()
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in trades)
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        return {
            "demo_balance": u.demo_balance if u else 10000,
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
        }
    finally:
        db.close()
