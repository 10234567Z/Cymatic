from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str  

    # Turnkey
    TURNKEY_API_PUBLIC_KEY: str
    TURNKEY_API_PRIVATE_KEY: str
    TURNKEY_ORG_ID: str

    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str

    # App
    BASE_URL: str  # your public ngrok/server URL e.g. https://abc.ngrok.io
    PLATFORM_AGENTS_URL: str = "http://127.0.0.1:8100"

    class Config:
        env_file = ".env"


settings = Settings()
