from app.models.login_data import LoginData

def parse_login_data(data: bytes) -> LoginData:
    (
        username,
        password_md5,
        remainder,
    ) = data.decode().split("\n", maxsplit=2)

    (
        osu_version,
        utc_offset,
        display_city,
        client_hashes,
        pm_private,
    ) = remainder.split("|", maxsplit=4)

    (
        osu_path_md5,
        adapters_str,
        adapters_md5,
        uninstall_md5,
        disk_signature_md5,
    ) = client_hashes[:-1].split(":", maxsplit=4)
    
    return LoginData(
        username=username,
        password_md5=password_md5,
        osu_version=osu_version,
        utc_offset=int(utc_offset),
        display_city=bool(int(display_city)),
        pm_private=bool(int(pm_private)),
        client_md5=osu_path_md5,
        adapters_str=adapters_str,
        adapters_md5=adapters_md5,
        uninstall_md5=uninstall_md5,
        disk_signature_md5=disk_signature_md5,
    )