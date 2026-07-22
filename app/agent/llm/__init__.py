import os

from langchain.chat_models import init_chat_model

from app.conf.app_config import appconfig

llm = init_chat_model(
        model=appconfig.llm.model_name,  # 模型名称
        api_key=os.getenv("DASHSCOPE_API_KEY"),  # 通义千问API密钥
        base_url=appconfig.llm.base_url,  # 阿里云兼容接口地址
        model_provider="openai",
    )
