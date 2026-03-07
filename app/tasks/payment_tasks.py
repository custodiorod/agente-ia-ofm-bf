from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import logging

from app.db.session import async_session_maker
from app.db.models import Payment, Order, PaymentStatus, OrderStatus
from app.services.uazapi_service import uazapi_service
from app.services.followup_service import followup_service


logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.payment_tasks.process_payment_confirmation")
def process_payment_confirmation(
    txid: str,
    status: str,
    amount: float,
    raw_data: dict = None
):
    """
    Process payment confirmation from PixBank.

    Args:
        txid: Transaction ID
        status: Payment status
        amount: Payment amount
        raw_data: Raw webhook data
    """
    import asyncio

    async def _process():
        async with async_session_maker() as session:
            try:
                # Find payment by txid
                query = select(Payment).where(Payment.txid == txid)
                result = await session.execute(query)
                payment = result.scalar_one_or_none()

                if not payment:
                    logger.warning(f"Payment not found: {txid}")
                    return

                # Update payment status
                if status == "confirmed":
                    payment.status = PaymentStatus.CONFIRMED.value
                    payment.paid_at = datetime.utcnow()

                    # Update order
                    order_query = select(Order).where(Order.id == payment.order_id)
                    order_result = await session.execute(order_query)
                    order = order_result.scalar_one_or_none()

                    if order:
                        order.status = OrderStatus.PAID.value

                        # Send confirmation to customer
                        await uazapi_service.send_text_message(
                            phone=order.contact.phone,
                            message=f"✅ Pagamento confirmado!\n\nValor: R$ {amount:.2f}\n\nObrigado pela preferência!"
                        )

                        # Cancel pending follow-ups
                        await followup_service.cancel_pending_followups(
                            contact_id=str(payment.contact_id),
                            session=session,
                            followup_type="payment_reminder"
                        )

                        # Schedule upsell follow-up
                        await followup_service.create_upsell_followup(
                            order_id=str(order.id),
                            contact_id=str(payment.contact_id),
                            session=session
                        )

                    logger.info(f"Payment {txid} confirmed successfully")

                elif status == "failed":
                    payment.status = PaymentStatus.FAILED.value
                    logger.info(f"Payment {txid} failed")

                elif status == "expired":
                    payment.status = PaymentStatus.EXPIRED.value
                    logger.info(f"Payment {txid} expired")

                payment.raw_payload = raw_data or {}
                await session.commit()

            except Exception as e:
                logger.error(f"Error processing payment: {e}", exc_info=True)
                await session.rollback()

    asyncio.run(_process())


@shared_task(name="app.tasks.payment_tasks.check_pending_payments")
def check_pending_payments():
    """
    Check for pending payments that may have expired.
    Runs periodically to clean up expired payments.
    """
    import asyncio

    async def _check():
        async with async_session_maker() as session:
            try:
                from datetime import timedelta

                # Find payments pending for more than 1 hour
                expiry_time = datetime.utcnow() - timedelta(hours=1)

                query = select(Payment).where(
                    and_(
                        Payment.status == PaymentStatus.PENDING.value,
                        Payment.created_at <= expiry_time
                    )
                )

                result = await session.execute(query)
                payments = result.scalars().all()

                for payment in payments:
                    # Check with PixBank
                    from app.services.payment_service import pixbank_service
                    try:
                        status_data = await pixbank_service.get_charge_status(payment.txid)
                        actual_status = status_data.get("status")

                        if actual_status == "expired":
                            payment.status = PaymentStatus.EXPIRED.value
                            await session.commit()
                            logger.info(f"Marked payment {payment.txid} as expired")

                    except Exception as e:
                        logger.error(f"Error checking payment {payment.txid}: {e}")

            except Exception as e:
                logger.error(f"Error in check_pending_payments: {e}", exc_info=True)

    asyncio.run(_check())
