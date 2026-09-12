from sqlalchemy import Column, Integer, String, Date, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Professional(Base):
    __tablename__ = "professionals"
    __table_args__ = (UniqueConstraint("cpf", name="uq_professional_cpf"), UniqueConstraint("email", name="uq_professional_email"))

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    cpf = Column(String(14), nullable=False, unique=True)
    date_of_birth = Column(Date, nullable=False)
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
