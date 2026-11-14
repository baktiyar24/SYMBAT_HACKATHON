from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas import Envelope, Overview, CampaignAnalytics, RpiOut, WaiOut
from services import metrics

router = APIRouter(tags=['Аналитика'])


def period(date_from: date | None = None, date_to: date | None = None, scenario: Literal['before', 'after'] = 'after'):
    return (*metrics.resolve_period(date_from, date_to, scenario), scenario)


@router.get('/analytics/overview', response_model=Envelope[Overview])
def overview(campaign_id: str | None = None, dates=Depends(period), db: Session = Depends(get_db)):
    return {'data': metrics.overview(db, dates[0], dates[1], campaign_id, dates[2])}


@router.get('/analytics/campaigns', response_model=Envelope[list[CampaignAnalytics]])
def campaigns(campaign_id: str | None = None, dates=Depends(period), db: Session = Depends(get_db)):
    return {'data': metrics.campaign_analytics(db, dates[0], dates[1], campaign_id, dates[2])}


@router.get('/analytics/rpi', response_model=Envelope[RpiOut])
def rpi(campaign_id: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db)):
    return {'data': metrics.rpi_analytics(db, *metrics.resolve_period(date_from, date_to), campaign_id)}


@router.get('/analytics/wai', response_model=Envelope[WaiOut])
def wai(campaign_id: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db)):
    return {'data': metrics.wai_analytics(db, *metrics.resolve_period(date_from, date_to), campaign_id)}
