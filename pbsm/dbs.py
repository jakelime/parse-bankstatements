import fnmatch
import os
import re
from pathlib import Path
import datetime
from dataclasses import dataclass

import tabula
from pypdf import PdfReader
import pandas as pd
import dotenv
import regex_spm

if __name__ == "__main__":
    import utils
else:
    from pbsm import utils


dotenv.load_dotenv()

APP_NAME = "pbsm"
AREA_PAYLAH_HEADER = [18.96, 7.34, 24.28, 93.47]
POSB_CREDIT_CARD_NUMBER = os.getenv("POSB_CREDIT_CARD_NUMBER")

lg = utils.init_logger(APP_NAME)


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
                lg.warning("creditCard function not ready")
            case "cashback":
                lg.warning("cashback function not ready")
            case "statementOfAccounts":
                lg.warning("statementOfAccounts function not ready")
            case "paylah":
                self.statement = PaylahStatement(self.filepath)
            case _:
                raise NotImplementedError("unknown statement type")

    def identify_statement_type(self) -> str:
        # Filename patter matching
        if fnmatch.fnmatch(self.filepath.name, "PDF文档*.pdf"):
            return "paylah"
        # TODO: add more file patterns

        raw_txt = self.parse_pdf_to_txt()
        txt = raw_txt[:1000]
        if POSB_CREDIT_CARD_NUMBER:
            if POSB_CREDIT_CARD_NUMBER in txt:
                return "creditCard"
        elif "POSB Cashback Bonus Statement" in txt:
            return "cashback"
        elif "Current and Savings Account Total" in txt:
            return "statementOfAccounts"
        elif "PayLah!" in txt:
            return "paylah"

        return "unknown"

    def rename_consolidated_statements(self):
        v = self.filepath.stem
        v = v.replace(" ", "")
        prefix = v.split("-")[0].replace(
            "ConsolidatedStatement", "OCBC_ConsolidatedStatement"
        )
        datestr = "-".join(v.split("-")[1:])
        dateobj = datetime.datetime.strptime(datestr, "%b-%y")
        newname = f"{prefix}-{dateobj.strftime('%Y_%m')}{self.filepath.suffix}"
        self.filepath = self.filepath.rename(newname)
        lg.info(f"renamed to '{self.filepath.name}'")


class PaylahStatement(PdfStatement):
    def __init__(self, filepath: Path):
        super().__init__(filepath=filepath)

    def rename_filename(self) -> None:
        prefix = "paylahStatement"
        dt_str = self.get_datetime_str()
        new_name = f"{prefix}-{dt_str}{self.filepath.suffix}"
        self.filepath = self.filepath.rename(new_name)
        lg.info(f"renamed to '{self.filepath.name}'")


def main():
    pathfinder = utils.PathFinder()
    files = pathfinder.get_pdf_files()
    [print(x) for x in files]

    stm = DbsStatement(filepath=files[1])
    print(stm.identify_statement_type())


if __name__ == "__main__":
    main()
