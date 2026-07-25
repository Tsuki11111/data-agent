启动项目：`.venv/Scripts/uvicorn main:app --reload --host localhost --port 8000`

浏览器打开 http://localhost:8000 使用对话式前端查询。

构建元数据知识库：`python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml`