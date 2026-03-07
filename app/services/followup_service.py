from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import logging

from app.db.models import FollowUp, FollowUpType, FollowUpStatus, Contact, Order
from app.config import settings


logger = logging.getLogger(__name__)


class FollowUpService:
    """Service for managing follow-up messages."""

    async def create_followup(
        self,
        contact_id: str,
        followup_type: str,
        message_template: str,
        session: AsyncSession,
        conversation_id: Optional[str] = None,
        order_id: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
        variables: Optional[dict] = None,
        delay_minutes: Optional[int] = None
    ) -> FollowUp:
        """
        Create a new follow-up.

        Args:
            contact_id: Contact ID
            followup_type: Type of follow-up
            message_template: Message template
            session: Database session
            conversation_id: Optional conversation ID
            order_id: Optional order ID
            scheduled_for: When to send (or use delay_minutes)
            variables: Template variables
            delay_minutes: Delay from now (alternative to scheduled_for)

        Returns:
            Created follow-up
        """
        try:
            # Calculate scheduled time
            if delay_minutes:
                scheduled_for = datetime.utcnow() + timedelta(minutes=delay_minutes)
            elif not scheduled_for:
                scheduled_for = datetime.utcnow() + timedelta(minutes=settings.followup_initial_delay_minutes)

            followup = FollowUp(
                contact_id=contact_id,
                conversation_id=conversation_id,
                order_id=order_id,
                followup_type=followup_type,
                scheduled_for=scheduled_for,
                message_template=message_template,
                variables=variables or {},
                status=FollowUpStatus.PENDING.value
            )

            session.add(followup)
            await session.commit()
            await session.refresh(followup)

            logger.info(f"Follow-up created: {followup_type} for contact {contact_id}")
            return followup

        except Exception as e:
            logger.error(f"Error creating follow-up: {e}")
            await session.rollback()
            raise

    async def get_pending_followups(
        self,
        session: AsyncSession,
        limit: int = 100
    ) -> List[FollowUp]:
        """
        Get follow-ups that are due to be sent.

        Args:
            session: Database session
            limit: Max number of follow-ups

        Returns:
            List of pending follow-ups
        """
        try:
            query = (
                select(FollowUp)
                .options(
                    selectinload(FollowUp.contact),
                    selectinload(FollowUp.order)
                )
                .where(
                    and_(
                        FollowUp.status == FollowUpStatus.PENDING.value,
                        FollowUp.scheduled_for <= datetime.utcnow()
                    )
                )
                .order_by(FollowUp.scheduled_for)
                .limit(limit)
            )

            result = await session.execute(query)
            followups = result.scalars().all()

            logger.info(f"Found {len(followups)} pending follow-ups")
            return followups

        except Exception as e:
            logger.error(f"Error getting pending follow-ups: {e}")
            return []

    async def send_followup(
        self,
        followup: FollowUp,
        session: AsyncSession
    ) -> bool:
        """
        Send a follow-up message.

        Args:
            followup: Follow-up to send
            session: Database session

        Returns:
            True if sent successfully
        """
        try:
            from app.services.uazapi_service import uazapi_service

            # Format message
            message = self._format_message(
                followup.message_template,
                followup.variables
            )

            # Send message
            await uazapi_service.send_text_message(
                phone=followup.contact.phone,
                message=message
            )

            # Update status
            followup.status = FollowUpStatus.SENT.value
            followup.sent_at = datetime.utcnow()
            followup.attempt_number += 1
            await session.commit()

            logger.info(f"Follow-up sent: {followup.id} to {followup.contact.phone}")
            return True

        except Exception as e:
            logger.error(f"Error sending follow-up: {e}")
            # Check if should retry
            if followup.attempt_number >= followup.max_attempts:
                followup.status = FollowUpStatus.FAILED.value
                followup.error_message = str(e)
            await session.commit()
            return False

    def _format_message(self, template: str, variables: dict) -> str:
        """Format message template with variables."""
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing variable in template: {e}")
            return template

    async def create_payment_reminder_followups(
        self,
        order_id: str,
        contact_id: str,
        amount: float,
        session: AsyncSession
    ):
        """
        Create follow-up sequence for payment reminder.

        Args:
            order_id: Order ID
            contact_id: Contact ID
            amount: Order amount
            session: Database session
        """
        delays = [20, 120, 1440]  # 20min, 2h, 24h

        for i, delay_minutes in enumerate(delays):
            await self.create_followup(
                contact_id=contact_id,
                followup_type=FollowUpType.PAYMENT_REMINDER.value,
                message_template=self._payment_reminder_template(i),
                session=session,
                order_id=order_id,
                delay_minutes=delay_minutes,
                variables={"amount": amount}
            )

    async def create_upsell_followup(
        self,
        order_id: str,
        contact_id: str,
        session: AsyncSession,
        delay_minutes: int = 60
    ):
        """
        Create upsell follow-up after successful payment.

        Args:
            order_id: Order ID
            contact_id: Contact ID
            session: Database session
            delay_minutes: Delay in minutes
        """
        await self.create_followup(
            contact_id=contact_id,
            followup_type=FollowUpType.UPSELL.value,
            message_template=self._upsell_template(),
            session=session,
            order_id=order_id,
            delay_minutes=delay_minutes
        )

    async def cancel_pending_followups(
        self,
        contact_id: str,
        session: AsyncSession,
        followup_type: Optional[str] = None
    ):
        """
        Cancel all pending follow-ups for a contact.

        Args:
            contact_id: Contact ID
            session: Database session
            followup_type: Optional filter by type
        """
        try:
            query = select(FollowUp).where(
                and_(
                    FollowUp.contact_id == contact_id,
                    FollowUp.status == FollowUpStatus.PENDING.value
                )
            )

            if followup_type:
                query = query.where(FollowUp.followup_type == followup_type)

            result = await session.execute(query)
            followups = result.scalars().all()

            for followup in followups:
                followup.status = FollowUpStatus.CANCELLED.value

            await session.commit()
            logger.info(f"Cancelled {len(followups)} follow-ups for contact {contact_id}")

        except Exception as e:
            logger.error(f"Error cancelling follow-ups: {e}")
            await session.rollback()

    def _payment_reminder_template(self, attempt: int) -> str:
        """Get payment reminder message template."""
        if attempt == 0:
            return """Olá! Vi que você ainda não concluiu o pagamento.

💰 Valor: R$ {amount:.2f}

O Pix está aguardando pagamento. Caso tenha alguma dúvida, estou aqui! 💬"""
        elif attempt == 1:
            return """Lembrete! ⏰

Seu pagamento de R$ {amount:.2f} ainda está pendente.

Precisa de ajuda com o pagamento?"""
        else:
            return """Última tentativa! 🔔

Seu pagamento não foi confirmado. Se ainda tiver interesse, por favor, realize o pagamento em até 15 minutos ou o pedido será cancelado."""

    def _upsell_template(self) -> str:
        """Get upsell message template."""
        return """Parabéns pela compra! 🎉

Como cliente especial, você tem acesso exclusivo a ofertas personalizadas.

Quer saber mais sobre os benefícios exclusivos para você?"""


# Singleton instance
followup_service = FollowUpService()
