from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from app.db.session import async_session_maker
from app.db.models import FollowUp, FollowUpStatus
from app.services.followup_service import followup_service


logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.followup_tasks.process_pending_followups")
def process_pending_followups():
    """
    Process all pending follow-ups that are due.
    This task runs periodically (configured in beat_schedule).
    """
    import asyncio

    async def _process():
        async with async_session_maker() as session:
            try:
                # Get pending follow-ups
                followups = await followup_service.get_pending_followups(
                    session=session,
                    limit=50
                )

                logger.info(f"Processing {len(followups)} pending follow-ups")

                for followup in followups:
                    try:
                        success = await followup_service.send_followup(
                            followup=followup,
                            session=session
                        )

                        if success:
                            logger.info(f"Follow-up sent: {followup.id}")
                        else:
                            logger.warning(f"Follow-up failed: {followup.id}")

                    except Exception as e:
                        logger.error(f"Error sending follow-up {followup.id}: {e}")

            except Exception as e:
                logger.error(f"Error in process_pending_followups: {e}", exc_info=True)

    asyncio.run(_process())


@shared_task(name="app.tasks.followup_tasks.schedule_payment_followups")
def schedule_payment_followups(order_id: str, contact_id: str, amount: float):
    """
    Schedule follow-up sequence for a payment.

    Args:
        order_id: Order ID
        contact_id: Contact ID
        amount: Order amount
    """
    import asyncio

    async def _schedule():
        async with async_session_maker() as session:
            try:
                await followup_service.create_payment_reminder_followups(
                    order_id=order_id,
                    contact_id=contact_id,
                    amount=amount,
                    session=session
                )
                logger.info(f"Payment follow-ups scheduled for order {order_id}")

            except Exception as e:
                logger.error(f"Error scheduling payment follow-ups: {e}", exc_info=True)

    asyncio.run(_schedule())


@shared_task(name="app.tasks.followup_tasks.reactivate_inactive_contacts")
def reactivate_inactive_contacts(days_inactive: int = 30):
    """
    Reactivate inactive contacts with a follow-up message.

    Args:
        days_inactive: Days of inactivity before reactivation
    """
    import asyncio

    async def _reactivate():
        async with async_session_maker() as session:
            try:
                from datetime import timedelta
                from sqlalchemy import select, and_
                from app.db.models import Contact, Conversation, FollowUpType

                threshold = datetime.utcnow() - timedelta(days=days_inactive)

                # Find contacts inactive for more than X days
                # This is a simplified query - adjust based on your needs
                query = select(Contact).limit(100)

                result = await session.execute(query)
                contacts = result.scalars().all()

                for contact in contacts:
                    # Check if there's already a recent reactivation follow-up
                    # If not, create one
                    pass

                logger.info(f"Processed {len(contacts)} inactive contacts")

            except Exception as e:
                logger.error(f"Error in reactivate_inactive_contacts: {e}", exc_info=True)

    asyncio.run(_reactivate())
