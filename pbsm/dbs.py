import os
from pathlib import Path
import datetime
import tabula
from pypdf import PdfReader
import pandas as pd
import dotenv

cwd = Path(os.getcwd())
dotenv.load_dotenv()

AREA_PAYLAH_HEADER = [18.96, 7.34, 24.28, 93.47]
POSB_CREDIT_CARD_NUMBER = os.getenv("POSB_CREDIT_CARD_NUMBER")


class PdfStatement:
    def __init__(self, filepath: Path):
        self.filepath = filepath

    def parse_pdf(self, area: list[float]) -> pd.DataFrame:
        dfs = tabula.io.read_pdf(
            self.filepath,
            pages=[1],
            pandas_options={"header": None},
            area=area,  # [top, left, bottom, right]
            relative_area=True,  # enables % from area argument
        )
        if not isinstance(dfs, list):
            dfs = [pd.DataFrame()]
        return dfs[0]

    def parse_pdf_to_txt(self) -> str:
        reader = PdfReader(self.filepath)
        page = reader.pages[0]
        text = page.extract_text()
        return text

    def get_datetime_str(self) -> str:
        df = self.parse_pdf(area=AREA_PAYLAH_HEADER)
        dt_str = str(df.iloc[1, 0])
        dt_obj = datetime.datetime.strptime(dt_str, "%d %b %Y")
        return dt_obj.strftime("%Y%m%d")


class DbsStatement(PdfStatement):
    def __init__(self, filepath: Path):
        super().__init__(filepath)
        self.statement = None
        self.statement_type = self.identify_statement_type()
        match self.statement_type:
            case "creditCard":
                print("creditCard function not ready")
            case "cashback":
                print("cashback function not ready")
            case "statementOfAccounts":
                print("statementOfAccounts function not ready")
            case "paylah":
                self.statement = PaylahStatement(self.filepath)
            case _:
                raise NotImplementedError("unknown statement type")

    def identify_statement_type(self) -> str:
        raw_txt = self.parse_pdf_to_txt()
        txt = raw_txt[:1000]
        if POSB_CREDIT_CARD_NUMBER:
            if POSB_CREDIT_CARD_NUMBER in txt:
                return "creditCard"
            else:
                raise EnvironmentError("POSB_CREDIT_CARD_NUMBER")
        elif "POSB Cashback Bonus Statement" in txt:
            return "cashback"
        elif "Current and Savings Account Total" in txt:
            return "statementOfAccounts"
        elif "PayLah!" in txt:
            return "paylah"

        return "unknown"


class PaylahStatement(PdfStatement):
    def __init__(self, filepath: Path):
        super().__init__(filepath=filepath)

    def rename_filename(self) -> None:
        prefix = "paylahStatement"
        dt_str = self.get_datetime_str()
        new_name = f"{prefix}-{dt_str}{self.filepath.suffix}"
        self.filepath = self.filepath.rename(new_name)
        print(f"renamed to '{self.filepath.name}'")


def rename_consolidated_statements(path: Path):
    v = path.stem
    v = v.replace(" ", "")
    prefix = v.split("-")[0].replace(
        "ConsolidatedStatement", "OCBC_ConsolidatedStatement"
    )
    datestr = "-".join(v.split("-")[1:])
    dateobj = datetime.datetime.strptime(datestr, "%b-%y")
    newname = f"{prefix}-{dateobj.strftime('%Y_%m')}{path.suffix}"
    path.rename(newname)
    print(f"renamed {path=}")


def rename_credit_card(path: Path):
    v = path.stem.replace("OCBC GREAT EASTERN CARD-1376", "OCBC_GECard")
    prefix = v.split("-")[0]
    datestr = "-".join(v.split("-")[1:])
    dateobj = datetime.datetime.strptime(datestr, "%b-%y")
    newname = f"{prefix}-{dateobj.strftime('%Y_%m')}{path.suffix}"
    path.rename(newname)
    print(f"renamed {path=}")


def rename_paylah_statement(path: Path):
    statement = PaylahStatement(path)
    statement.rename_filename()


def main_paylah():
    # files = [x for x in cwd.glob("PDF文档-*.pdf")]
    files = [x for x in cwd.glob("paylah*.pdf")]
    for x in files:
        rename_paylah_statement(x)


def main_dbs():
    files = [x for x in cwd.glob("*.pdf")]
    for x in files:
        print(f"processing '{x.name}' ...")
        stm = DbsStatement(x)
        if stm.statement:
            stm.statement.rename_filename()


if __name__ == "__main__":
    main_paylah()
    main_dbs()
