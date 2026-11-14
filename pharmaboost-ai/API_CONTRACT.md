# PharmaBoost AI — предварительный REST API-контракт

Версия 1.0, 14 ноября 2026. Это предложение frontend-команды, пути и форматы согласуются с backend-разработчиком. Единственная точка адаптации — api.js. Backend здесь не реализован.

## Общие правила

- Базовый адрес: http://localhost:8000/api. В config.js URL уже содержит /api; пути адаптера его не повторяют.
- UTF-8 JSON, Accept: application/json. POST/PATCH: Content-Type: application/json.
- Успех: HTTP 200 (или 201 для нового события), оболочка {"data": ...}. Для списков пустой результат — {"data": []}. Не возвращайте 204 для перечисленных методов.
- Ошибка: {"error":{"code":"VALIDATION_ERROR","message":"Понятное описание","details":{}}}. Frontend показывает message, не переключается на mock автоматически.
- ID — непрозрачные строки. UUID генерируются frontend для impression_id, click_id, order_id; сервер обязан проверять и дедуплицировать. product_id, pharmacy_id и campaign_id выдаёт backend.
- Даты: ISO 8601 с часовым поясом. В локальном DEMO часы фиксированы на 2026-11-14T12:00:00+05:00 для повторяемого выступления. API использует своё серверное время.
- Все суммы — KZT (₸). Отображение округлено; расчёты выполняются на неокруглённых значениях. Для production рекомендуется договориться о целых тиынах и адаптировать api.js.
- campaign_id без значения означает агрегат по всем кампаниям; scenario=before|after, по умолчанию after. Период прототипа — 08–14 ноября 2026. Расширение фильтра дат требует нового согласования.
- Отменённые заказы хранятся отдельно; confirmed_purchases их не включает. 0 ≤ покупки ≤ клики ≤ показы в упрощённой модели. relevant_impressions и available_impressions не больше impressions.
- Текущий frontend не отправляет реальных событий: рекламная карточка создаёт явные тестовые события с is_demo=true. Обычный рендер и изменение поиска не создают событий.
- Backend — источник истины для ранжирования, цен, расходов, атрибуции и подтверждений. Настоящие покупки поступают через интеграцию с аптекой. /orders/demo предназначен исключительно для тестовой среды и не списывает деньги.
- В production заранее согласовать видимость (например ≥50% карточки ≥1 секунды), идентичность показа, window атрибуции, срок дедупликации и consent. До этого реальный автотрекинг отключён.
- Никаких API-секретов в браузере. Способ авторизации не включён в предварительный контракт. Перед production необходимо согласовать серверную сессию/токен, права на PATCH и CSRF/CORS.

## Модели

### Product

product_id, pharmacy_id: string; name, brand, category, volume: string; keywords: string[]; price, current_price: number (₸); effective_discount: number (0–90); in_stock, ad_allowed: boolean; discount: Discount; pharmacy: string; shape: bottle | tube | box; color: mint | blue | peach | yellow.

```json
{
  "product_id": "p1",
  "pharmacy_id": "ph1",
  "name": "Шампунь Daily Balance",
  "brand": "BOTANICA",
  "category": "Волосы",
  "keywords": [
    "шампунь",
    "шамп",
    "shampoo",
    "волосы",
    "уход за волосами"
  ],
  "price": 4800,
  "in_stock": true,
  "ad_allowed": true,
  "shape": "bottle",
  "color": "mint",
  "volume": "250 мл",
  "discount": {
    "product_id": "p1",
    "percent": 10,
    "active": true,
    "start_at": "2026-11-01T00:00:00+05:00",
    "end_at": "2026-12-01T00:00:00+05:00"
  },
  "effective_discount": 10,
  "current_price": 4320,
  "pharmacy": "Аптека Green"
}
```

### Pharmacy

pharmacy_id: string; name: string. В Product передаётся также отображаемое имя pharmacy.

```json
{
  "pharmacy_id": "ph1",
  "name": "Аптека Green"
}
```

### Discount

product_id: string; percent: number, 0–90; active: boolean; start_at, end_at: ISO 8601 с часовым поясом. Период start_at ≤ now < end_at. Только положительная скидка в активном периоде меняет цену.

```json
{
  "product_id": "p1",
  "percent": 10,
  "active": true,
  "start_at": "2026-11-01T00:00:00+05:00",
  "end_at": "2026-12-01T00:00:00+05:00"
}
```

### AdCampaign

campaign_id, product_id, name: string; status: active | paused; budget: number (₸).

```json
{
  "campaign_id": "c1",
  "product_id": "p1",
  "name": "Шампунь Daily Balance",
  "status": "active",
  "budget": 80000
}
```

### AdImpression

impression_id, product_id, campaign_id, query: string; created_at: ISO 8601; is_demo: boolean. В прототипе отправляются только is_demo=true.

```json
{
  "impression_id": "impression-demo-001",
  "product_id": "p1",
  "campaign_id": "c1",
  "query": "Шампунь",
  "is_demo": true,
  "created_at": "2026-11-14T12:00:00+05:00"
}
```

### AdClick

click_id, impression_id, product_id, campaign_id: string; created_at: ISO 8601; is_demo: boolean. Идентификаторы должны соответствовать зарегистрированному показу.

```json
{
  "click_id": "click-demo-001",
  "impression_id": "impression-demo-001",
  "product_id": "p1",
  "campaign_id": "c1",
  "is_demo": true,
  "created_at": "2026-11-14T12:00:00+05:00"
}
```

### DemoOrder

order_id, product_id, pharmacy_id: string; click_id, campaign_id: string | null (null для органической покупки); amount: number (₸); status: confirmed | pending | cancelled; is_demo: true. Frontend не назначает amount и status.

```json
{
  "order_id": "order-demo-001",
  "product_id": "p1",
  "click_id": "click-demo-001",
  "is_demo": true,
  "campaign_id": "c1",
  "pharmacy_id": "ph1",
  "amount": 4320,
  "status": "confirmed"
}
```

### CampaignAnalytics

AdCampaign + все поля AnalyticsOverview ниже. Доли ctr и cvr выражены в процентах (0–100); rr, ar — коэффициенты (0–1). rpi — баллы (0–100). Денежные поля в ₸. cpc, cpa, roas могут быть null. daily — массив дневных аддитивных счётчиков, без повторного суммирования коэффициентов.

```json
{
  "campaign_id": "c1",
  "product_id": "p1",
  "name": "Шампунь Daily Balance",
  "status": "active",
  "budget": 80000,
  "impressions": 20510,
  "clicks": 889,
  "confirmed_purchases": 45,
  "cancelled_orders": 7,
  "relevant_impressions": 18867,
  "available_impressions": 19892,
  "spend": 19670,
  "revenue": 216000,
  "ctr": 4.334470989761092,
  "cpc": 22.125984251968504,
  "cvr": 5.061867266591676,
  "cpa": 437.1111111111111,
  "roas": 10.98118962887646,
  "rpi": 4.516070697948472,
  "rr": 0.919892735251097,
  "ar": 0.9698683568990736,
  "scenario": "after",
  "daily": [
    {
      "date": "2026-11-08",
      "impressions": 2600,
      "clicks": 112,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2392,
      "available_impressions": 2522,
      "spend": 2600,
      "revenue": 28800
    },
    {
      "date": "2026-11-09",
      "impressions": 2710,
      "clicks": 117,
      "confirmed_purchases": 7,
      "cancelled_orders": 1,
      "relevant_impressions": 2493,
      "available_impressions": 2628,
      "spend": 2670,
      "revenue": 33600
    },
    {
      "date": "2026-11-10",
      "impressions": 2820,
      "clicks": 122,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2594,
      "available_impressions": 2735,
      "spend": 2740,
      "revenue": 28800
    },
    {
      "date": "2026-11-11",
      "impressions": 2930,
      "clicks": 127,
      "confirmed_purchases": 7,
      "cancelled_orders": 1,
      "relevant_impressions": 2695,
      "available_impressions": 2842,
      "spend": 2810,
      "revenue": 33600
    },
    {
      "date": "2026-11-12",
      "impressions": 3040,
      "clicks": 132,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2796,
      "available_impressions": 2948,
      "spend": 2880,
      "revenue": 28800
    },
    {
      "date": "2026-11-13",
      "impressions": 3150,
      "clicks": 137,
      "confirmed_purchases": 7,
      "cancelled_orders": 1,
      "relevant_impressions": 2898,
      "available_impressions": 3055,
      "spend": 2950,
      "revenue": 33600
    },
    {
      "date": "2026-11-14",
      "impressions": 3260,
      "clicks": 142,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2999,
      "available_impressions": 3162,
      "spend": 3020,
      "revenue": 28800
    }
  ],
  "active_campaigns": 1,
  "available_products": 1,
  "active_discounts": 1
}
```

### RpiAnalytics

current: AnalyticsOverview для after; baseline: AnalyticsOverview для before; change_percent: number | null. При baseline.rpi=0 изменение не определено (null).

Ниже сокращённый пример факторов; полный ответ с обоими AnalyticsOverview приведён у endpoint.

```json
{
  "current": {
    "rpi": 4.516070697948472,
    "cvr": 5.061867266591676,
    "rr": 0.919892735251097,
    "ar": 0.9698683568990736
  },
  "baseline": {
    "rpi": 2.4392083444257167,
    "cvr": 3.8509316770186333,
    "rr": 0.719892735251097,
    "ar": 0.879863481228669
  },
  "change_percent": 85.14493476004112
}
```

### Recommendation

id, title, text, product_id: string; status: Рекомендуется | Требует внимания | Оптимизировано. Возвращает объяснение причин, а не обещание роста.

```json
{
  "id": "rel-p1",
  "title": "Повысить релевантность",
  "status": "Рекомендуется",
  "text": "Шампунь Daily Balance: 72% релевантных показов в контрольном периоде. Уточните подбор по запросам.",
  "product_id": "p1"
}
```

### AdRecommendation

Product + campaign_id: string; relevance, discount_score, performance, score: number (0–1); explanation: string. Неподходящие, отсутствующие и запрещённые товары не включаются в массив.

```json
{
  "product_id": "p1",
  "pharmacy_id": "ph1",
  "name": "Шампунь Daily Balance",
  "brand": "BOTANICA",
  "category": "Волосы",
  "keywords": [
    "шампунь",
    "шамп",
    "shampoo",
    "волосы",
    "уход за волосами"
  ],
  "price": 4800,
  "in_stock": true,
  "ad_allowed": true,
  "shape": "bottle",
  "color": "mint",
  "volume": "250 мл",
  "discount": {
    "product_id": "p1",
    "percent": 10,
    "active": true,
    "start_at": "2026-11-01T00:00:00+05:00",
    "end_at": "2026-12-01T00:00:00+05:00"
  },
  "effective_discount": 10,
  "current_price": 4320,
  "pharmacy": "Аптека Green",
  "campaign_id": "c1",
  "relevance": 1,
  "discount_score": 0.1,
  "performance": 0.3850931677018633,
  "score": 0.635527950310559,
  "explanation": "Товар соответствует запросу «Шампунь», есть в наличии и участвует в активной кампании. Актуальная скидка: 10%."
}
```

### AnalyticsOverview

Аддитивные поля: impressions, clicks, confirmed_purchases, cancelled_orders, relevant_impressions, available_impressions — целые неотрицательные счётчики; spend, revenue — неотрицательные суммы. budget — согласованный бюджет выбранных кампаний. active_campaigns, available_products, active_discounts — целые числа. scenario — before или after. daily — массив {date, ...аддитивные поля}; сумма daily совпадает с итогом. Коэффициенты вычисляются после агрегации, не усредняются по кампаниям.

- ctr = 100 × clicks / impressions; cpc = spend / clicks.
- cvr = 100 × confirmed_purchases / clicks; cpa = spend / confirmed_purchases.
- roas = revenue / spend.
- rr = relevant_impressions / impressions; ar = available_impressions / impressions.
- rpi = 100 × (cvr / 100) × rr × ar.
- При нулевых знаменателях ctr, cvr, rr, ar, rpi = 0; cpc, cpa, roas = null.

```json
{
  "impressions": 20510,
  "clicks": 889,
  "confirmed_purchases": 45,
  "cancelled_orders": 7,
  "relevant_impressions": 18867,
  "available_impressions": 19892,
  "spend": 19670,
  "revenue": 216000,
  "ctr": 4.334470989761092,
  "cpc": 22.125984251968504,
  "cvr": 5.061867266591676,
  "cpa": 437.1111111111111,
  "roas": 10.98118962887646,
  "rpi": 4.516070697948472,
  "rr": 0.919892735251097,
  "ar": 0.9698683568990736,
  "scenario": "after",
  "budget": 80000,
  "daily": [
    {
      "date": "2026-11-08",
      "impressions": 2600,
      "clicks": 112,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2392,
      "available_impressions": 2522,
      "spend": 2600,
      "revenue": 28800
    },
    {
      "date": "2026-11-09",
      "impressions": 2710,
      "clicks": 117,
      "confirmed_purchases": 7,
      "cancelled_orders": 1,
      "relevant_impressions": 2493,
      "available_impressions": 2628,
      "spend": 2670,
      "revenue": 33600
    },
    {
      "date": "2026-11-10",
      "impressions": 2820,
      "clicks": 122,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2594,
      "available_impressions": 2735,
      "spend": 2740,
      "revenue": 28800
    },
    {
      "date": "2026-11-11",
      "impressions": 2930,
      "clicks": 127,
      "confirmed_purchases": 7,
      "cancelled_orders": 1,
      "relevant_impressions": 2695,
      "available_impressions": 2842,
      "spend": 2810,
      "revenue": 33600
    },
    {
      "date": "2026-11-12",
      "impressions": 3040,
      "clicks": 132,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2796,
      "available_impressions": 2948,
      "spend": 2880,
      "revenue": 28800
    },
    {
      "date": "2026-11-13",
      "impressions": 3150,
      "clicks": 137,
      "confirmed_purchases": 7,
      "cancelled_orders": 1,
      "relevant_impressions": 2898,
      "available_impressions": 3055,
      "spend": 2950,
      "revenue": 33600
    },
    {
      "date": "2026-11-14",
      "impressions": 3260,
      "clicks": 142,
      "confirmed_purchases": 6,
      "cancelled_orders": 1,
      "relevant_impressions": 2999,
      "available_impressions": 3162,
      "spend": 3020,
      "revenue": 28800
    }
  ],
  "active_campaigns": 1,
  "available_products": 1,
  "active_discounts": 1
}
```

## Endpoint

Для каждого GET тело запроса отсутствует. Все endpoint могут вернуть 401/403 при включённой серверной авторизации, 429 при лимите и 500/503 при сбое. Frontend прерывает ожидание через 12 секунд, показывает ошибку и позволяет повторить вручную.

### GET /api/products

Получить каталог с текущими ценами, наличием и вложенной акцией.

**Query parameters:** Нет.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": [
    {
      "product_id": "p1",
      "pharmacy_id": "ph1",
      "name": "Шампунь Daily Balance",
      "brand": "BOTANICA",
      "category": "Волосы",
      "keywords": [
        "шампунь",
        "шамп",
        "shampoo",
        "волосы",
        "уход за волосами"
      ],
      "price": 4800,
      "in_stock": true,
      "ad_allowed": true,
      "shape": "bottle",
      "color": "mint",
      "volume": "250 мл",
      "discount": {
        "product_id": "p1",
        "percent": 10,
        "active": true,
        "start_at": "2026-11-01T00:00:00+05:00",
        "end_at": "2026-12-01T00:00:00+05:00"
      },
      "effective_discount": 10,
      "current_price": 4320,
      "pharmacy": "Аптека Green"
    }
  ]
}
```

**Статусы и ошибки:** 200; 500/503.

**Потребители frontend:** Реклама по скидкам; состояние каталога.

### GET /api/products/search

Найти обычные товары. Поиск и категории применяются сервером.

**Query parameters:** q: string, допускает пустое значение; category: string, необязательно. Пример: ?q=Шампунь&category=Волосы.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": [
    {
      "product_id": "p1",
      "pharmacy_id": "ph1",
      "name": "Шампунь Daily Balance",
      "brand": "BOTANICA",
      "category": "Волосы",
      "keywords": [
        "шампунь",
        "шамп",
        "shampoo",
        "волосы",
        "уход за волосами"
      ],
      "price": 4800,
      "in_stock": true,
      "ad_allowed": true,
      "shape": "bottle",
      "color": "mint",
      "volume": "250 мл",
      "discount": {
        "product_id": "p1",
        "percent": 10,
        "active": true,
        "start_at": "2026-11-01T00:00:00+05:00",
        "end_at": "2026-12-01T00:00:00+05:00"
      },
      "effective_discount": 10,
      "current_price": 4320,
      "pharmacy": "Аптека Green"
    },
    {
      "product_id": "p2",
      "pharmacy_id": "ph1",
      "name": "Шампунь Gentle Care",
      "brand": "PURE LAB",
      "category": "Волосы",
      "keywords": [
        "шампунь",
        "шамп",
        "shampoo",
        "волосы",
        "мягкий"
      ],
      "price": 5600,
      "in_stock": true,
      "ad_allowed": true,
      "shape": "bottle",
      "color": "blue",
      "volume": "300 мл",
      "discount": {
        "product_id": "p2",
        "percent": 5,
        "active": false,
        "start_at": "2026-11-01T00:00:00+05:00",
        "end_at": "2026-12-01T00:00:00+05:00"
      },
      "effective_discount": 0,
      "current_price": 5600,
      "pharmacy": "Аптека Green"
    },
    {
      "product_id": "p3",
      "pharmacy_id": "ph2",
      "name": "Шампунь Fresh Ritual",
      "brand": "NATURALIST",
      "category": "Волосы",
      "keywords": [
        "шампунь",
        "шамп",
        "shampoo",
        "волосы",
        "свежесть"
      ],
      "price": 3900,
      "in_stock": false,
      "ad_allowed": true,
      "shape": "bottle",
      "color": "peach",
      "volume": "250 мл",
      "discount": {
        "product_id": "p3",
        "percent": 25,
        "active": true,
        "start_at": "2026-11-01T00:00:00+05:00",
        "end_at": "2026-12-01T00:00:00+05:00"
      },
      "effective_discount": 25,
      "current_price": 2925,
      "pharmacy": "Аптека City"
    }
  ]
}
```

**Статусы и ошибки:** 200 с [] при отсутствии результатов; 400 при неверном query.

**Потребители frontend:** Витрина «Реклама по запросам».

### GET /api/discounts

Получить список акций.

**Query parameters:** Нет.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": [
    {
      "product_id": "p1",
      "percent": 10,
      "active": true,
      "start_at": "2026-11-01T00:00:00+05:00",
      "end_at": "2026-12-01T00:00:00+05:00"
    }
  ]
}
```

**Статусы и ошибки:** 200; 500/503.

**Потребители frontend:** api.getDiscounts; резерв отдельной загрузки акций. Текущая таблица использует вложенный Product.discount из /products.

### GET /api/ads/recommendations

Получить отсортированные рекламные предложения с объяснением оценки.

**Query parameters:** q: string; campaign_id: string, необязательно; smart: true|false, по умолчанию true. При false исключается скидочный компонент, сохраняются релевантность, наличие и историческая эффективность.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": [
    {
      "product_id": "p1",
      "pharmacy_id": "ph1",
      "name": "Шампунь Daily Balance",
      "brand": "BOTANICA",
      "category": "Волосы",
      "keywords": [
        "шампунь",
        "шамп",
        "shampoo",
        "волосы",
        "уход за волосами"
      ],
      "price": 4800,
      "in_stock": true,
      "ad_allowed": true,
      "shape": "bottle",
      "color": "mint",
      "volume": "250 мл",
      "discount": {
        "product_id": "p1",
        "percent": 10,
        "active": true,
        "start_at": "2026-11-01T00:00:00+05:00",
        "end_at": "2026-12-01T00:00:00+05:00"
      },
      "effective_discount": 10,
      "current_price": 4320,
      "pharmacy": "Аптека Green",
      "campaign_id": "c1",
      "relevance": 1,
      "discount_score": 0.1,
      "performance": 0.3850931677018633,
      "score": 0.635527950310559,
      "explanation": "Товар соответствует запросу «Шампунь», есть в наличии и участвует в активной кампании. Актуальная скидка: 10%."
    }
  ]
}
```

**Статусы и ошибки:** 200 с [] при отсутствии кандидатов; 400 неверные параметры; 404 неизвестная кампания.

**Потребители frontend:** Умная реклама, поиск, сравнение скидок и предпросмотр.

### POST /api/ads/impression

Зарегистрировать одно идемпотентное тестовое событие показа.

**Query parameters:** Нет.

**Request body:** 

```json
{
  "impression_id": "impression-demo-001",
  "product_id": "p1",
  "campaign_id": "c1",
  "query": "Шампунь",
  "is_demo": true
}
```


**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": {
    "impression_id": "impression-demo-001",
    "product_id": "p1",
    "campaign_id": "c1",
    "query": "Шампунь",
    "is_demo": true,
    "created_at": "2026-11-14T12:00:00+05:00"
  }
}
```

**Статусы и ошибки:** 201 новый / 200 повторный ID с тем же телом; 409 тот же ID с другим телом или объявление больше не допускается; 422 неверные связи ID.

**Потребители frontend:** Открытие рекламной карточки; шаг 6 демонстрации.

### POST /api/ads/click

Зарегистрировать клик, связанный с показом. В простой демомодели — не более одного клика на показ.

**Query parameters:** Нет.

**Request body:** 

```json
{
  "click_id": "click-demo-001",
  "impression_id": "impression-demo-001",
  "product_id": "p1",
  "campaign_id": "c1",
  "is_demo": true
}
```


**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": {
    "click_id": "click-demo-001",
    "impression_id": "impression-demo-001",
    "product_id": "p1",
    "campaign_id": "c1",
    "is_demo": true,
    "created_at": "2026-11-14T12:00:00+05:00"
  }
}
```

**Статусы и ошибки:** 201 / 200 повтор; 404 неизвестный показ; 409 конфликт ID; 422 несоответствие товара/кампании.

**Потребители frontend:** Кнопка «Подробнее» рекламной карточки после регистрации показа.

### POST /api/orders/demo

Создать исключительно тестовую покупку. Цена фиксируется сервером на момент создания.

**Query parameters:** Нет.

**Request body:** 

```json
{
  "order_id": "order-demo-001",
  "product_id": "p1",
  "click_id": "click-demo-001",
  "is_demo": true
}
```


**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": {
    "order_id": "order-demo-001",
    "product_id": "p1",
    "click_id": "click-demo-001",
    "is_demo": true,
    "campaign_id": "c1",
    "pharmacy_id": "ph1",
    "amount": 4320,
    "status": "confirmed"
  }
}
```

**Статусы и ошибки:** 201 / 200 повтор; 403 не тестовая среда; 409 нет наличия/конфликт ID; 422 неверная связь click_id/product_id. Для органической покупки click_id=null, рекламная аналитика не меняется.

**Потребители frontend:** Модальное окно товара; шаг 7. Повторный клик блокируется на клиенте; сервер всё равно дедуплицирует.

### GET /api/analytics/overview

Вернуть агрегированную аналитику и дневной ряд.

**Query parameters:** campaign_id: string, необязательно; scenario: before|after, по умолчанию after.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": {
    "impressions": 20510,
    "clicks": 889,
    "confirmed_purchases": 45,
    "cancelled_orders": 7,
    "relevant_impressions": 18867,
    "available_impressions": 19892,
    "spend": 19670,
    "revenue": 216000,
    "ctr": 4.334470989761092,
    "cpc": 22.125984251968504,
    "cvr": 5.061867266591676,
    "cpa": 437.1111111111111,
    "roas": 10.98118962887646,
    "rpi": 4.516070697948472,
    "rr": 0.919892735251097,
    "ar": 0.9698683568990736,
    "scenario": "after",
    "budget": 80000,
    "daily": [
      {
        "date": "2026-11-08",
        "impressions": 2600,
        "clicks": 112,
        "confirmed_purchases": 6,
        "cancelled_orders": 1,
        "relevant_impressions": 2392,
        "available_impressions": 2522,
        "spend": 2600,
        "revenue": 28800
      },
      {
        "date": "2026-11-09",
        "impressions": 2710,
        "clicks": 117,
        "confirmed_purchases": 7,
        "cancelled_orders": 1,
        "relevant_impressions": 2493,
        "available_impressions": 2628,
        "spend": 2670,
        "revenue": 33600
      },
      {
        "date": "2026-11-10",
        "impressions": 2820,
        "clicks": 122,
        "confirmed_purchases": 6,
        "cancelled_orders": 1,
        "relevant_impressions": 2594,
        "available_impressions": 2735,
        "spend": 2740,
        "revenue": 28800
      },
      {
        "date": "2026-11-11",
        "impressions": 2930,
        "clicks": 127,
        "confirmed_purchases": 7,
        "cancelled_orders": 1,
        "relevant_impressions": 2695,
        "available_impressions": 2842,
        "spend": 2810,
        "revenue": 33600
      },
      {
        "date": "2026-11-12",
        "impressions": 3040,
        "clicks": 132,
        "confirmed_purchases": 6,
        "cancelled_orders": 1,
        "relevant_impressions": 2796,
        "available_impressions": 2948,
        "spend": 2880,
        "revenue": 28800
      },
      {
        "date": "2026-11-13",
        "impressions": 3150,
        "clicks": 137,
        "confirmed_purchases": 7,
        "cancelled_orders": 1,
        "relevant_impressions": 2898,
        "available_impressions": 3055,
        "spend": 2950,
        "revenue": 33600
      },
      {
        "date": "2026-11-14",
        "impressions": 3260,
        "clicks": 142,
        "confirmed_purchases": 6,
        "cancelled_orders": 1,
        "relevant_impressions": 2999,
        "available_impressions": 3162,
        "spend": 3020,
        "revenue": 28800
      }
    ],
    "active_campaigns": 1,
    "available_products": 1,
    "active_discounts": 1
  }
}
```

**Статусы и ошибки:** 200; 400 параметры; 404 кампания.

**Потребители frontend:** Обзор, эффективность, KPI и графики. Пример ответа отфильтрован по c1.

### GET /api/analytics/campaigns

Вернуть кампании с их аналитикой.

**Query parameters:** campaign_id: string, необязательно; scenario: before|after.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": [
    {
      "campaign_id": "c1",
      "product_id": "p1",
      "name": "Шампунь Daily Balance",
      "status": "active",
      "budget": 80000,
      "impressions": 20510,
      "clicks": 889,
      "confirmed_purchases": 45,
      "cancelled_orders": 7,
      "relevant_impressions": 18867,
      "available_impressions": 19892,
      "spend": 19670,
      "revenue": 216000,
      "ctr": 4.334470989761092,
      "cpc": 22.125984251968504,
      "cvr": 5.061867266591676,
      "cpa": 437.1111111111111,
      "roas": 10.98118962887646,
      "rpi": 4.516070697948472,
      "rr": 0.919892735251097,
      "ar": 0.9698683568990736,
      "scenario": "after",
      "daily": [
        {
          "date": "2026-11-08",
          "impressions": 2600,
          "clicks": 112,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2392,
          "available_impressions": 2522,
          "spend": 2600,
          "revenue": 28800
        },
        {
          "date": "2026-11-09",
          "impressions": 2710,
          "clicks": 117,
          "confirmed_purchases": 7,
          "cancelled_orders": 1,
          "relevant_impressions": 2493,
          "available_impressions": 2628,
          "spend": 2670,
          "revenue": 33600
        },
        {
          "date": "2026-11-10",
          "impressions": 2820,
          "clicks": 122,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2594,
          "available_impressions": 2735,
          "spend": 2740,
          "revenue": 28800
        },
        {
          "date": "2026-11-11",
          "impressions": 2930,
          "clicks": 127,
          "confirmed_purchases": 7,
          "cancelled_orders": 1,
          "relevant_impressions": 2695,
          "available_impressions": 2842,
          "spend": 2810,
          "revenue": 33600
        },
        {
          "date": "2026-11-12",
          "impressions": 3040,
          "clicks": 132,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2796,
          "available_impressions": 2948,
          "spend": 2880,
          "revenue": 28800
        },
        {
          "date": "2026-11-13",
          "impressions": 3150,
          "clicks": 137,
          "confirmed_purchases": 7,
          "cancelled_orders": 1,
          "relevant_impressions": 2898,
          "available_impressions": 3055,
          "spend": 2950,
          "revenue": 33600
        },
        {
          "date": "2026-11-14",
          "impressions": 3260,
          "clicks": 142,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2999,
          "available_impressions": 3162,
          "spend": 3020,
          "revenue": 28800
        }
      ],
      "active_campaigns": 1,
      "available_products": 1,
      "active_discounts": 1
    }
  ]
}
```

**Статусы и ошибки:** 200 с [] если нет кампаний; 400 параметры.

**Потребители frontend:** Верхний выбор кампании, таблицы, расходы и CSV-экспорт. Пример отфильтрован по c1.

### GET /api/analytics/rpi

Вернуть актуальный и базовый RPI с исходными факторами.

**Query parameters:** campaign_id: string, необязательно. scenario игнорируется: current всегда after, baseline всегда before.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": {
    "current": {
      "impressions": 20510,
      "clicks": 889,
      "confirmed_purchases": 45,
      "cancelled_orders": 7,
      "relevant_impressions": 18867,
      "available_impressions": 19892,
      "spend": 19670,
      "revenue": 216000,
      "ctr": 4.334470989761092,
      "cpc": 22.125984251968504,
      "cvr": 5.061867266591676,
      "cpa": 437.1111111111111,
      "roas": 10.98118962887646,
      "rpi": 4.516070697948472,
      "rr": 0.919892735251097,
      "ar": 0.9698683568990736,
      "scenario": "after",
      "budget": 80000,
      "daily": [
        {
          "date": "2026-11-08",
          "impressions": 2600,
          "clicks": 112,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2392,
          "available_impressions": 2522,
          "spend": 2600,
          "revenue": 28800
        },
        {
          "date": "2026-11-09",
          "impressions": 2710,
          "clicks": 117,
          "confirmed_purchases": 7,
          "cancelled_orders": 1,
          "relevant_impressions": 2493,
          "available_impressions": 2628,
          "spend": 2670,
          "revenue": 33600
        },
        {
          "date": "2026-11-10",
          "impressions": 2820,
          "clicks": 122,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2594,
          "available_impressions": 2735,
          "spend": 2740,
          "revenue": 28800
        },
        {
          "date": "2026-11-11",
          "impressions": 2930,
          "clicks": 127,
          "confirmed_purchases": 7,
          "cancelled_orders": 1,
          "relevant_impressions": 2695,
          "available_impressions": 2842,
          "spend": 2810,
          "revenue": 33600
        },
        {
          "date": "2026-11-12",
          "impressions": 3040,
          "clicks": 132,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2796,
          "available_impressions": 2948,
          "spend": 2880,
          "revenue": 28800
        },
        {
          "date": "2026-11-13",
          "impressions": 3150,
          "clicks": 137,
          "confirmed_purchases": 7,
          "cancelled_orders": 1,
          "relevant_impressions": 2898,
          "available_impressions": 3055,
          "spend": 2950,
          "revenue": 33600
        },
        {
          "date": "2026-11-14",
          "impressions": 3260,
          "clicks": 142,
          "confirmed_purchases": 6,
          "cancelled_orders": 1,
          "relevant_impressions": 2999,
          "available_impressions": 3162,
          "spend": 3020,
          "revenue": 28800
        }
      ],
      "active_campaigns": 1,
      "available_products": 1,
      "active_discounts": 1
    },
    "baseline": {
      "impressions": 20510,
      "clicks": 805,
      "confirmed_purchases": 31,
      "cancelled_orders": 7,
      "relevant_impressions": 14765,
      "available_impressions": 18046,
      "spend": 19670,
      "revenue": 148800,
      "ctr": 3.9249146757679183,
      "cpc": 24.434782608695652,
      "cvr": 3.8509316770186333,
      "cpa": 634.516129032258,
      "roas": 7.564819522114896,
      "rpi": 2.4392083444257167,
      "rr": 0.719892735251097,
      "ar": 0.879863481228669,
      "scenario": "before",
      "budget": 80000,
      "daily": [
        {
          "date": "2026-11-08",
          "impressions": 2600,
          "clicks": 100,
          "confirmed_purchases": 4,
          "cancelled_orders": 1,
          "relevant_impressions": 1872,
          "available_impressions": 2288,
          "spend": 2600,
          "revenue": 19200
        },
        {
          "date": "2026-11-09",
          "impressions": 2710,
          "clicks": 105,
          "confirmed_purchases": 5,
          "cancelled_orders": 1,
          "relevant_impressions": 1951,
          "available_impressions": 2384,
          "spend": 2670,
          "revenue": 24000
        },
        {
          "date": "2026-11-10",
          "impressions": 2820,
          "clicks": 110,
          "confirmed_purchases": 4,
          "cancelled_orders": 1,
          "relevant_impressions": 2030,
          "available_impressions": 2481,
          "spend": 2740,
          "revenue": 19200
        },
        {
          "date": "2026-11-11",
          "impressions": 2930,
          "clicks": 115,
          "confirmed_purchases": 5,
          "cancelled_orders": 1,
          "relevant_impressions": 2109,
          "available_impressions": 2578,
          "spend": 2810,
          "revenue": 24000
        },
        {
          "date": "2026-11-12",
          "impressions": 3040,
          "clicks": 120,
          "confirmed_purchases": 4,
          "cancelled_orders": 1,
          "relevant_impressions": 2188,
          "available_impressions": 2675,
          "spend": 2880,
          "revenue": 19200
        },
        {
          "date": "2026-11-13",
          "impressions": 3150,
          "clicks": 125,
          "confirmed_purchases": 5,
          "cancelled_orders": 1,
          "relevant_impressions": 2268,
          "available_impressions": 2772,
          "spend": 2950,
          "revenue": 24000
        },
        {
          "date": "2026-11-14",
          "impressions": 3260,
          "clicks": 130,
          "confirmed_purchases": 4,
          "cancelled_orders": 1,
          "relevant_impressions": 2347,
          "available_impressions": 2868,
          "spend": 3020,
          "revenue": 19200
        }
      ],
      "active_campaigns": 1,
      "available_products": 1,
      "active_discounts": 1
    },
    "change_percent": 85.14493476004112
  }
}
```

**Статусы и ошибки:** 200; 400 параметры; 404 кампания.

**Потребители frontend:** Большая карточка RPI, сравнительные KPI и аналитика. Пример для c1.

### GET /api/recommendations

Вернуть объяснимые рекомендации и статусы.

**Query parameters:** campaign_id: string, необязательно; scenario допустим, в прототипе рекомендации используют контрольную историю и актуальный каталог.

**Request body:** отсутствует.

**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": [
    {
      "id": "rel-p1",
      "title": "Повысить релевантность",
      "status": "Рекомендуется",
      "text": "Шампунь Daily Balance: 72% релевантных показов в контрольном периоде. Уточните подбор по запросам.",
      "product_id": "p1"
    }
  ]
}
```

**Статусы и ошибки:** 200 с [] если рекомендаций нет; 400 параметры.

**Потребители frontend:** Обзор, Умная реклама и Аналитика.

### PATCH /api/products/{product_id}

Предлагаемое дополнение к предварительному контракту: менять тестовые параметры предложения. В production требуется серверная авторизация.

**Query parameters:** Нет. product_id в path.

**Request body:** 

```json
{
  "product_id": "p1",
  "percent": 20,
  "active": true,
  "in_stock": true
}
```


**Response body:** объект {data: ...}; пример успешного JSON:

```json
{
  "data": {
    "product_id": "p1",
    "pharmacy_id": "ph1",
    "name": "Шампунь Daily Balance",
    "brand": "BOTANICA",
    "category": "Волосы",
    "keywords": [
      "шампунь",
      "шамп",
      "shampoo",
      "волосы",
      "уход за волосами"
    ],
    "price": 4800,
    "in_stock": true,
    "ad_allowed": true,
    "shape": "bottle",
    "color": "mint",
    "volume": "250 мл",
    "discount": {
      "product_id": "p1",
      "percent": 20,
      "active": true,
      "start_at": "2026-11-01T00:00:00+05:00",
      "end_at": "2026-12-01T00:00:00+05:00"
    },
    "effective_discount": 20,
    "current_price": 3840,
    "pharmacy": "Аптека Green"
  }
}
```

**Статусы и ошибки:** 200 полная обновлённая Product; 400 неверные типы; 404 товар; 422 процент вне 0–90; 403 нет прав.

**Потребители frontend:** Редактирование скидки, активности акции и наличия. Передаются только изменённые поля, product_id всегда присутствует.

## Идемпотентность и обновление аналитики

1. До запроса клиент создаёт стабильные UUID. Ошибка сети не должна приводить к генерации новых ID для той же операции.
2. Сервер атомарно сохраняет событие и его результат по ID. Повтор с тем же телом возвращает прежний результат; с другим — 409.
3. click.impression_id должен ссылаться на тот же product_id и campaign_id. order.click_id определяет атрибуцию; переданный клиентом campaign_id не является доказательством.
4. Для тестовой модели не более одного клика на показ и не более одного подтверждённого заказа на click_id, даже с разными ID повторных запросов.
5. После успешного тестового заказа все GET аналитики должны видеть согласованный итог. При eventual consistency добавьте согласованный механизм статуса/версии; текущий UI рассчитывает на read-after-write.
6. Историческая выручка — сумма зафиксированных цен заказов, не текущая цена каталога × количество покупок. Изменение скидки не пересчитывает историю.
7. Локальный симулятор дополнительно защищает от повторного учёта, но не заменяет серверные ограничения. Локальная дедупликация действует до перезагрузки/сброса.
8. Сброс DEMO — локальная операция, /api/demo/reset не вызывается в API-режиме и не требуется backend.

## Правила Smart Ranking

До оценки исключаются in_stock=false, ad_allowed=false, неактивные кампании и relevance=0. Нормализованные оценки: relevance по словарю/категориям; discount_score = действующая скидка / 100; performance = min(CVR контрольного периода / 10%, 1). Итог: 0.50 × relevance + 0.20 × discount_score + 0.30 × performance. При smart=false скидочная часть равна нулю. Равные оценки сортируются стабильно по product_id. Backend может заменить правило моделью, сохранив объяснение и согласованный формат ответа.

## RPI и проверка гипотез

RPI — экспериментальный составной показатель, не вероятность дополнительной покупки и не доказательство causal uplift. 100 × 0.05 × 0.90 × 0.95 = 4.275. Изменение относительно 3.10 составляет +37.9032%, при отображении с одним знаком +37.9%. Значение 4.28 является округлённым; для расчёта изменения используется 4.275. Не вводить произвольные пороги «хорошего RPI».

RR и AR — отдельные агрегированные доли; их произведение не измеряет пересечение событий. Потребуются контрольная группа, правила атрибуции, реальные подтверждённые заказы и проверка статистической значимости.

## CORS и интеграционная приёмка

Разрешите origin статического frontend, например http://localhost:8080 или http://127.0.0.1:4173. Разрешите GET, POST, PATCH, OPTIONS и заголовки Content-Type, Accept. Не разрешайте production-источники шире необходимого. HTTPS frontend требует HTTPS API (localhost имеет отдельные браузерные ограничения).

Проверить: пустые массивы; 400/403/404/409/422/429/500; не-JSON ответ; таймаут; нулевые знаменатели; просроченную и будущую акцию; товар без наличия; повтор тех же ID; конфликт тела с ID; сумму кампаний против overview; цену заказа после изменения акции; отсутствие реальных заказов через /orders/demo. Frontend не повторяет POST автоматически и не подменяет серверную ошибку mock-ответом.
