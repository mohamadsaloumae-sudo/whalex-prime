from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from db.database import get_session, User, hash_password, verify_password
from core.config import get_settings
import uuid

router = APIRouter(prefix="/api/auth", tags=["Auth"])
security = HTTPBearer(auto_error=False)

def create_token(user_id: str, tier: str) -> str:
    s = get_settings()
    payload = {"sub": user_id, "tier": tier, "exp": datetime.utcnow() + timedelta(days=30)}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    s = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, s.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(401, "Invalid token")

def require_pro(user=Depends(get_current_user)):
    if user.get("tier") not in ("pro", "admin"):
        raise HTTPException(403, "PRO subscription required")
    return user

def require_admin(user=Depends(get_current_user)):
    if user.get("tier") != "admin":
        raise HTTPException(403, "Admin access required")
    return user

class RegisterBody(BaseModel):
    username: str
    password: str
    email: str = ""

class LoginBody(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(body: RegisterBody):
    db = get_session()
    try:
        if db.query(User).filter(User.username == body.username).first():
            raise HTTPException(400, "Username already exists")
        user = User(
            username=body.username,
            email=body.email or None,
            password_hash=hash_password(body.password),
            tier="free",
        )
        db.add(user); db.commit(); db.refresh(user)
        token = create_token(user.id, user.tier)
        return {"access_token": token, "tier": user.tier, "uid": user.id}
    finally:
        db.close()

@router.post("/login")
def login(body: LoginBody):
    db = get_session()
    try:
        user = db.query(User).filter(User.username == body.username).first()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Invalid credentials")
        token = create_token(user.id, user.tier)
        return {"access_token": token, "tier": user.tier, "uid": user.id, "username": user.username}
    finally:
        db.close()

@router.post("/guest")
def guest():
    uid = str(uuid.uuid4())
    token = create_token(uid, "free")
    return {"access_token": token, "tier": "free", "uid": uid}

@router.get("/me")
def me(user=Depends(get_current_user)):
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        if not u:
            return {"uid": user["sub"], "tier": user["tier"], "username": "Guest"}
        return {"uid": u.id, "tier": u.tier, "username": u.username, "demo_balance": u.demo_balance}
    finally:
        db.close()
