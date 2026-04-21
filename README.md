# Payment Processing Service

Асинхронный микросервис для обработки платежей с webhook уведомлениями.

## Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI API  │────▶│  PostgreSQL │
└─────────────┘     └──────────────┘     └─────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │  Outbox Table │
                    └──────────────┘
                          │
                          ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   RabbitMQ   │────▶│  Consumer   │
                    │ payments.new │     │  Processor  │
                    └──────────────┘     └─────────────┘
                                                │
                                                ▼
                                          ┌─────────────┐
                                          │   Webhook   │
                                          │  (Client)   │
                                          └─────────────┘
```

## Компоненты

### API (FastAPI)
- `POST /api/v1/payments` - Создание платежа
- `GET /api/v1/payments/{payment_id}` - Получение информации о платеже
- `GET /health` - Проверка здоровья сервиса

### Consumer
- Обрабатывает сообщения из очереди `payments.new`
- Эмулирует обработку платежа (2-5 сек, 90% успех)
- Обновляет статус в БД
- Отправляет webhook уведомление

### Outbox Pattern
Гарантированная доставка событий через таблицу `outbox_messages`.

## Быстрый старт

### Через Docker Compose

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f api
docker-compose logs -f consumer

# Остановка
docker-compose down
```

### Локальная разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск PostgreSQL и RabbitMQ
docker-compose up -d postgres rabbitmq

# Применение миграций
alembic upgrade head

# Запуск API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Запуск Consumer (в отдельном терминале)
python -m app.consumers.payment_consumer
```

## Примеры использования

### Создание платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-api-key-secret" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "amount": 1000.00,
    "currency": "RUB",
    "description": "Оплата заказа #123",
    "metadata": {"order_id": "123", "user_id": "456"},
    "webhook_url": "https://webhook.site/your-unique-id"
  }'
```

Ответ:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": "1000.00",
  "currency": "RUB",
  "description": "Оплата заказа #123",
  "metadata": {"order_id": "123", "user_id": "456"},
  "status": "pending",
  "idempotency_key": "unique-key-123",
  "webhook_url": "https://webhook.site/your-unique-id",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "processed_at": null
}
```

### Получение информации о платеже

```bash
curl http://localhost:8000/api/v1/payments/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: test-api-key-secret"
```

### Webhook уведомление

После обработки платежа на указанный `webhook_url` будет отправлен POST запрос:

```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",
  "amount": "1000.00",
  "currency": "RUB",
  "timestamp": "2024-01-01T12:00:05Z"
}
```

При ошибке:
```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "amount": "1000.00",
  "currency": "RUB",
  "timestamp": "2024-01-01T12:00:05Z",
  "error": "Insufficient funds"
}
```

## Конфигурация

Переменные окружения:

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DB_HOST` | Хост PostgreSQL | `postgres` |
| `DB_PORT` | Порт PostgreSQL | `5432` |
| `DB_NAME` | Имя базы данных | `payments` |
| `DB_USER` | Пользователь БД | `postgres` |
| `DB_PASSWORD` | Пароль БД | `postgres` |
| `RABBIT_HOST` | Хост RabbitMQ | `rabbitmq` |
| `RABBIT_PORT` | Порт RabbitMQ | `5672` |
| `RABBIT_USER` | Пользователь RabbitMQ | `guest` |
| `RABBIT_PASSWORD` | Пароль RabbitMQ | `guest` |
| `API_KEY` | Ключ аутентификации API | `test-api-key-secret` |
| `PAYMENT_SUCCESS_RATE` | Вероятность успеха платежа | `0.9` |
| `MAX_RETRIES` | Количество попыток отправки webhook | `3` |

## Идемпотентность

Для защиты от дублирования платежей используется заголовок `Idempotency-Key`. 
При повторном запросе с тем же ключом будет возвращен существующий платеж.

## Dead Letter Queue

Сообщения, которые не удалось обработать после 3 попыток, направляются в DLQ 
(очередь `payments.dlq`).

## Миграции

```bash
# Применить все миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Создать новую миграцию
alembic revision --autogenerate -m "Description"
```

## Тестирование webhook

Используйте сервисы вроде [webhook.site](https://webhook.site) или [ngrok](https://ngrok.com) 
для получения webhook уведомлений во время разработки.

## Запуск тестов

Проект использует `pytest` для автоматизированного тестирования. Тесты покрывают API эндпоинты, сервисы, миграции БД и работу с платежным шлюзом.

### Запуск в Docker контейнере

```bash
# Установка необходимых зависимостей (если не установлены в образе)
docker-compose exec api pip install pytest pytest-asyncio pytest-cov aiosqlite httpx

# Запуск всех тестов с подробным выводом
docker-compose exec api pytest tests/ -v

# Запуск тестов с отчетом о покрытии кода
docker-compose exec api pytest tests/ -v --cov=app --cov-report=term-missing

# Запуск тестов по категориям
docker-compose exec api pytest tests/test_api.py -v        # Тесты API
docker-compose exec api pytest tests/test_services.py -v   # Тесты сервисов
docker-compose exec api pytest tests/test_migrations.py -v # Тесты миграций
docker-compose exec api pytest tests/test_gateway.py -v    # Тесты платежного шлюза
```

### Локальный запуск тестов

```bash
# Установка зависимостей
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov aiosqlite httpx

# Запуск PostgreSQL и RabbitMQ (требуется для интеграционных тестов)
docker-compose up -d postgres rabbitmq

# Применение миграций
alembic upgrade head

# Запуск всех тестов
pytest tests/ -v

# Запуск с покрытием
pytest tests/ -v --cov=app --cov-report=html
```

### Структура тестов

- `test_api.py` - Тесты REST API эндпоинтов (создание платежа, получение статуса, идемпотентность)
- `test_services.py` - Тесты бизнес-логики и сервисов обработки платежей
- `test_migrations.py` - Тесты целостности схемы БД и миграций Alembic
- `test_gateway.py` - Тесты эмуляции внешнего платежного шлюза

### Конфигурация тестирования

Настройки pytest находятся в файле `pytest.ini`:
- Асинхронный режим через `pytest-asyncio`
- Автоматическое обнаружение асинхронных тестов
- Отчет о покрытии кода (опционально)

Фикстуры для тестов определены в `tests/conftest.py` и включают:
- Изолированную тестовую базу данных (SQLite для юнит-тестов, PostgreSQL для интеграционных)
- Моки для внешних зависимостей (RabbitMQ, webhook)
- Тестовые данные и фабрики объектов
