"""Shared fixtures for DataSecurity tests."""

from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.db.sqlite_adapter import SQLiteAdapter
from src.models import EncryptionStatus


class _Base(DeclarativeBase):
    pass


class _Users(_Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255))
    phone = Column(String(20))
    full_name = Column(String(128))
    address = Column(Text)
    nric = Column(String(20))


class _Payments(_Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    credit_card = Column(String(20))
    amount = Column(Integer)
    merchant = Column(String(255))


class _Health(_Base):
    __tablename__ = "health_records"
    id = Column(Integer, primary_key=True)
    patient_name = Column(String(128))
    diagnosis = Column(Text)
    medication = Column(String(255))
    date_of_birth = Column(String(20))


class _Logs(_Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(64))
    message = Column(Text)
    created_at = Column(String(32))


@pytest.fixture()
def test_engine():  # type: ignore[return]
    """Create an in-memory SQLite engine with test tables."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    _Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                _Users(
                    email="alice@example.com",
                    phone="+6591234567",
                    full_name="Alice Tan",
                    address="123 Main St",
                    nric="S1234567A",
                ),
                _Users(
                    email="bob@test.org",
                    phone="98765432",
                    full_name="Bob Lee",
                    address="456 Oak Ave",
                    nric="T7654321B",
                ),
            ]
        )
        session.add_all(
            [
                _Payments(credit_card="4111111111111111", amount=9900, merchant="Shopee"),
                _Payments(credit_card="5500005555555559", amount=12000, merchant="Lazada"),
            ]
        )
        session.add_all(
            [
                _Health(
                    patient_name="Charlie Wong",
                    diagnosis="Hypertension",
                    medication="Amlodipine",
                    date_of_birth="1985-03-12",
                ),
            ]
        )
        session.add_all(
            [
                _Logs(event_type="LOGIN", message="User logged in", created_at="2026-01-01"),
            ]
        )
        session.commit()
    return engine


@pytest.fixture()
def sqlite_adapter(test_engine):  # type: ignore[return]
    """SQLiteAdapter backed by the shared test engine."""
    adapter = SQLiteAdapter()
    adapter._engine = test_engine  # inject test engine
    return adapter


@pytest.fixture()
def db_session(test_engine):  # type: ignore[return]
    """SQLAlchemy session for the test database."""
    factory = sessionmaker(bind=test_engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def tls_off_encryption() -> EncryptionStatus:
    return EncryptionStatus(database_name="test_db", tde_enabled=False, tls_enabled=False)


@pytest.fixture()
def tls_on_encryption() -> EncryptionStatus:
    return EncryptionStatus(
        database_name="test_db",
        tde_enabled=True,
        tls_enabled=True,
        tls_version="TLSv1.3",
        tls_cipher="ECDHE-RSA-AES256-GCM-SHA384",
    )
