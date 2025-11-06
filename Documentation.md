# Backend API для интернет-магазина

Django REST API для интернет-магазина с API для покупателей и магазинов-партнеров.

## 🚀 Быстрый старт

```bash
git clone <repository-url>
```
```bash
cd netology_pd_diplom
```
```bash
pip install -r requirements.txt
```
```bash
python manage.py migrate
```
```bash
python manage.py runserver
```
```bash
# В отдельном терминале:
celery -A backend worker -l info
```
## 🧪Тестирование

```bash
python manage.py test
# Результат: 20 tests OK
```

## 📖 Документация API

### 🔐 Аутентификация

### Регистрация

```
POST /api/v1/user/register
```

```json
{
  "first_name": "Иван",
  "last_name": "Иванов", 
  "email": "ivan@example.com",
  "password": "pass123",
  "company": "ООО Ромашка",
  "position": "Менеджер"
}
```

### Авторизация
```
POST /api/v1/user/login
```
```json
{
  "email": "ivan@example.com",
  "password": "pass123"
}
```
```
Ответ: {"Status": true, "Token": "abc123"}
```

### 👤 Контакты
### Добавить контакт
```
POST /api/v1/user/contact
```
```json
{
  "city": "Москва",
  "street": "Тверская", 
  "phone": "+79161234567"
}
```
### Получить контакты
```
GET /api/v1/user/contact
```
### Удалить контакты
```
DELETE /api/v1/user/contact
```
```json
{"items": "1,2,3"}
```
### 🏪 Каталог

* Категории ``` GET /api/v1/categories```
* Магазины ``` GET /api/v1/shops```
* Товары ```GET /api/v1/products```

### 🛒 Корзина
### Просмотр 
```GET /api/v1/basket```

### Добавить товары
```POST /api/v1/basket```

```json
{
  "items": [
    {"product_info": 1, "quantity": 2}
  ]
}
```
### Обновить количество
```PUT /api/v1/basket```

```json
{
  "items": [
    {"id": 1, "quantity": 3}
  ]
}
```
### Удалить товары
```DELETE /api/v1/basket```

```json
{"items": "1,2"}
```

### 📦 Заказы
### История заказов 
```GET /api/v1/order```

### Создать заказ
``` POST /api/v1/order```

```json
{"id": 5, "contact": 1}
```
Ответ: ``` {"Status": true, "OrderID": 1, "TotalPrice": 10000} ```

### Обновить заказ
```PUT /api/v1/order```

```json
{"id": 1, "contact": 2}
```
### Отменить заказ
```DELETE /api/v1/order```

```json
{"id": 1}
```

### 🤝 Partner API
### Статус магазина
* Получить ``` GET /api/v1/partner/state```
* Изменить ``` POST /api/v1/partner/state ```

```json
{"state": "false"}
```
### Импорт товаров
```POST /api/v1/partner/update```

```json
{"url": "http://example.com/price.yaml"}
```
### Заказы магазина 
```GET /api/v1/partner/orders```

### ⚠️ Ошибки
Формат:

```json
{
  "Status": false,
  "Errors": "Описание ошибки"
}
```
Коды: 
* 400 (данные)
* 401 (авторизация)
* 403 (доступ)
* 404 (не найдено)