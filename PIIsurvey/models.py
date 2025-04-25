from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref
from sqlalchemy import ForeignKey, Integer, Text, Boolean, DateTime, String
import datetime

db = SQLAlchemy()

class Participant(db.Model):
    __tablename__ = "participant_table"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, autoincrement=False)  # Student ID (900 number) hashed
    datetime_taken: Mapped[DateTime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    major: Mapped[str] = mapped_column(String, nullable=False)
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    responses: Mapped[list["Response"]] = relationship("Response", back_populates="participant_id_rel", cascade="all, delete-orphan")

class Question(db.Model):
    __tablename__ = "question_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=True) 
    prompt: Mapped[str] = mapped_column(Text, nullable=True) 
    init_prompt_answer: Mapped[str] = mapped_column(Text, nullable=True) 
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Response(db.Model):
    __tablename__ = "response_table"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True)
    participant_id: Mapped[str] = mapped_column(String, ForeignKey("participant_table.id"))
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_table.id"))
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False)
    skip_alled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conversation: Mapped[str] = mapped_column(Text, nullable=True) 
    
    participant_id_rel: Mapped["Participant"] = relationship("Participant")
    question_rel: Mapped["Question"] = relationship("Question")