from fastapi import APIRouter, Query, Depends, Form, Cookie, HTTPException, status, Path
from dotenv import load_dotenv
import os
import math
import requests
from itsdangerous import URLSafeSerializer, BadSignature
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from starlette.requests import Request
from starlette.responses import RedirectResponse

from database import SessionLocal
from models import User, Location  # User, Location ORM 모델 임포트

router = APIRouter()
load_dotenv()
templates = Jinja2Templates(directory="templates")

EARTH_RADIUS = 6371000  # meters
METER = 5000

# 시크릿 키로 serializer 생성
SECRET_KEY = os.getenv("SECRET_KEY")
serializer = URLSafeSerializer(SECRET_KEY)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def meter_to_lat(delta_m):
    return (delta_m / EARTH_RADIUS) * (180 / math.pi)

def meter_to_lon(delta_m, lat):
    return (delta_m / (EARTH_RADIUS * math.cos(math.radians(lat)))) * (180 / math.pi)

def haversine(lat1, lon1, lat2, lon2):
    R = EARTH_RADIUS
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@router.get("/around")
def get_range_around(
    latitude: float = Query(..., description="중심 위도"),
    longitude: float = Query(..., description="중심 경도"),
    radius: int = Query(METER, description="검색 반경 (미터 단위, 기본 5000m)")
):
    lat_offset = meter_to_lat(METER)
    lon_offset = meter_to_lon(METER, latitude)
    url = "https://www.safetydata.go.kr/V2/api/DSSP-IF-10944"
    serviceKey = os.getenv("SERVICE_KEY")
    payloads = {
        "serviceKey": serviceKey,
        "returnType": "json",
        "pageNo": "1",
        "numOfRows": "5",
        "startLot": round(longitude - lon_offset, 7),
        "endLot": round(longitude + lon_offset, 7),
        "startLat": round(latitude - lat_offset, 7),
        "endLat": round(latitude + lat_offset, 7),
    }

    res = requests.get(url, params=payloads)
    res.raise_for_status()
    data = res.json()

    shelters_raw = data.get("body", [])
    if not shelters_raw:
        return {
            "center": {"lat": latitude, "lon": longitude, "radius": radius},
            "shelters": []
        }

    shelters = []
    for shelter in shelters_raw:
        lat_s = float(shelter.get("LA", 0))
        lon_s = float(shelter.get("LO", 0))
        dist = haversine(latitude, longitude, lat_s, lon_s)
        if dist <= radius:
            shelters.append({
                "name": shelter.get("SHNT_PLACE_NM", "이름 없음"),
                "address": shelter.get("SHNT_PLACE_DTL_POSITION", "주소 없음"),
                "lat": lat_s,
                "lon": lon_s,
            })

    return {
        "center": {
            "lat": latitude,
            "lon": longitude,
            "radius": radius
        },
        "shelters": shelters
    }

# 로그인된 사용자 확인
def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    try:
        data = serializer.loads(session_token)
        user = db.query(User).filter(User.id == data["user_id"]).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자가 존재하지 않습니다.")
        return user
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 세션입니다.")

@router.post("/save_location")
def save_location(
    latitude: float = Form(...),
    longitude: float = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    location = Location(
        user_id=user.id,
        latitude=latitude,
        longitude=longitude,
        description=description,
    )
    db.add(location)
    db.commit()
    db.refresh(location)

    return {
        "message": "위치가 성공적으로 저장되었습니다.",
        "location_id": location.id,
        "user_id": user.id,
        "latitude": latitude,
        "longitude": longitude,
        "description": description
    }
@router.get("/get_locations")
def get_locations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    locations = db.query(Location).filter(Location.user_id == user.id).all()
    return [
        {
            "id": loc.id,
            "lat": loc.latitude,
            "lon": loc.longitude,
            "description": loc.description,
        }
        for loc in locations
    ]
@router.delete("/delete_location/{location_id}")
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.user_id == user.id
    ).first()

    if not location:
        raise HTTPException(status_code=404, detail="위치를 찾을 수 없습니다.")

    db.delete(location)
    db.commit()
    return {"message": "삭제 완료", "location_id": location_id}



@router.get("/update_description/{location_id}")
def show_update_form(
    request: Request,
    location_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.user_id == user.id
    ).first()

    if not location:
        raise HTTPException(status_code=404, detail="위치를 찾을 수 없습니다.")

    return templates.TemplateResponse("update_description.html", {
        "request": request,
        "location": location
    })
@router.post("/update_description/{location_id}")
def update_location_description(
    location_id: int = Path(...),
    new_description: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.user_id == user.id
    ).first()

    if not location:
        raise HTTPException(status_code=404, detail="위치를 찾을 수 없습니다.")

    location.description = new_description
    db.commit()
    db.refresh(location)

    return RedirectResponse("http://localhost:3000/", status_code=status.HTTP_303_SEE_OTHER)