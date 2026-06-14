.PHONY: help backend-install backend-seed backend-run backend-test frontend-install frontend-dev frontend-build up down

help:
	@echo "Bugis - DCI/EVPN 专线运营平台"
	@echo "  make backend-install   安装后端依赖"
	@echo "  make backend-seed      初始化演示数据"
	@echo "  make backend-run       启动后端 (http://localhost:8000)"
	@echo "  make backend-test      运行后端测试"
	@echo "  make frontend-install  安装前端依赖"
	@echo "  make frontend-dev      启动前端 (http://localhost:5173)"
	@echo "  make frontend-build    构建前端"
	@echo "  make up / down         docker compose 启停"

backend-install:
	cd backend && pip install -r requirements.txt

backend-seed:
	cd backend && python -m scripts.seed

backend-run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd backend && python -m pytest -q

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

up:
	docker compose up --build

down:
	docker compose down
