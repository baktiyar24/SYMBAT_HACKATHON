from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db, get_write_db
from models import Pharmacy, Inventory
from schemas import Envelope, ProductOut, PharmacyOut, InventoryOut, InventoryPatch, ProductPatch
import crud

router = APIRouter(tags=['Каталог и наличие'])


@router.get('/products', response_model=Envelope[list[ProductOut]])
def products(pharmacy_id: str | None = None, category: str | None = None, db: Session = Depends(get_db)):
    return {'data': crud.list_products(db, category=category, pharmacy_id=pharmacy_id)}


@router.get('/products/search', response_model=Envelope[list[ProductOut]])
def search(q: str = Query('', max_length=200), category: str | None = None, pharmacy_id: str | None = None, db: Session = Depends(get_db)):
    aliases = {'Волосы': 'Уход за волосами', 'Защита от солнца': 'Солнцезащитные средства'}
    return {'data': crud.list_products(db, q, aliases.get(category, category), pharmacy_id)}


@router.patch('/products/{product_id}', response_model=Envelope[ProductOut], dependencies=[Depends(crud.require_demo)])
def edit_product(product_id: str, body: ProductPatch, db: Session = Depends(get_write_db, scope='function')):
    return {'data': crud.patch_product_compat(db, product_id, body)}


@router.get('/pharmacies', response_model=Envelope[list[PharmacyOut]])
def pharmacies(db: Session = Depends(get_db)):
    return {'data': [dict(id=p.id, pharmacy_id=p.id, name=p.name, active=p.active) for p in db.scalars(select(Pharmacy).order_by(Pharmacy.id))]}


@router.get('/inventory', response_model=Envelope[list[InventoryOut]])
def inventory(product_id: str | None = None, pharmacy_id: str | None = None, db: Session = Depends(get_db)):
    query = select(Inventory).order_by(Inventory.id)
    if product_id:
        query = query.where(Inventory.product_id == product_id)
    if pharmacy_id:
        query = query.where(Inventory.pharmacy_id == pharmacy_id)
    return {'data': [crud.inventory_view(i) for i in db.scalars(query)]}


@router.patch('/inventory/{inventory_id}', response_model=Envelope[InventoryOut], dependencies=[Depends(crud.require_demo)])
def edit_inventory(inventory_id: str, body: InventoryPatch, db: Session = Depends(get_write_db, scope='function')):
    return {'data': crud.patch_inventory(db, inventory_id, body.stock_quantity)}
