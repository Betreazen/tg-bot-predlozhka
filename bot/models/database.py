"""Database models for the bot."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class SubmissionStatus(enum.Enum):
    """Submission status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ACCEPTED_NOT_PUBLISHED = "accepted_not_published"
    PUBLICATION_FAILED = "publication_failed"
    SCHEDULED = "scheduled"


class ActionType(enum.Enum):
    """Admin action type enumeration."""
    APPROVE_PUBLISH = "approve_publish"
    APPROVE_ONLY = "approve_only"
    REJECT = "reject"
    BLOCK_USER = "block_user"
    UNBLOCK_USER = "unblock_user"
    ADD_NOTE = "add_note"
    EDIT_NOTE = "edit_note"
    CANCEL_PUBLICATION = "cancel_publication"


class User(Base):
    """User model."""
    
    __tablename__ = "users"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_submissions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    registration_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_interaction_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="user", cascade="all, delete-orphan"
    )


class Submission(Base):
    """Submission model."""
    
    __tablename__ = "submissions"
    
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    submission_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False
    )
    moderator_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    decision_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    show_authorship: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message_id_in_admin_chat: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_id_in_channel: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Store Telegram message ID and chat ID for forwarding
    user_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    user_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Media information
    has_media: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    media_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Text content (optional caption for media)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Publication scheduling
    scheduled_publication_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    publication_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publication_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="submissions")
    action_logs: Mapped[list["AdminActionLog"]] = relationship(
        "AdminActionLog", back_populates="submission", cascade="all, delete-orphan"
    )


class AdminActionLog(Base):
    """Admin action log model."""
    
    __tablename__ = "admin_action_logs"
    
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    admin_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.submission_id"), nullable=True
    )
    action_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    additional_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    submission: Mapped[Optional["Submission"]] = relationship(
        "Submission", back_populates="action_logs"
    )
