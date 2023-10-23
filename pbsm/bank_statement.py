import fnmatch
import os
import datetime
import math
from pathlib import Path
from dataclasses import dataclass
from decimal import Decimal

import tabula
from pypdf import PdfReader
import pandas as pd
import dotenv

if __name__ == "__main__":
    import utils
    from config import BankStatementType as Stm
    from config import BankTransactionType as Btt

else:
    from pbsm import utils
    from pbsm.config import BankStatementType as Stm
    from pbsm.config import BankTransactionType as Btt


APP_NAME = "pbsm"
AREA_PAYLAH_HEADER = [18.96, 7.34, 24.28, 93.47]
AREA_PAYLAH_PG1 = [37.53, 8.38, 95.4, 94.02]
AREA_PAYLAH_PG2 = [15.01, 6.85, 93.93, 94.18]
COLUMNS_BOUNDARY_PAYLAH = [15.2, 80.48]

dotenv.load_dotenv()
lg = utils.init_logger(APP_NAME)


@dataclass
class DataRow:
    date: datetime.datetime
    descr: str
    amount: Decimal
    reference_number: str
    reference_filename: str


class PdfStatement:
    def __init__(self, filepath: Path):
        self.statement_date = datetime.datetime(1, 1, 1)
        self.filepath = filepath
        self.prefix = "nil"
        self.POSB_CREDIT_CARD_NUMBER = os.getenv("POSB_CREDIT_CARD_NUMBER", default="")
        if not self.POSB_CREDIT_CARD_NUMBER:
            lg.warning("Environment variable 'POSB_CREDIT_CARD_NUMBER' not configured")

    def parse_pdf_to_dataframe(self, area: list[float]) -> pd.DataFrame:
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

    def get_datetime_str(self, area: list[float]) -> str:
        df = self.parse_pdf_to_dataframe(area=area)
        dt_str = str(df.iloc[1, 0])
        self.statement_date = datetime.datetime.strptime(dt_str, "%d %b %Y")
        return self.statement_date.strftime("%Y%m%d")

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
            and (self.POSB_CREDIT_CARD_NUMBER)
            and (self.POSB_CREDIT_CARD_NUMBER in txt)
        ):
            return Stm.DBS_CREDITCARD
        elif "Current and Savings Account" in txt:
            return Stm.DBS_ACCOUNT
        elif "PayLah!" in txt:
            return Stm.DBS_PAYLAH

        return Stm.UNKNOWN


class DbsPaylahStatement(PdfStatement):
    def __init__(self, filepath: Path):
        super().__init__(filepath)
        self.HEADER_AREA = AREA_PAYLAH_HEADER
        self.prefix = Stm.DBS_PAYLAH
        self.statement_date_str = self.get_datetime_str(
            area=self.HEADER_AREA
        )  # run this to set dt_object
        self.WALLET_NUMBER = os.getenv("PAYLAH_WALLET_NUMBER", "")
        if not self.WALLET_NUMBER:
            raise EnvironmentError("missing 'PAYLAH_WALLET_NUMBER'")

    def get_transaction_lines(self) -> list[str]:
        starter_line = f"PayLah! Wallet No. {self.WALLET_NUMBER}"
        reader = PdfReader(self.filepath)
        header_page_line = (0, 0)
        is_useful_toggle = False  # switch to True, then append to useful_text
        is_transactions_end = False
        is_transactions_start = False
        trasactions_textlines = []

        for pg_no, pg in enumerate(reader.pages):
            if is_transactions_end:
                break
            text = pg.extract_text()
            for line_no, line in enumerate(text.splitlines()):
                if is_transactions_end:
                    break

                if not is_useful_toggle:
                    if starter_line in line:
                        is_useful_toggle = True
                        header_page_line = pg_no, line_no - 1
                    continue

                if "NEW TRANSACTION" in line:
                    is_transactions_start = True
                    continue

                if is_transactions_start:
                    if line[:5] == "Total":
                        is_transactions_end = True
                        continue
                    trasactions_textlines.append(line)
                    continue

        header = (
            reader.pages[header_page_line[0]]
            .extract_text()
            .splitlines()[header_page_line[1]]
        )
        trasactions_textlines.insert(0, header)
        return trasactions_textlines

    def algorithm_text_to_data(self) -> pd.DataFrame:
        """This algorithm is aborted because reference number varies in length
        # e.g. transaction number: 01689999990329103390492 4.50 CR
        # e.g. transaction number: 48985721688828929266 200.00 CR
        # e.g. transaction number: IPS69330326152174285 30.00 DB
        # e.g. transaction number: MB124510692040L54 200.00 CR
        """

        textlist = self.get_transaction_lines()

        if len(textlist) == 1:
            lg.warning(f"empty transactions detected in {self.filepath.name}")
            datarows = [
                DataRow(
                    date=self.statement_date,
                    descr="error",  # type: ignore
                    amount=Decimal("0.00"),
                    reference_number="nil",
                    reference_filename=self.filepath.name,
                )
            ]
            return pd.DataFrame(datarows)

        datarows = []
        it_txtlist = iter(textlist)
        _ = next(it_txtlist)  # header

        dt_obj = None
        descr = None
        amt = None
        amt_type = None

        line = next(it_txtlist)
        while line:
            try:
                if not dt_obj:
                    try:
                        datestr = f"{line[:6]} {self.statement_date.year}"
                        dt_obj = datetime.datetime.strptime(datestr, "%d %b %Y")

                        descr = line[6:]
                    except ValueError:
                        dt_obj = None
                        descr = None
                    finally:
                        line = next(it_txtlist)
                        continue

                line = line.replace("REF NO:. ", "").strip()

                match line[:2]:
                    case "MB":
                        # e.g. transaction number: MB124510692040L542
                        value_str, amt_type = line.split(" ")
                        ref_no = value_str[:19]
                        amt = Decimal(value_str[19:])
                    case _:
                        # e.g. transaction number: 01689999990329103390492 4.50 CR
                        # e.g. transaction number: 48985721688828929266 200.00 CR
                        # e.g. transaction number: 016899999904092003345262
                        value_str, amt_type = line.split(" ")
                        ref_no = value_str[:23]
                        amt = Decimal(value_str[23:])

                match amt_type:
                    case "DB":
                        amt_type = Btt.DEBIT
                    case "CR":
                        amt_type = Btt.CREDIT
                    case _:
                        amt_type = Btt.UNKNOWN

                datarows.append(
                    DataRow(
                        date=dt_obj,
                        descr=descr.strip(),  # type: ignore
                        amount=amt_type.value * amt,
                        reference_number=ref_no,
                        reference_filename=self.filepath.name,
                    )
                )
                dt_obj = None
                descr = None
                line = next(it_txtlist)
                continue
            except StopIteration:
                break

        df = pd.DataFrame(datarows)

        return df

    def algorithm_table_to_data(self):
        reader = PdfReader(self.filepath)
        dflist = []
        is_last_page = False
        for pg_no in range(1, len(reader.pages) + 1):
            match pg_no:
                case 1:
                    area = AREA_PAYLAH_PG1
                case _:
                    area = AREA_PAYLAH_PG2

            dfs = tabula.io.read_pdf(
                self.filepath,
                pages=[pg_no],
                pandas_options={"header": None},
                columns=COLUMNS_BOUNDARY_PAYLAH,
                relative_columns=True,
                area=area,  # [top, left, bottom, right]
                relative_area=True,  # enables % from area argument
            )
            df = dfs[0]
            series_findlast = df[df.columns[1]].str.contains("Total :").loc[lambda x: x]

            # determine if we have reached the last page
            if series_findlast.empty and not is_last_page:
                dflist.append(df)
                # print(df)
                continue

            elif not series_findlast.empty:
                is_last_page = True
                last_row_index = series_findlast.index[-1]
                # lg.debug(f"{last_row_index=}")
                df = df.iloc[:last_row_index, :]
                dflist.append(df)

            break

        df = pd.concat(dflist).reset_index(drop=True)

        ## Remove errored dataframe due to empty transaction records
        if df[df.columns[1]].str.contains("INFORMATION ON YOUR DBS PAYLAH!").any():
            return pd.DataFrame()

        dt_obj = None
        descr = None
        amt = None
        amt_type = None
        reference_no = None

        datarows = []
        dfiter = df.itertuples()
        while (row := next(dfiter, None)) is not None:
            # print(f"{row._1=}, {row._2=}, {row._3=}")
            if not dt_obj:
                datestr = f"{row._1} {self.statement_date.year}"
                # dt_obj = datetime.datetime.strptime(datestr, "%d %b")
                dt_obj = datetime.datetime.strptime(datestr, "%d %b %Y")
                descr = row._2
                amt, amt_type = row._3.split(" ")
                match amt_type:
                    case "DB":
                        amt_type = Btt.DEBIT
                    case "CR":
                        amt_type = Btt.CREDIT
                    case _:
                        amt_type = Btt.UNKNOWN
                amt = Decimal(amt) * amt_type.value
            elif math.isnan(row._1):
                reference_no = row._2.replace("REF NO:.", "").strip()
                datarows.append(
                    DataRow(
                        date=dt_obj,
                        descr=descr,
                        amount=amt,
                        reference_number=reference_no,
                        reference_filename=self.filepath.name,
                    )
                )
                dt_obj = None
                descr = None
                amt = None
                amt_type = None
                reference_no = None
        df = pd.DataFrame(datarows)

        return df

    def parse_transaction_to_dataframe(self) -> pd.DataFrame:
        # df = self.algorithm_text_to_data()
        df = self.algorithm_table_to_data()
        return df

    def rename_filename(self) -> None:
        dt_str = self.get_datetime_str(self.HEADER_AREA)
        new_name = f"{self.prefix}-{dt_str}{self.filepath.suffix}"
        self.filepath = self.filepath.rename(new_name)
        lg.info(f"renamed to '{self.filepath.name}'")


def main():
    pathfinder = utils.PathFinder()

    dflist = []
    try:
        for fp in pathfinder.get_pdf_files():
            statement = PdfStatement(filepath=fp)
            stm_type = statement.get_statement_type()
            lg.info(f"{fp.stem} is {stm_type}")

            match stm_type:
                case Stm.DBS_PAYLAH:
                    statement = DbsPaylahStatement(statement.filepath)
                    df = statement.parse_transaction_to_dataframe()
                    dflist.append(df)
                case _:
                    lg.warning(f"{stm_type} not implemented yet")

            # TODO:
            # break
    except Exception as e:
        lg.error(f"{e=}, {statement.filepath=}", exc_info=True)
    finally:
        pass
        if dflist:
            df = pd.concat(dflist)
            print(df)
            df.to_excel("output-paylah_statements.xlsx")


if __name__ == "__main__":
    pd.set_option("display.max_rows", None)
    main()
