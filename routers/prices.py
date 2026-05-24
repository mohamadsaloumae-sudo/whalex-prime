from fastapi import APIRouter
from services.prices import get_all_prices, get_price

router = APIRouter(prefix="/api/prices", tags=["Prices"])

@router.get("/all")
def all_prices():
    return {"prices": get_all_prices()}

@router.get("/{symbol}")
def symbol_price(symbol: str):
    return {"symbol": symbol, "data": get_price(symbol)}
