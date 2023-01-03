from dataclasses import dataclass

@dataclass
class LoginData:
    username: str
    password_md5: str
    osu_version: str
    utc_offset: int
    display_city: bool
    pm_private: bool
    client_md5: str
    adapters_str: str
    adapters_md5: str
    uninstall_md5: str
    disk_signature_md5: str