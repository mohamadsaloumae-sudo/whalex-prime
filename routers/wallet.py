from fastapi import APIRouter, Depends
from pydantic import BaseModel
from routers.auth import get_current_user
import secrets, hashlib

router = APIRouter(prefix="/api/wallet", tags=["Wallet"])

WORDLIST = [
    "abandon","ability","able","about","above","absent","absorb","abstract","absurd","abuse",
    "access","accident","account","accuse","achieve","acid","acoustic","acquire","across","act",
    "action","actor","actress","actual","adapt","add","addict","address","adjust","admit",
    "adult","advance","advice","aerobic","afford","afraid","again","age","agent","agree",
    "ahead","aim","air","airport","aisle","alarm","album","alcohol","alert","alien",
    "all","alley","allow","almost","alone","alpha","already","also","alter","always",
    "amateur","amazing","among","amount","amused","analyst","anchor","ancient","anger","angle",
    "angry","animal","ankle","announce","annual","another","answer","antenna","antique","anxiety",
    "any","apart","apology","appear","apple","approve","april","arch","arctic","area",
    "arena","argue","arm","armed","armor","army","around","arrange","arrest","arrive",
    "arrow","art","artefact","artist","artwork","ask","aspect","assault","asset","assist",
    "assume","asthma","athlete","atom","attack","attend","attitude","attract","auction","audit",
    "august","aunt","author","auto","autumn","average","avocado","avoid","awake","aware",
    "away","awesome","awful","awkward","axis","baby","balance","bamboo","banana","banner",
    "barely","bargain","barrel","base","basic","basket","battle","beach","bean","beauty",
    "because","become","beef","begin","behave","behind","believe","below","belt","bench",
]

def generate_seed_phrase(words=12):
    return " ".join(secrets.choice(WORDLIST) for _ in range(words))

def seed_to_address(seed: str, chain: str) -> str:
    h = hashlib.sha256(seed.encode()).hexdigest()
    if chain == "sol":
        return h[:32].upper() + "..." + h[32:44]
    elif chain in ("eth", "arb", "base", "bsc", "avax", "poly"):
        return "0x" + h[:40]
    elif chain == "tron":
        return "T" + h[:33].upper()
    elif chain == "btc":
        return "1" + h[:33]
    return h[:44]

class GenerateBody(BaseModel):
    chain: str = "sol"

@router.post("/generate")
def generate_wallet(body: GenerateBody, user=Depends(get_current_user)):
    seed = generate_seed_phrase(12)
    address = seed_to_address(seed, body.chain)
    private_key = hashlib.sha256((seed + body.chain).encode()).hexdigest()
    return {
        "chain": body.chain,
        "address": address,
        "seed_phrase": seed,
        "private_key": "0x" + private_key,
        "warning": "احفظ هذه المعلومات في مكان آمن. لن نتمكن من استرجاعها.",
    }

@router.get("/{chain}/address")
def get_address(chain: str, user=Depends(get_current_user)):
    uid = user["sub"]
    seed = hashlib.sha256((uid + chain).encode()).hexdigest()
    address = seed_to_address(seed, chain)
    return {"chain": chain, "address": address}

@router.get("/chains")
def get_chains():
    return {"chains": [
        {"id": "sol",  "name": "Solana",   "symbol": "SOL",  "color": "#9945ff"},
        {"id": "eth",  "name": "Ethereum", "symbol": "ETH",  "color": "#6288f5"},
        {"id": "bsc",  "name": "BSC",      "symbol": "BNB",  "color": "#f0b90b"},
        {"id": "arb",  "name": "Arbitrum", "symbol": "ARB",  "color": "#12aaff"},
        {"id": "base", "name": "Base",     "symbol": "BASE", "color": "#0052ff"},
        {"id": "avax", "name": "Avalanche","symbol": "AVAX", "color": "#e84142"},
        {"id": "tron", "name": "Tron",     "symbol": "TRX",  "color": "#ff060a"},
        {"id": "btc",  "name": "Bitcoin",  "symbol": "BTC",  "color": "#f7931a"},
        {"id": "poly", "name": "Polygon",  "symbol": "MATIC","color": "#8247e5"},
    ]}
