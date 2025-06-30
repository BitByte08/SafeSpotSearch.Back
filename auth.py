from fastapi import APIRouter, Request, Form, Depends, Response, status, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from itsdangerous import URLSafeSerializer
from models import User
from database import SessionLocal

router = APIRouter()
templates = Jinja2Templates(directory="templates")
serializer = URLSafeSerializer("SECRET_KEY")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

@router.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("register.html", {"request": {}, "error": "이미 존재하는 사용자명입니다."})
    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": {}, "error": "로그인 실패"})
    token = serializer.dumps({"user_id": user.id})
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_token", value=token, httponly=True)
    return response

def get_current_user(session_token: str = Cookie(None), db: Session = Depends(get_db)) -> User:
    if not session_token:
        raise HTTPException(status_code=401, detail="로그인 필요")
    try:
        user_id = serializer.loads(session_token).get("user_id")
    except:
        raise HTTPException(status_code=401, detail="세션 오류")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자 없음")
    return user
