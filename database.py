from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class InvoiceEmail(Base):
    __tablename__ = 'invoice_emails'
    
    invoice_number = Column(String, primary_key=True)
    email = Column(String, nullable=False)
    company_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)

def get_email_by_invoice(invoice_number: str) -> str:
    session = Session()
    try:
        record = session.query(InvoiceEmail).filter_by(invoice_number=invoice_number).first()
        return record.email if record else None
    finally:
        session.close()

def add_invoice_email(invoice_number: str, email: str, company_name: str = None):
    session = Session()
    try:
        invoice_email = InvoiceEmail(
            invoice_number=invoice_number,
            email=email,
            company_name=company_name
        )
        session.add(invoice_email)
        session.commit()
    finally:
        session.close() 