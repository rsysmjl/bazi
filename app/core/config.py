"""应用配置：读取 .env，统一暴露给各层。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout: float = 120.0

    # provider 路由：local / thirdparty
    provider_bazi: str = "local"
    provider_ziwei: str = "local"
    provider_qimen: str = "local"
    allow_fallback: bool = True

    # 第三方排盘
    thirdparty_base_url: str = ""
    thirdparty_api_key: str = ""

    # 紫微 Node 桥接
    ziwei_mode: str = "per_process"  # per_process | node_service
    ziwei_node_bin: str = "node"
    ziwei_script_path: str = "node_ziwei/ziwei-chart.mjs"

    # 真太阳时
    true_solar_time: bool = True

    # 数据库（业务落库；连接失败不阻塞接口）
    db_enabled: bool = True
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "mingpan"

    # 安全
    api_keys: str = ""  # 逗号分隔；为空则不校验

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
