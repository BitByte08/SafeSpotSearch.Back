import os

from fastapi import FastAPI, Depends, Request, Form, Response, status, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from itsdangerous import URLSafeSerializer
from starlette.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

from database import SessionLocal
from models import User  # <- 누락 주의
from router import location

from database import engine
from models import User, Base  # User 모델과 Base 가져와야 함


app = FastAPI()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
serializer = URLSafeSerializer(SECRET_KEY)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(location.router, prefix="/location", tags=["Location"])

# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 비밀번호 해시
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# 회원가입
@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "이미 존재하는 사용자명입니다."})
    new_user = User(username=username, hashed_password=hash_password(password))
    db.add(new_user)
    db.commit()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

# 로그인
@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(
    response: Response,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "로그인 실패"})
    token = serializer.dumps({"user_id": user.id})
    response = RedirectResponse("https://sss.bitworkspace.kr", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("session_token", token)
    return response
