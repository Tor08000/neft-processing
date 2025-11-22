NEFT Processing — локальная среда: Postgres, Redis, Core API, Auth Host, AI Service, Workers, Nginx.

Быстрый старт:
1) Скопировать .env.example -> .env (cp -n .env.example .env)
2) docker compose up -d --build

Проверка: http://localhost:8001/api/v1/health и http://localhost:8081/
