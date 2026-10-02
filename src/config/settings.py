from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "dev"                   
    debug: bool = True

    project_root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = Path("data")

    class Config:
        env_prefix = "APP_"
        env_file = ".env"
        extra = "ignore"


settings = Settings()