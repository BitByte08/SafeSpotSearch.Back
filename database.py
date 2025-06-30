import time
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "mysql+pymysql://user:1234@db:3306/safespot_db?charset=utf8mb4"

# 먼저 엔진 생성 (이건 연결 시도하지 않음)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 연결 재시도 로직
max_tries = 30
for i in range(max_tries):
    try:
        with engine.connect() as conn:
            print("✅ DB 연결 성공")
            break
    except OperationalError:
        print(f"❌ DB 연결 실패... 재시도 중 ({i + 1}/{max_tries})")
        time.sleep(20)
else:
    raise Exception("🚨 DB에 연결할 수 없습니다. 컨테이너가 계속 실패합니다.")

# 연결 성공 후 세션과 Base 설정
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

Base.metadata.create_all(bind=engine)