from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
import json
from accounts.models import Account
from transactions.models import Transaction
from django.utils.timezone import now
from django.db import transaction as db_transaction, OperationalError, DatabaseError, connection
from django.db.utils import IntegrityError
from authentication.auth import jwt_required
import logging
from telemetry.setup import meter

logger = logging.getLogger(__name__)

# OpenTelemetry Counter 정의
transaction_counter = meter.create_counter(
    name="transaction_count",
    description="Count of successful transactions",
)
import time

class DepositView(APIView):
    @method_decorator(jwt_required)
    def post(self, request):
        try:
            data = json.loads(request.body)
            transaction_id = data.get("transaction_id")
            account_number = data.get("account_number")
            amount = int(data.get("amount", 0))
            memo = data.get("memo", "입금")

            if amount <= 0:
                logger.warning(f"[deposit] Invalid amount: {amount}")
                return Response({"success": False, "message": "[ERROR] Invalid amount"}, status=400)
            
            if Transaction.objects.filter(transaction_id=transaction_id).exists():
                return JsonResponse({"success": False, "message": "[ERROR] Duplicate transaction"}, status=409)

            with db_transaction.atomic():
                account = Account.objects.select_for_update.get(account_number=account_number)
                if account.status == "CLOSED":
                    return Response({"success": False, "message": "[ERROR] 계좌가 비활성되어 있습니다."}, status=400)

                account.balance += amount
                account.save()

                transaction = Transaction.objects.create(
                    transaction_id=transaction_id,
                    type="DEPOSIT",
                    status="SUCCESS",
                    to_account=account,
                    amount=amount,
                    balance_after=account.balance,
                    memo=memo,
                )

                logger.info(f"[deposit] Success | transaction_id: {transaction.transaction_id}, balance: {account.balance}")
                logger.info(f"[{transaction.type.lower()}] Success | transaction_id: %s", transaction.transaction_id)
                transaction_counter.add(1, {"type": "deposit", "status": "success"})

                return Response({
                    "success": True,
                    "transaction": {
                        "transaction_id": str(transaction.transaction_id),
                        "type": "deposit",
                        "to_account": account.account_number,
                        "amount": transaction.amount,
                        "balance_after": transaction.balance_after,
                        "timestamp": transaction.created_at.isoformat(),
                        "memo": transaction.memo,
                        "status": transaction.status,
                    }
                })
        except Account.DoesNotExist:
            logger.error(f"[deposit] Account not found: {account_number}")
            transaction_counter.add(1, {"type": "deposit", "status": "fail"})
            return JsonResponse({"success": False, "message": "[ERROR] Account not found"}, status=404)
        except json.JSONDecodeError:
            logger.error("[deposit] JSON Decode Error", exc_info=True)
            return JsonResponse({"success": False, "message": "[ERROR] Invalid JSON"}, status=400)
        except Exception as e:
            logger.exception(f"[deposit] Unexpected Error: {str(e)}")
            transaction_counter.add(1, {"type": "deposit", "status": "fail"})
            return Response({"success": False, "message": f"[ERROR] {str(e)}"}, status=500)

class WithdrawView(APIView):
    @method_decorator(jwt_required)
    def post(self, request):
        try:
            data = request.data
            transaction_id = data.get("transaction_id")
            account_number = data.get("account_number")
            amount = int(data.get("amount", 0))
            memo = data.get("memo", "출금")

            logger.info(f"[withdraw] Request received | account: {account_number}, amount: {amount}")

            if amount <= 0:
                return Response({"success": False, "message": "[ERROR] Invalid amount"}, status=400)
            
            if Transaction.objects.filter(transaction_id=transaction_id).exists():
                return JsonResponse({"success": False, "message": "[ERROR] Duplicate transaction"}, status=409)


            with db_transaction.atomic():
                account = Account.objects.select_for_update.get(account_number=account_number)
                if account.status == "CLOSED":
                    return JsonResponse({"success": False, "message": "[ERROR] 계좌가 비활성되어 있습니다."}, status=400)
                
                if account.balance < amount:
                    logger.warning(f"[withdraw] Insufficient balance | account: {account_number}, balance: {account.balance}, attempted: {amount}")
                    transaction_counter.add(1, {"type": "withdraw", "status": "fail"})
                    return JsonResponse({"success": False, "message": "[ERROR] Insufficient balance"}, status=400)
                
                account.balance -= amount
                account.save()

                transaction = Transaction.objects.create(
                    transaction_id=transaction_id,
                    type="WITHDRAWAL",
                    status="SUCCESS",
                    from_account=account,
                    amount=amount,
                    balance_after=account.balance,
                    memo=memo,
                )

                logger.info(f"[withdraw] Success | transaction_id: {transaction.transaction_id}, balance: {account.balance}")
                logger.info(f"[{transaction.type.lower()}] Success | transaction_id: %s", transaction.transaction_id)
                transaction_counter.add(1, {"type": "withdraw", "status": "success"})

                return JsonResponse({
                    "success": True,
                    "transaction": {
                        "transaction_id": str(transaction.transaction_id),
                        "type": "withdrawal",
                        "from_account": account.account_number,
                        "amount": transaction.amount,
                        "balance_after": transaction.balance_after,
                        "timestamp": transaction.created_at.isoformat(),
                        "memo": transaction.memo,
                        "status": transaction.status,
                    }
                })
        except Account.DoesNotExist:
            logger.error(f"[withdraw] Account not found: {account_number}")
            transaction_counter.add(1, {"type": "withdraw", "status": "fail"})
            return JsonResponse({"success": False, "message": "[ERROR] Account not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "[ERROR] Invalid JSON"}, status=400)
        except Exception as e:
            logger.exception(f"[withdraw] Unexpected Error: {str(e)}")
            transaction_counter.add(1, {"type": "withdraw", "status": "fail"})
            return JsonResponse({"success": False, "message": f"[ERROR] {str(e)}"}, status=500)

class TransferView(APIView):
    @method_decorator(jwt_required)
    def post(self, request):
        try:
            data = request.data
            transaction_id = data.get("transaction_id")
            from_account_number = data.get("from_account")
            to_account_number = data.get("to_account")
            amount = int(data.get("amount", 0))
            memo = data.get("memo", "송금")

            logger.info(f"[transfer] Request received | from: {from_account_number}, to: {to_account_number}, amount: {amount}")

            if amount <= 0:
                logger.warning(f"[transfer] Invalid amount: {amount}")
                return JsonResponse({"success": False, "message": "[ERROR] Invalid amount"}, status=400)

            if from_account_number == to_account_number:
                logger.warning(f"[transfer] Same account transfer attempt: {from_account_number}")
                return JsonResponse({"success": False, "message": "[ERROR] Cannot transfer to the same account"}, status=400)

            for attempt in range(3):
                try:
                    with db_transaction.atomic():
                        
                        if Transaction.objects.filter(transaction_id=transaction_id).exists():
                            return JsonResponse({"success": False, "message": "[ERROR] Duplicate transaction"}, status=409)

                        # 락 대기시간을 5초로 변경
                        with connection.cursor() as cursor:
                            cursor.execute("SET innodb_lock_wait_timeout = 5")  # 5초로 세션 설정 변경

                        try:
                            # 계좌 접근에 Lock 걸기(select_for_update)
                            from_account = Account.objects.select_for_update().get(account_number=from_account_number)
                            to_account = Account.objects.select_for_update().get(account_number=to_account_number)
                        except Account.DoesNotExist:
                            logger.error(f"[transfer] Account not found: from: {from_account_number}, to: {to_account_number}")
                            transaction_counter.add(1, {"type": "transfer", "status": "fail"})
                            return JsonResponse({"success": False, "message": "[ERROR] One or both accounts not found"}, status=404)
                        
                        if from_account.status == "CLOSED" or to_account.status == "CLOSED":
                            return Response({"success": False, "message": "[ERROR] 계좌가 비활성되어 있습니다."}, status=400)

                        if from_account.balance < amount:
                            logger.warning(f"[transfer] Insufficient balance | from: {from_account_number}, balance: {from_account.balance}, attempted: {amount}")
                            transaction_counter.add(1, {"type": "transfer", "status": "fail"})
                            return JsonResponse({"success": False, "message": "[ERROR] Insufficient balance"}, status=400)
                    
                        from_account.balance -= amount
                        to_account.balance += amount

                        from_account.save()
                        to_account.save()

                        transaction = Transaction.objects.create(
                            transaction_id=transaction_id,
                            type="TRANSFER",
                            status="SUCCESS",
                            from_account=from_account,
                            to_account=to_account,
                            amount=amount,
                            balance_after=from_account.balance,
                            memo=memo,
                        )

                        logger.info(f"[transfer] Success | transaction_id: {transaction.transaction_id}, from: {from_account_number}, to: {to_account_number}, amount: {amount}")
                        logger.info(f"[{transaction.type.lower()}] Success | transaction_id: %s", transaction.transaction_id)
                        transaction_counter.add(1, {"type": "transfer", "status": "success"})

                        return JsonResponse({
                            "success": True,
                            "transaction": {
                                "transaction_id": str(transaction.transaction_id),
                                "type": "transfer",
                                "from_account": from_account.account_number,
                                "to_account": to_account.account_number,
                                "amount": transaction.amount,
                                "balance_after": transaction.balance_after,
                                "timestamp": transaction.created_at.isoformat(),
                                "memo": transaction.memo,
                                "status": transaction.status,
                            }
                        })
                except DatabaseError as e:
                    if attempt == 2:
                        # 마지막 시도도 실패하면 에러 터뜨림
                        return JsonResponse({"success": False, "message": "[ERROR] DB Error: " + str(e)}, status=500) 
                    time.sleep(0.1)  # 짧게 쉬고 재시도

                except OperationalError as e:
                    if attempt == 2:
                        # 마지막 시도도 실패하면 에러 터뜨림
                        return JsonResponse({"success": False, "message": "[ERROR] Lock wait timeout or deadlock: " + str(e)}, status=500) 
                    time.sleep(0.1)  # 짧게 쉬고 재시도

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "[ERROR] Invalid JSON"}, status=400)
        
        except Exception as e:
            logger.exception(f"[transfer] Unexpected Error: {str(e)}")
            transaction_counter.add(1, {"type": "transfer", "status": "fail"})
            return JsonResponse({"success": False, "message": f"[ERROR] {str(e)}"}, status=500)


class ValidateAccountView(APIView):
    @method_decorator(jwt_required)
    def post(self, request):
        try:
            data = request.data
            account_number = data.get("account_number")

            if not account_number:
                return JsonResponse({"success": False, "message": "[ERROR] Missing account number"}, status=400)

            try:
                account = Account.objects.get(account_number=account_number)

                if account.status == "CLOSED":
                    return JsonResponse({"success": False, "message": "[ERROR] 계좌가 비활성되어 있습니다."}, status=400)

                return JsonResponse({
                    "success": True,
                    "account": {
                        "account_number": account.account_number,
                        "account_name": account.nickname,
                        "owner": account.user.name,
                        "owner_email": account.user.email,
                        "balance": account.balance
                    }
                })
            except Account.DoesNotExist:
                logger.warning(f"[validate_account] Account not found: {account_number}")
                return JsonResponse({"success": False, "message": "[ERROR] Account not found"}, status=404)

        except json.JSONDecodeError:
            logger.error("[validate_account] JSON Decode Error", exc_info=True)
            return JsonResponse({"success": False, "message": "[ERROR] Invalid JSON"}, status=400)
        except Exception as e:
            logger.exception(f"[validate_account] Unexpected Error: {str(e)}")
            return JsonResponse({"success": False, "message": f"[ERROR] {str(e)}"}, status=500)

class TransactionHistoryView(APIView):
    @method_decorator(jwt_required)
    def get(self, request, account_number):
        try:
            account = Account.objects.get(account_number=account_number)
            transactions = Transaction.objects.filter(
                from_account=account
            ) | Transaction.objects.filter(
                to_account=account
            )
            transactions = transactions.order_by('-created_at')

            history = []
            for tx in transactions:
                if tx.type == 'TRANSFER':
                    if tx.from_account == account:
                        counterparty_name = tx.to_account.user.name if tx.to_account and tx.to_account.user else "알 수 없음"
                    else:
                        counterparty_name = tx.from_account.user.name if tx.from_account and tx.from_account.user else "알 수 없음"
                else:
                    counterparty_name = None

                history.append({
                    "transaction_id": str(tx.transaction_id),
                    "type": tx.type,
                    "amount": tx.amount,
                    "balance_after": tx.balance_after,
                    "timestamp": tx.created_at.isoformat(),
                    "memo": tx.memo,
                    "status": tx.status,
                    "from_account": tx.from_account.account_number if tx.from_account else None,
                    "to_account": tx.to_account.account_number if tx.to_account else None,
                    "counterparty_name": counterparty_name
                })

            return JsonResponse({"success": True, "history": history},json_dumps_params={'ensure_ascii': False})

        except Account.DoesNotExist:
            logger.warning(f"[transaction_history] Account not found: {account_number}")
            return JsonResponse({"success": False, "message": "[ERROR] Account not found"}, status=404)
        except Exception as e:
            logger.exception(f"[transaction_history] Unexpected Error: {str(e)}")
            return JsonResponse({"success": False, "message": f"[ERROR] {str(e)}"}, status=500)
