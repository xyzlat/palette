import time
from datetime import datetime

from sqlalchemy import Column, BigInteger, Integer, String, DateTime
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm.exc import NoResultFound

from akiri.framework.ext.sqlalchemy import meta
from event_control import EventControl
from mixin import BaseDictMixin
from util import utc2local

class ExtractEntry(meta.Base, BaseDictMixin):
    __tablename__ = "extracts"

    extractid = Column(BigInteger, unique=True, nullable=False,
                       primary_key=True)
    agentid = Column(BigInteger, ForeignKey("agent.agentid"), nullable=False)
    finish_code = Column(Integer, nullable=False)
    notes = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    title = Column(String)
    subtitle = Column(String)
    site_id = Column(Integer)


class ExtractManager(object):

    def __init__(self, server):
        self.server = server

    def load(self, agent):
        stmt = "SELECT id, finish_code, notes, started_at, completed_at, " +\
            "title, subtitle, site_id " +\
            "FROM background_jobs " +\
            "WHERE job_name = 'Refresh Extracts' AND progress = 100"

        session = meta.Session()

        lastid = self.lastid()
        if not lastid is None:
            stmt += " AND id > '" + lastid + "'"

        data = agent.odbc.execute(stmt)

        if 'error' in data or '' not in data:
            return data

        FMT = "%Y-%m-%d %H:%M:%SZ"
        for row in data['']:
            started_at = utc2local(datetime.strptime(row[3], FMT))
            completed_at = utc2local(datetime.strptime(row[4], FMT))
            entry = ExtractEntry(extractid=row[0],
                                 agentid=agent.agentid,
                                 finish_code=row[1],
                                 notes=row[2],
                                 started_at=started_at,
                                 completed_at=completed_at,
                                 title=row[5],
                                 subtitle=row[6],
                                 site_id=row[7])

            body = dict(agent.__dict__.items() + entry.todict().items())
            if entry.finish_code == 0:
                self.eventgen(EventControl.EXTRACT_OK, body,
                              timestamp=completed_at)
            else:
                self.eventgen(EventControl.EXTRACT_FAILED, body,
                              timestamp=completed_at)

            session.add(entry)

        session.commit()

        return {u'status': 'OK',
                u'count': len(data[''])}

    def lastid(self):
        entry = meta.Session.query(ExtractEntry).\
            order_by(ExtractEntry.extractid.desc()).first()
        if entry:
                return str(entry.extractid)
        return None

    def eventgen(self, key, data, timestamp=None):
        return self.server.event_control.gen(key, data, timestamp=timestamp)
