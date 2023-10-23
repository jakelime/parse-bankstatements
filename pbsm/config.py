from enum import Enum


class BankStatementType(Enum):
    """Enum representing statement types"""

    UNKNOWN = "UnknownStatement"
    DBS_CASHBACK = "DBSCashbackStatement"
    DBS_CREDITCARD = "DBSCreditCardStatement"
    DBS_PAYLAH = "DBSPaylahStatement"
    DBS_ACCOUNT = "DBSAccountsStatement"
    UOB_CREDITCARD = "UOBCreditCardStatement"
    UOB_ACCOUNT = "UOBAccountsStatement"


class BankTransactionType(Enum):
    CREDIT = 1
    DEBIT = -1
    UNKNOWN = 0
