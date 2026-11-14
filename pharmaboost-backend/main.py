import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from database import Base, engine, get_db, iso, utcnow
from crud import demo_enabled
from schemas import Envelope, Health, ErrorResponse
from routers import products, discounts, ads, orders, analytics, recommendations

DEFAULT_ORIGINS = [f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in (5500, 8001, 8080, 4173)]


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if os.getenv('AUTO_SEED', 'true').lower() == 'true':
        from seed import seed_database
        seed_database()
    yield
    engine.dispose()


def create_app(initialize: bool = True) -> FastAPI:
    app = FastAPI(title='PharmaBoost AI', version='1.0.0', lifespan=lifespan if initialize else None,
                  description='Демонстрационный AdTech-модуль SIMB-AD. Все заказы тестовые. RPI и WAI экспериментальны.',
                  responses={status: {'model': ErrorResponse} for status in (400,403,404,409,410,422,503)})
    app.add_middleware(CORSMiddleware,
                       allow_origins=[s.strip() for s in os.getenv('CORS_ORIGINS', ','.join(DEFAULT_ORIGINS)).split(',') if s.strip()],
                       allow_credentials=False, allow_methods=['GET','POST','PATCH','OPTIONS'],
                       allow_headers=['Content-Type','Accept'])

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {'code': 'HTTP_ERROR', 'message': str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={'error': {**detail, 'details': detail.get('details', {})}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        errors = [{'loc': list(e['loc']), 'message': e['msg'], 'type': e['type']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'error': {'code': 'VALIDATION_ERROR', 'message': 'Некорректные параметры запроса', 'details': errors}})

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(status_code=409, content={'error': {'code': 'INTEGRITY_CONFLICT', 'message': 'Нарушено ограничение целостности или уникальности', 'details': {}}})

    @app.exception_handler(OperationalError)
    async def database_error(request, exc):
        logging.getLogger('pharmaboost').exception('Database operation failed')
        return JSONResponse(status_code=503, content={'error': {'code': 'DATABASE_UNAVAILABLE', 'message': 'База данных временно недоступна; повторите запрос с тем же ID', 'details': {}}})

    @app.get('/api/health', response_model=Envelope[Health], tags=['Состояние'])
    def health(db: Session = Depends(get_db)):
        db.execute(text('SELECT 1'))
        return {'data': {'status':'ok', 'database':'sqlite', 'demo_enabled':demo_enabled(), 'time':iso(utcnow())}}

    for router in (products.router, discounts.router, ads.router, orders.router, analytics.router, recommendations.router):
        app.include_router(router, prefix='/api')
    return app


app = create_app()
