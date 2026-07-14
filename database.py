import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base


@st.cache_resource
def get_engine():
    """
    Streamlit이 화면 조작 때마다 코드를 다시 실행하더라도
    동일한 인메모리 DB 엔진을 유지한다.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
        echo=False,
    )

    Base.metadata.create_all(engine)

    return engine


@st.cache_resource
def get_session_factory():
    engine = get_engine()

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def create_session() -> Session:
    session_factory = get_session_factory()
    return session_factory()
