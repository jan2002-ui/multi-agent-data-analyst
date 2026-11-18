.PHONY: install run test lint cli docker
install:
	pip install -r requirements-dev.txt
run:
	streamlit run app.py
test:
	python -m pytest -q
lint:
	ruff check .
cli:
	python main.py data/sample/sales_dataset.csv
docker:
	docker build -t multi-agent-data-analyst . && docker run -p 8501:8501 multi-agent-data-analyst
