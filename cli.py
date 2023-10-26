from pbsm.utils import init_logger
from pbsm import connect
from pbsm import bank_statement

APP_NAME = "pbsm"
lg = init_logger(APP_NAME)


def main():
    bank_statement.main()


def check_connection():
    nas_connection = connect.get_nas_path("NAS_ADDR01_SMB", "NAS_ADDR01_LOCAL")
    print(f"{nas_connection=}")


if __name__ == "__main__":
    main()
