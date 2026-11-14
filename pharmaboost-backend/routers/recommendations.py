from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas import Envelope, RecommendationOut
from services.optimization import recommendations as build_recommendations
from routers.analytics import period

router = APIRouter(tags=['Рекомендации'])


@router.get('/recommendations', response_model=Envelope[list[RecommendationOut]])
def recommendations(campaign_id: str | None = None, dates=Depends(period), db: Session = Depends(get_db)):
    return {'data': build_recommendations(db, dates[0], dates[1], campaign_id)}
