from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    telegram_api_base_url: str = Field(default="https://api.telegram.org", alias="TELEGRAM_API_BASE_URL")
    telegram_api_is_local: bool = Field(default=False, alias="TELEGRAM_API_IS_LOCAL")
    telegram_upload_timeout: int = Field(default=900, ge=30, alias="TELEGRAM_UPLOAD_TIMEOUT")
    telegram_upload_retries: int = Field(default=4, ge=1, le=10, alias="TELEGRAM_UPLOAD_RETRIES")

    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="playdl", alias="MONGODB_DB_NAME")
    tools_dir: Path = Field(default=Path("tools"), alias="TOOLS_DIR")
    download_dir: Path = Field(default=Path("storage/downloads"), alias="DOWNLOAD_DIR")
    max_parallel_jobs: int = Field(default=4, ge=1, le=20, alias="MAX_PARALLEL_JOBS")

    auto_install_tools: bool = Field(default=True, alias="AUTO_INSTALL_TOOLS")
    play_downloader_backend: str = Field(default="auto", alias="PLAY_DOWNLOADER_BACKEND")
    play_downloader_cmd: str | None = Field(default=None, alias="PLAY_DOWNLOADER_CMD")
    alltech_gplay_path: Path = Field(
        default=Path("tools/gplay-apk-downloader/gplay"),
        alias="ALLTECH_GPLAY_PATH",
    )
    alltech_auto_auth: bool = Field(default=True, alias="ALLTECH_AUTO_AUTH")
    alltech_auth_file: Path = Field(default=Path("~/.gplay-auth.json"), alias="ALLTECH_AUTH_FILE")
    play_arch: str = Field(default="arm64", alias="PLAY_ARCH")
    merge_splits: bool = Field(default=True, alias="MERGE_SPLITS")
    apkeep_path: Path = Field(default=Path("tools/apkeep"), alias="APKEEP_PATH")
    apkeep_source: str | None = Field(default=None, alias="APKEEP_SOURCE")
    apkeep_fallback_source: str = Field(default="apk-pure", alias="APKEEP_FALLBACK_SOURCE")
    apkeep_email: str | None = Field(default=None, alias="APKEEP_EMAIL")
    apkeep_token: str | None = Field(default=None, alias="APKEEP_TOKEN")

    apkeditor_jar: Path = Field(default=Path("tools/APKEditor.jar"), alias="APKEDITOR_JAR")
    apks_to_apk_cmd: str | None = Field(default=None, alias="APKS_TO_APK_CMD")
    sign_apk_cmd: str | None = Field(default=None, alias="SIGN_APK_CMD")
    apksigner_jar: Path = Field(default=Path("tools/uber-apk-signer.jar"), alias="APKSIGNER_JAR")
    auto_sign_apk: bool = Field(default=True, alias="AUTO_SIGN_APK")

    nixfile_username: str | None = Field(default=None, alias="NIXFILE_USERNAME")
    nixfile_pass: str | None = Field(default=None, alias="NIXFILE_PASS")
    nixfile_login_url: str = Field(
        default="https://panel.nixfile.com/auth/login",
        alias="NIXFILE_LOGIN_URL",
    )
    nixfile_panel_url: str = Field(
        default="https://panel.nixfile.com",
        alias="NIXFILE_PANEL_URL",
    )
    nixfile_headless: bool = Field(default=True, alias="NIXFILE_HEADLESS")
    nixfile_proxy: str | None = Field(default=None, alias="NIXFILE_PROXY")
    nixfile_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        alias="NIXFILE_USER_AGENT",
    )
    nixfile_upload_timeout: int = Field(default=600, alias="NIXFILE_UPLOAD_TIMEOUT")
    nixfile_session_file: Path = Field(
        default=Path("storage/nixfile-session.json"),
        alias="NIXFILE_SESSION_FILE",
    )
    limit_daily_ir: int = Field(default=0, ge=0, alias="LIMIT_DAILY_IR")

    downloads_max_mb: int = Field(default=500, ge=1, alias="DOWNLOADS_MAX_MB")
    keep_files: bool = Field(default=True, alias="KEEP_FILES")
    rar_path: str = Field(default="rar", alias="RAR_PATH")
    downloads_sweep_interval_s: int = Field(default=3600, ge=60, alias="DOWNLOADS_SWEEP_INTERVAL_S")
    nixfile_link_check_interval_s: int = Field(default=21600, ge=60, alias="NIXFILE_LINK_CHECK_INTERVAL_S")
    nixfile_max_file_mb: int = Field(default=100, ge=1, alias="NIXFILE_MAX_FILE_MB")

    rubika_session_name: str = Field(default="playdl_rubika", alias="RUBIKA_SESSION_NAME")
    rubika_session_dir: Path = Field(default=Path("storage"), alias="RUBIKA_SESSION_DIR")
    rubika_max_file_mb: int = Field(default=500, ge=1, alias="RUBIKA_MAX_FILE_MB")
    rubika_upload_timeout: int = Field(default=900, ge=30, alias="RUBIKA_UPLOAD_TIMEOUT")


def load_settings() -> Settings:
    settings = Settings()
    settings.tools_dir.mkdir(parents=True, exist_ok=True)
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    return settings
