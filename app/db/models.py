from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Float,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum


Base = declarative_base()


class Contact(Base):
    """Contact/Lead information."""

    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    tags = Column(JSON, default=list)
    custom_fields = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    conversations = relationship(
        "Conversation", back_populates="contact", cascade="all, delete-orphan"
    )
    orders = relationship(
        "Order", back_populates="contact", cascade="all, delete-orphan"
    )
    payments = relationship(
        "Payment", back_populates="contact", cascade="all, delete-orphan"
    )
    followups = relationship(
        "FollowUp", back_populates="contact", cascade="all, delete-orphan"
    )


class ConversationStage(enum.Enum):
    NEW = "new"
    QUALIFYING = "qualifying"
    PRESENTING = "presenting"
    NEGOTIATING = "negotiating"
    CLOSING = "closing"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    HANDOFF = "handoff"


class Conversation(Base):
    """Conversation thread with a contact."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    current_stage = Column(
        String(50), default=ConversationStage.NEW.value, nullable=False
    )
    human_handoff = Column(Boolean, default=False, nullable=False)
    context = Column(JSON, default=dict)  # Store conversation context
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    contact = relationship("Contact", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    orders = relationship(
        "Order", back_populates="conversation", cascade="all, delete-orphan"
    )
    followups = relationship(
        "FollowUp", back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageType(enum.Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    SYSTEM = "system"


class MessageDirection(enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Message(Base):
    """Individual message in a conversation."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    direction = Column(
        String(20), default=MessageDirection.INBOUND.value, nullable=False
    )
    message_type = Column(String(20), default=MessageType.TEXT.value, nullable=False)
    content = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)  # For audio messages
    provider_message_id = Column(String(255), nullable=True, index=True)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    contact = relationship("Contact")
    conversation = relationship("Conversation", back_populates="messages")


class OrderStatus(enum.Enum):
    PENDING = "pending"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(Base):
    """Sales order."""

    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    offer_type = Column(String(100), nullable=False)
    offer_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="BRL", nullable=False)
    status = Column(
        String(50), default=OrderStatus.PENDING.value, nullable=False, index=True
    )
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    contact = relationship("Contact", back_populates="orders")
    conversation = relationship("Conversation", back_populates="orders")
    payments = relationship(
        "Payment", back_populates="order", cascade="all, delete-orphan"
    )
    followups = relationship(
        "FollowUp", back_populates="order", cascade="all, delete-orphan"
    )


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class Payment(Base):
    """Payment transaction."""

    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    provider = Column(String(50), default="pixbank", nullable=False)
    txid = Column(String(255), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(
        String(50), default=PaymentStatus.PENDING.value, nullable=False, index=True
    )
    paid_at = Column(DateTime, nullable=True)
    raw_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    order = relationship("Order", back_populates="payments")
    contact = relationship("Contact", back_populates="payments")


class FollowUpType(enum.Enum):
    PAYMENT_REMINDER = "payment_reminder"
    OFFER_FOLLOW_UP = "offer_follow_up"
    INACTIVE_REACTIVATION = "inactive_reactivation"
    UPSELL = "upsell"
    FEEDBACK = "feedback"
    ABANDONED_CART = "abandoned_cart"


class FollowUpStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FollowUp(Base):
    """Scheduled follow-up messages."""

    __tablename__ = "followups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True, index=True
    )
    followup_type = Column(String(50), nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=False, index=True)
    status = Column(
        String(50), default=FollowUpStatus.PENDING.value, nullable=False, index=True
    )
    attempt_number = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    message_template = Column(Text, nullable=False)
    variables = Column(JSON, default=dict)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    contact = relationship("Contact", back_populates="followups")
    conversation = relationship("Conversation", back_populates="followups")
    order = relationship("Order", back_populates="followups")


class KnowledgeBase(Base):
    """RAG knowledge base with pgvector."""

    __tablename__ = "knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False)  # faq, script, doc, response
    tags = Column(JSON, default=list)
    category = Column(String(100), nullable=True)
    embedding = Column(Vector(1536), nullable=True)  # OpenAI embedding dimension
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SystemEvent(Base):
    """System events for audit and monitoring."""

    __tablename__ = "system_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
