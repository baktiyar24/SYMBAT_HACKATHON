from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db, get_write_db
from models import Discount
from schemas import Envelope, DiscountOut, DiscountPatch
import crud

router = APIRouter(tags=['Акции'])


@router.get('/discounts', response_model=Envelope[list[DiscountOut]])
def discounts(include_all: bool = False, product_id: str | None = None, pharmacy_id: str | None = None, db: Session = Depends(get_db)):
    query = select(Discount).order_by(Discount.id)
    if product_id:
        query = query.where(Discount.product_id == product_id)
    if pharmacy_id:
        query = query.where(Discount.pharmacy_id == pharmacy_id)
    return {'data': [crud.discount_view(db, d) for d in db.scalars(query) if include_all or crud.discount_valid(d)]}


@router.patch('/discounts/{discount_id}', response_model=Envelope[DiscountOut], dependencies=[Depends(crud.require_demo)])
def edit_discount(discount_id: str, body: DiscountPatch, db: Session = Depends(get_write_db, scope='function')):
    return {'data': crud.patch_discount(db, discount_id, body)}
