from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db, get_write_db
from schemas import Envelope, AdOut, ImpressionIn, ImpressionOut, ClickIn, ClickOut
from services.ranking import recommend_ads
import crud

router = APIRouter(tags=['Реклама и события'])


@router.get('/ads/recommendations', response_model=Envelope[list[AdOut]])
def ads(q: str = Query('', max_length=200), campaign_id: str | None = None,
        pharmacy_id: str | None = None, smart: bool = True, db: Session = Depends(get_db)):
    return {'data': recommend_ads(db, q, campaign_id, pharmacy_id, smart)}


@router.post('/ads/impression', response_model=Envelope[ImpressionOut], dependencies=[Depends(crud.require_demo)])
def impression(body: ImpressionIn, db: Session = Depends(get_write_db, scope='function')):
    return {'data': crud.record_impression(db, body)}


@router.post('/ads/click', response_model=Envelope[ClickOut], dependencies=[Depends(crud.require_demo)])
def click(body: ClickIn, db: Session = Depends(get_write_db, scope='function')):
    return {'data': crud.record_click(db, body)}
