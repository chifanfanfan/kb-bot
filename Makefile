PY ?= python
PORT ?= 8000

.PHONY: help setup models build demo test eval web clean

help:
	@echo "make setup   安装依赖（不含模型）"
	@echo "make models  下载向量与重排模型（约 306 MB）"
	@echo "make build   建索引（data 下的 PDF）"
	@echo "make demo    跑 5 分钟演示"
	@echo "make test    单元测试（不依赖模型/网络）"
	@echo "make eval    检索指标 + 端到端评测"
	@echo "make web     启动网页界面 :$(PORT)"

setup:
	$(PY) -m pip install -r requirements.txt pytest

models:
	$(PY) scripts/fetch_models.py

build:
	$(PY) -m kb build data/毕业论文_脱敏.pdf

demo:
	$(PY) tools/demo.py

test:
	$(PY) -m pytest tests -q

eval:
	$(PY) -m kb eval --answers

web:
	$(PY) web/app.py --port $(PORT)

clean:
	rm -rf chroma models __pycache__ .pytest_cache
