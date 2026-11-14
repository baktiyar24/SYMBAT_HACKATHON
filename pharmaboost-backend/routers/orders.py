from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_write_db
from schemas import Envelope, OrderIn, OrderOut, OrderStatusIn
import crud

router = APIRouter(tags=['Тестовые заказы'], dependencies=[Depends(crud.require_demo)])


@router.post('/orders/demo', response_model=Envelope[OrderOut])
def demo_order(body: OrderIn, db: Session = Depends(get_write_db, scope='function')):
    return {'data': crud.create_order(db, body)}


@router.patch('/orders/demo/{order_id}', response_model=Envelope[OrderOut])
def status(order_id: str, body: OrderStatusIn, db: Session = Depends(get_write_db, scope='function')):
    return {'data': crud.change_order_status(db, order_id, body.status)}
