# Панель Мастера Подземелий

Веб-приложение на C# / ASP.NET Core (Blazor Server) для ведения кампаний D&D: кампании и сессии, персонажи игроков, бестиарий монстров/NPC и трекер инициативы для боя.

## Стек

- .NET 8, Blazor Server (Interactive Server render mode)
- EF Core 8 + SQLite (по умолчанию, локально); переключается на PostgreSQL конфигурацией
- Архитектура: `DMA.Domain` → `DMA.Application` → `DMA.Infrastructure` → `DMA.Web`

## Запуск локально

```bash
dotnet run --project src/DMA.Web
```

При первом запуске приложение само применит миграции (создаст `dungeonmaster.db`) и засеет бестиарий несколькими монстрами из SRD 5.1. Откройте адрес, который выведет `dotnet run` (обычно `https://localhost:5xxx`).

## Тесты

```bash
dotnet test
```

## Переключение на PostgreSQL (для будущего деплоя)

В `appsettings.json` / переменных окружения:

```
Database__Provider=Postgres
ConnectionStrings__Default=Host=...;Database=...;Username=...;Password=...
```

Обратите внимание: текущая миграция (`src/DMA.Infrastructure/Data/Migrations`) сгенерирована под SQLite. Перед реальным деплоем на PostgreSQL нужно сгенерировать отдельный набор миграций под Npgsql (`dotnet ef migrations add InitialCreate -o Data/Migrations/Postgres -- --provider Postgres`, потребуется небольшая доработка `AppDbContextFactory`).

Также в репозитории есть `Dockerfile` и `docker-compose.yml` (веб + Postgres) как отправная точка для контейнерного деплоя.
