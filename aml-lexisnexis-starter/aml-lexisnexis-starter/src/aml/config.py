
from dataclasses import dataclass

@dataclass
class Columns:
    # transactions
    txn_id: str = "txn_id"
    customer_id: str = "customer_id"
    account_id: str = "account_id"
    datetime: str = "datetime"
    amount: str = "amount"
    currency: str = "currency"
    channel: str = "channel"
    counterparty_id: str = "counterparty_id"
    counterparty_country: str = "counterparty_country"
    mcc: str = "mcc"
    description: str = "description"

    # lexisnexis (enrichment)
    ln_customer_id: str = "customer_id"
    pep_flag: str = "pep_flag"
    sanctions_flag: str = "sanctions_flag"
    adverse_media_score: str = "adverse_media_score"
    risk_rating: str = "risk_rating"
    kyc_last_review_date: str = "kyc_last_review_date"


C = Columns()
