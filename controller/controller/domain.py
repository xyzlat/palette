from datetime import datetime
from sqlalchemy import Column, String, BigInteger, DateTime, func, Boolean
from sqlalchemy import Integer

import akiri.framework.sqlalchemy as meta

from mixin import BaseMixin, BaseDictMixin
import uuid

class Domain(meta.Base, BaseMixin, BaseDictMixin):
    __tablename__ = 'domain'

    domainid = Column(BigInteger, unique=True, nullable=False,
                           autoincrement=True, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    license_key = Column(String)
    systemid = Column(String)
    expiration_time = Column(DateTime)
    contact_time = Column(DateTime)
    contact_failures = Column(Integer)
    trial = Column(Boolean)
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(),
                                   server_onupdate=func.current_timestamp())

    defaults = [{'domainid': 0,
                 'name': 'default.local',
                 'systemid': str(uuid.uuid1())}]

    def trial_days(self):
        if not self.trial:
            return None
        timedelta = self.expiration_time - datetime.utcnow()
        if timedelta.days >= 0:
            return timedelta.days + 1
        return 0

    @classmethod
    def get_by_name(cls, name):
        # We expect the entry to exist, so allow a NoResultFound
        # exception to percolate up if the entry is not found.
        entry = meta.Session.query(Domain).\
            filter(Domain.name == name).one()
        return entry

    @classmethod
    def getone(cls):
        return meta.Session.query(Domain).one()
