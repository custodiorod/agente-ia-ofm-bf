from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import logging

from app.db.session import async_session_maker
from app.db.models import Contact, Conversation, Message, MessageDirection, MessageType
from app.agents.conversation_agent import conversation_agent
from app.services.uazapi_service import uazapi_service


logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.message_tasks.process_whatsapp_message")
def process_whatsapp_message(
    phone: str,
    message: str,
    message_type: str = "text",
    message_id: str = None
):
    """
    Process incoming WhatsApp message asynchronously.

    Args:
        phone: Sender phone number
        message: Message content
        message_type: Type of message (text, audio, image, etc.)
        message_id: Provider message ID
    """
    import asyncio

    async def _process():
        async with async_session_maker() as session:
            try:
                # Get or create contact
                contact = await _get_or_create_contact(phone, session)
                logger.info(f"Contact: {contact.id} - {contact.name or phone}")

                # Get or create conversation
                conversation = await _get_or_create_conversation(contact.id, session)
                logger.info(f"Conversation: {conversation.id}")

                # Save message
                db_message = Message(
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    direction=MessageDirection.INBOUND.value,
                    message_type=message_type,
                    content=message,
                    provider_message_id=message_id
                )
                session.add(db_message)
                await session.commit()

                # Get conversation history
                history_query = (
                    select(Message)
                    .where(Message.conversation_id == conversation.id)
                    .order_by(Message.created_at)
                    .limit(10)
                )
                history_result = await session.execute(history_query)
                history_messages = history_result.scalars().all()

                conversation_history = [
                    {
                        "role": "user" if m.direction == MessageDirection.INBOUND.value else "assistant",
                        "content": m.content or ""
                    }
                    for m in history_messages
                ]

                # Process with agent
                result = await conversation_agent.process_message(
                    user_input=message,
                    contact_id=str(contact.id),
                    conversation_id=str(conversation.id),
                    conversation_history=conversation_history,
                    session=session
                )

                # Send response
                await uazapi_service.send_text_message(
                    phone=phone,
                    message=result["response"]
                )

                # Save response message
                response_message = Message(
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    direction=MessageDirection.OUTBOUND.value,
                    message_type=MessageType.TEXT.value,
                    content=result["response"]
                )
                session.add(response_message)

                # Update conversation if handoff
                if result["should_handoff"]:
                    conversation.human_handoff = True

                await session.commit()
                logger.info(f"Message processed successfully for {phone}")

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await session.rollback()

    asyncio.run(_process())


async def _get_or_create_contact(phone: str, session: AsyncSession) -> Contact:
    """Get existing contact or create new one."""
    query = select(Contact).where(Contact.phone == phone)
    result = await session.execute(query)
    contact = result.scalar_one_or_none()

    if not contact:
        contact = Contact(phone=phone)
        session.add(contact)
        await session.flush()
        logger.info(f"Created new contact: {phone}")

    return contact


async def _get_or_create_conversation(
    contact_id: str,
    session: AsyncSession
) -> Conversation:
    """Get active conversation or create new one."""
    # Check for active conversation (no handoff, recent activity)
    from datetime import timedelta

    recent_threshold = datetime.utcnow() - timedelta(hours=24)

    query = (
        select(Conversation)
        .where(
            and_(
                Conversation.contact_id == contact_id,
                Conversation.human_handoff == False,
                Conversation.updated_at >= recent_threshold
            )
        )
        .order_by(Conversation.updated_at.desc())
    )

    result = await session.execute(query)
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            contact_id=contact_id,
            current_stage="new"
        )
        session.add(conversation)
        await session.flush()
        logger.info(f"Created new conversation for contact {contact_id}")

    return conversation
