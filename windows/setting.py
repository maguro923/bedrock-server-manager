import re
from dataclasses import dataclass
from pathlib import Path
import tomllib

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_CONFIG_PATH = Path(__file__).with_name("config.toml")


@dataclass(frozen=True)
class Settings:
    server_path: Path
    world_name: str
    emergency_backup_path: Path
    backup_times: list[str]
    restart_time: str
    update_check_time: str
    max_backups: int

    # 派生パス（base から組み立てる。個別にずらす必要が出たら設定項目化する）
    @property
    def backup_path(self) -> Path: return self.server_path / "backup"
    @property
    def log_path(self) -> Path: return self.server_path / "logs" / "server.log"
    @property
    def error_log_path(self) -> Path: return self.server_path / "logs" / "error.log"


def _require(section: dict, key: str, section_name: str):
    if key not in section:
        raise ValueError(f"config.toml: [{section_name}] に {key} がありません")
    return section[key]


def _check_time(value, key: str) -> str:
    if not isinstance(value, str) or not _TIME_RE.match(value):
        raise ValueError(f"config.toml: {key} は HH:MM 形式で書いてください（現在値: {value!r}）")
    return value


def load_settings(path: Path = _CONFIG_PATH) -> Settings:
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
    with path.open("rb") as f:
        raw = tomllib.load(f)

    server = raw.get("server", {})
    schedule = raw.get("schedule", {})
    backup = raw.get("backup", {})

    backup_times = list(
        _check_time(t, "schedule.backup_times")
        for t in _require(schedule, "backup_times", "schedule")
    )
    max_backups = _require(backup, "max_backups", "backup")
    if not isinstance(max_backups, int) or max_backups < 1:
        raise ValueError("config.toml: [backup] max_backups は1以上の整数にしてください")

    return Settings(
        server_path=Path(_require(server, "base_path", "server")),
        world_name=_require(server, "world_name", "server"),
        emergency_backup_path=Path(_require(server, "emergency_backup_path", "server")),
        backup_times=backup_times,
        restart_time=_check_time(_require(schedule, "restart_time", "schedule"), "schedule.restart_time"),
        update_check_time=_check_time(_require(schedule, "update_check_time", "schedule"), "schedule.update_check_time"),
        max_backups=max_backups,
    )
