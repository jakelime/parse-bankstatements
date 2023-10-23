import fnmatch
import os
import datetime
from enum import Enum
from pathlib import Path

import tabula
from pypdf import PdfReader
import pandas as pd
import dotenv


if __name__ == "__main__":
    import utils
else:
    from pbsm import utils


APP_NAME = "pbsm"
AREA_PAYLAH_HEADER = [18.96, 7.34, 24.28, 93.47]
POSB_CREDIT_CARD_NUMBER = os.getenv("POSB_CREDIT_CARD_NUMBER")

dotenv.load_dotenv()
lg = utils.init_logger(APP_NAME)


class Stm(Enum):
    """Enum representing statement types"""

    UNKNOWN = "UnknownStatement"
    DBS_CASHBACK = "DBSCashbackStatement"
    DBS_CREDITCARD = "DBSCreditCardStatement"
    DBS_PAYLAH = "DBSPaylahStatement"
    DBS_ACCOUNT = "DBSAccountsStatement"
    UOB_CREDITCARD = "UOBCreditCardStatement"
    UOB_ACCOUNT = "UOBAccountsStatement"


class PdfStatement:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.prefix = "nil"

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

    def get_statement_type(self) -> Stm:
        # Filename patter matching
        if fnmatch.fnmatch(self.filepath.name, "PDF文档*.pdf"):
            return Stm.DBS_PAYLAH

        # Pdf file content keywords search
        raw_txt = self.parse_pdf_to_txt()
        txt = raw_txt[:1000]
        if "POSB Cashback Bonus Statement" in txt:
            return Stm.DBS_CASHBACK
        elif (
            ("POSB everyday CARD NO.:" in txt)
            and (POSB_CREDIT_CARD_NUMBER)
            and (POSB_CREDIT_CARD_NUMBER in txt)
        ):
            return Stm.DBS_CREDITCARD
        elif "Current and Savings Account" in txt:
            return Stm.DBS_ACCOUNT
        elif "PayLah!" in txt:
            return Stm.DBS_PAYLAH

        return Stm.UNKNOWN

    def rename_filename(self) -> None:
        dt_str = self.get_datetime_str()
        new_name = f"{self.prefix}-{dt_str}{self.filepath.suffix}"
        self.filepath = self.filepath.rename(new_name)
        lg.info(f"renamed to '{self.filepath.name}'")


class DbsPaylahStatement(PdfStatement):
    def __init__(self, filepath: Path):
        super().__init__(filepath)
        self.prefix = Stm.DBS_PAYLAH


def main():
    pathfinder = utils.PathFinder()

    for fp in pathfinder.get_pdf_files():
        statement = PdfStatement(filepath=fp)
        stm_type = statement.get_statement_type()
        lg.info(f"{fp.stem} is {stm_type}")


if __name__ == "__main__":
    main()
