from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    gemini_api_key: str
    gcp_project_id: str
    bq_dataset_id: str = "market_intelligence"
    bq_table_id: str = "anomalies"

    # Automatically loads from a .env file if it exists
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()