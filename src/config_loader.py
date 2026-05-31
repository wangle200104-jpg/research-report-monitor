"""Configuration loader / 配置加载模块"""
import os
import yaml


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml"
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_keywords(config: dict) -> list:
    return config.get("keywords", [])


def get_download_dir(config: dict) -> str:
    output_dir = config.get("download", {}).get("output_dir", "./reports")
    if not os.path.isabs(output_dir):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, output_dir)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir
