import os
import sys
import dotenv
from pathlib import Path

from pbsm.utils import init_logger

APP_NAME = "pbsm"
extDataDir = os.getcwd()
if getattr(sys, "frozen", False):
    extDataDir = sys._MEIPASS  # type: ignore - this is a temporary directory for pyinstaller
dotenv.load_dotenv(dotenv_path=os.path.join(extDataDir, ".env"))

lg = init_logger(APP_NAME)


def get_nas_path(
    nasDir_env_key: str = "NAS_ADDR01_SMB", localDir_env_key: str = "NAS_ADDR01_LOCAL"
):
    nasDir = os.getenv(nasDir_env_key, None)
    if not nasDir:
        raise EnvironmentError(f"missing {nasDir_env_key=}")
    localDir = os.getenv(localDir_env_key, None)
    if not nasDir:
        raise EnvironmentError(f"missing {localDir_env_key=}")
    path = Path(localDir)
    if not path.is_dir():
        raise NotADirectoryError(f"{localDir=}")
    return path


def test_nas_connection():
    kv_list = [
        ("NAS_ADDR01_SMB", "NAS_ADDR01_LOCAL"),
    ]

    paths_db = {}
    # Example .env file
    # NAS_ADDR01_SMB="smb://10.10.10.10/data"
    # NAS_ADDR01_LOCAL="/Volumes/data"

    for key, value in kv_list:
        k = os.getenv(key, None)
        if not k:
            raise EnvironmentError(f"missing {key=}")
        v = os.getenv(value, None)
        if not v:
            raise EnvironmentError(f"missing {value=}")
        paths_db[k] = v

    for smb_addr, local_addr in paths_db.items():
        local_path = Path(local_addr)
        if local_path.is_dir():
            lg.info(f"already mounted - {local_path=}")
        else:
            command = f"osascript -e 'mount volume \"{smb_addr}\"'"
            returncode = os.system(command)
            if returncode == 0 and local_path.is_dir():
                lg.info(f"mounted successfully - {local_path=}")
            else:
                lg.error(f"mounting ({smb_addr} failed. {returncode=}, \n{command=})")
