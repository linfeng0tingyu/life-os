from __future__ import annotations

from flask import Blueprint, request

from life_os.api import json_object, query_bool, success_response
from life_os.serializers import (
    finance_account_data,
    finance_summary_data,
    finance_transaction_data,
)
from life_os.services.common import ValidationError
from life_os.services.finance_service import FinanceService


blueprint = Blueprint("finance", __name__)
ACCOUNT_CREATE_FIELDS = {
    "name",
    "kind",
    "account_type",
    "opening_balance",
    "currency",
    "sort_order",
}
ACCOUNT_UPDATE_FIELDS = (
    ACCOUNT_CREATE_FIELDS - {"currency"}
) | {"active"}
TRANSACTION_CREATE_FIELDS = {
    "date",
    "type",
    "amount",
    "from_account_id",
    "to_account_id",
    "category",
    "description",
    "note",
}


@blueprint.get("/api/finance/accounts")
def get_accounts():
    accounts = FinanceService.list_accounts(
        include_inactive=query_bool("include_inactive")
    )
    return success_response([finance_account_data(account) for account in accounts])


@blueprint.post("/api/finance/accounts")
def post_account():
    payload = json_object(
        allowed=ACCOUNT_CREATE_FIELDS,
        required={"name", "kind", "account_type"},
    )
    account = FinanceService.create_account(**payload)
    return success_response(finance_account_data(account), status=201)


@blueprint.put("/api/finance/accounts/<int:account_id>")
def put_account(account_id: int):
    payload = json_object(allowed=ACCOUNT_UPDATE_FIELDS, require_any=True)
    account = FinanceService.update_account(account_id, **payload)
    return success_response(finance_account_data(account))


@blueprint.get("/api/finance/transactions")
def get_transactions():
    account_id = request.args.get("account_id")
    if account_id is not None:
        try:
            normalized_account_id = int(account_id)
        except ValueError as exc:
            raise ValidationError("account_id 必须是正整数。") from exc
    else:
        normalized_account_id = None
    transactions = FinanceService.list_transactions(
        value_date=request.args.get("date"),
        transaction_type=request.args.get("type"),
        account_id=normalized_account_id,
        include_archived=query_bool("include_archived"),
    )
    return success_response(
        [finance_transaction_data(item) for item in transactions]
    )


@blueprint.post("/api/finance/transactions")
def post_transaction():
    payload = json_object(
        allowed=TRANSACTION_CREATE_FIELDS,
        required={"date", "type", "amount"},
    )
    payload["value_date"] = payload.pop("date")
    payload["transaction_type"] = payload.pop("type")
    transaction = FinanceService.create_transaction(**payload)
    return success_response(finance_transaction_data(transaction), status=201)


@blueprint.put("/api/finance/transactions/<int:transaction_id>")
def put_transaction(transaction_id: int):
    payload = json_object(
        allowed=TRANSACTION_CREATE_FIELDS, require_any=True
    )
    if "date" in payload:
        payload["value_date"] = payload.pop("date")
    if "type" in payload:
        payload["transaction_type"] = payload.pop("type")
    transaction = FinanceService.update_transaction(transaction_id, **payload)
    return success_response(finance_transaction_data(transaction))


@blueprint.delete("/api/finance/transactions/<int:transaction_id>")
def delete_transaction(transaction_id: int):
    transaction = FinanceService.archive_transaction(transaction_id)
    return success_response(finance_transaction_data(transaction))


@blueprint.get("/api/finance/summary")
def get_summary():
    summary = FinanceService.summary(
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
    )
    return success_response(finance_summary_data(summary))
