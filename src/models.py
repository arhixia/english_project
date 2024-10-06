from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


# Модель для элективов
class Elective(Base):
    __tablename__ = 'electives'

    id = Column(Integer, primary_key=True)
    unique_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(255), nullable=False)  # Название курса
    description = Column(Text, nullable=False)  # Аннотация
    elective_type = Column(String(50), nullable=False)  # PEP или RIM

    reviews = relationship("Review", back_populates="elective")  # Связь с отзывами


# Модель отзывов
class Review(Base):
    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True)
    elective_id = Column(Integer, ForeignKey('electives.id'), nullable=False)  # Связь с курсом
    user_name = Column(String(255), nullable=False)  # Имя или ID пользователя, оставившего отзыв
    text = Column(Text, nullable=False)  # Текст отзыва
    date_created = Column(String(100), nullable=False)  # Дата создания отзыва

    elective = relationship("Elective", back_populates="reviews")  # Связь с курсом

