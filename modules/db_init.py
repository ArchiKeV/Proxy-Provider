from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, PrimaryKeyConstraint, create_engine
from sqlalchemy.orm.session import sessionmaker

base = declarative_base()


class Proxy(base):
    __tablename__ = 'Proxy'
    ip_in = Column(String)
    port_in = Column(Integer)
    type = Column(Integer)
    country_code_in = Column(String)
    ip_out = Column(String)
    country_code_out = Column(String)
    load_ts = Column(DateTime)
    status = Column(String)
    status_ts = Column(DateTime)
    ip_in_port_in = PrimaryKeyConstraint(ip_in, port_in)


class SourceTimer(base):
    __tablename__ = "SourceTimer"
    name = Column(String, primary_key=True)
    ts = Column(DateTime)
