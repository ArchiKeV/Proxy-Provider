from pydantic import BaseModel, PositiveInt
from loguru import logger
import json
import os

base_config = {
    "db": {
        "db_type": "sqlite",
        "settings": {
            "filepath": "proxy_provider_db.sqlite",
            "concurrent_slots": 1
        }
    },
    "proxy": {
        "country_code_ignore_list": [
            "IR"  # Iran
        ],
        "sources": [],  # check the README for this setting
        "checkup_timers": {
            "active_server_check_period_in_hours": 1,
            "inactive_server_check_period_in_hours": 24
        },
        "timeouts":
        {
            "connection_timeout": 10,
            "read_timeout": 30
        },
        "num_of_simultaneous_checks": 5
    },
    "system":
    {
        "tui_text_line_buffer_size": 500,
        "debug": False
    }
}


class RootConfig(BaseModel):
    class DBConfig(BaseModel):
        class Settings(BaseModel):
            filepath: str = "proxy_provider_db.sqlite"
            concurrent_slots: PositiveInt = 1
        db_type: str = "sqlite"
        settings: Settings

    class ProxyConfig(BaseModel):
        class SourcesConfig(BaseModel):
            name: str
            timer: PositiveInt
            module_path: str

        class CTConfig(BaseModel):
            active_server_check_period_in_hours: PositiveInt = 1
            inactive_server_check_period_in_hours: PositiveInt = 24

        class TimeoutsConfig(BaseModel):
            connection_timeout: int = 10
            read_timeout: int = 30
        country_code_ignore_list: list[str] = ["IR", ]  # Iran
        sources: list[SourcesConfig] = []  # check the README for this setting
        checkup_timers: CTConfig
        timeouts: TimeoutsConfig
        num_of_simultaneous_checks: PositiveInt = 5

    class SystemConfig(BaseModel):
        tui_text_line_buffer_size: PositiveInt = 500
        debug: bool = False
    db: DBConfig
    proxy: ProxyConfig
    system: SystemConfig


@logger.catch()
def load_cfg():
    if not os.path.isfile("config.json"):
        with open('config.json', 'w') as config_file:
            json.dump(base_config, config_file)
        logger.info("Run without config file. Config file created")
        config = RootConfig.parse_obj(base_config)
    else:
        config = RootConfig.parse_file("config.json")
    return config

