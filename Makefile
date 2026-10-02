.PHONY: dev test seed freeze eval deploy capture

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest tests/

freeze:
	pip freeze > requirements.lock

seed:
	python ../scripts/seed.py

eval:
	python ../eval/run.py

capture:
	python ../scripts/capture.py

deploy:
	gcloud run deploy contextiq --source . --region us-central1 --allow-unauthenticated
