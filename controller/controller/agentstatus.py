import logging
import string
import time
import threading
import platform

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, func
from sqlalchemy.schema import ForeignKey, UniqueConstraint
from sqlalchemy.orm.exc import NoResultFound

from akiri.framework.ext.sqlalchemy import meta
from mixin import BaseDictMixin

from agentinfo import AgentVolumesEntry

class AgentStatusEntry(meta.Base, BaseDictMixin):
    __tablename__ = 'agent'

    agentid = Column(BigInteger, unique=True, nullable=False, \
      autoincrement=True, primary_key=True)
    domainid = Column(BigInteger, ForeignKey("domain.domainid"))
    uuid = Column(String, unique=True, index=True)
    displayname = Column(String)
    display_order = Column(Integer)
    hostname = Column(String)
    agent_type = Column(String)
    version = Column(String)
    ip_address = Column(String)
    listen_port = Column(Integer)
    username = Column(String)
    password = Column(String)
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(), \
      server_onupdate=func.current_timestamp())
    last_connection_time = Column(DateTime, server_default=func.now())
    last_disconnect_time = Column(DateTime)
    UniqueConstraint('domainid', 'displayname')

    def __init__(self, hostname, agent_type, version, ip_address, listen_port,
                                            username, password, uuid, domainid):
        try:
            # FIXME: shouldn't this be a merge?
            entry = meta.Session.query(AgentStatusEntry).\
                filter(AgentStatusEntry.uuid == uuid).one()
            agentid = entry.agentid
        except NoResultFound, e:
            agentid = None

        self.agentid = agentid
        self.hostname = hostname
        self.agent_type = agent_type
        self.version = version
        self.ip_address = ip_address
        self.listen_port = listen_port
        self.username = username
        self.password = password
        self.uuid = uuid
        self.domainid = domainid

    def connected(self):
        if not self.last_disconnect_time or \
                        self.last_disconnect_time < self.last_connection_time:
            return True # connected
        else:
            return False # not connected

    @classmethod
    def display_order_by_domainid(cls, domainid):
        """Returns a list of agent uuids, sorted by display_order."""
        agent_entries = meta.Session.query(AgentStatusEntry).\
            filter(AgentStatusEntry.domainid == domainid).\
            order_by(AgentStatusEntry.display_order).\
            all()

        agents_sorted = [entry.uuid for entry in agent_entries]
        return agents_sorted

    @classmethod
    def get_agentstatusentry_by_volid(cls, volid):
        vol_entry = AgentVolumesEntry.get_vol_entry_by_volid(volid)
        if not vol_entry:
            return False

        return meta.Session.query(AgentStatusEntry).\
            filter(AgentStatusEntry.agentid == vol_entry.agentid).\
            one()
