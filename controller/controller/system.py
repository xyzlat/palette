import re

from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Boolean
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from akiri.framework.ext.sqlalchemy import meta
from mixin import BaseMixin, BaseDictMixin

from storage import StorageConfig

class SystemEntry(meta.Base, BaseMixin, BaseDictMixin):
    __tablename__ = 'system'

    envid = Column(BigInteger, ForeignKey("environment.envid"),
                   primary_key=True)
    key = Column(String, unique=True, nullable=False, primary_key=True)
    value = Column(String)
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(),
                               onupdate=func.current_timestamp())

    defaults = [{'envid':1, 'key':'disk-watermark-low', 'value':str(50)},
                {'envid':1, 'key':'disk-watermark-high', 'value':str(80)},
                {'envid':1, 'key':StorageConfig.STORAGE_ENCRYPT, 'value': 'no'},
                {'envid':1,
                 'key':StorageConfig.WORKBOOKS_AS_TWB,
                 'value': 'no'},
                {'envid':1,
                 'key':StorageConfig.BACKUP_AUTO_RETAIN_COUNT,
                 'value': '3'},
                {'envid':1,
                 'key':StorageConfig.BACKUP_USER_RETAIN_COUNT,
                 'value': '5'},
                {'envid':1,
                 'key':StorageConfig.BACKUP_DEST_TYPE,
                 'value': StorageConfig.VOL},
                {'envid':1,
                 'key':StorageConfig.LOG_ARCHIVE_RETAIN_COUNT,
                 'value': '5'}
        # Note: No default volid set.
    ]

    @classmethod
    def get_by_key(cls, key):
        try:
            entry = meta.Session.query(SystemEntry).\
                filter(SystemEntry.key == key).one()
        except NoResultFound:
            return None
        return entry

class SystemManager(object):

    # Keys
    SYSTEM_KEY_STATE = "state"
    SYSTEM_KEY_EVENT_SUMMARY_FORMAT = "event-summary-format"

    def __init__(self, envid):
        self.envid = envid

    def save(self, key, value):
        session = meta.Session()

        entry = SystemEntry(envid=self.envid, key=key, value=value)
        session.merge(entry)
        session.commit()

    def entry(self, key, **kwargs):
        try:
            entry = meta.Session.query(SystemEntry).\
                filter(SystemEntry.envid == self.envid).\
                filter(SystemEntry.key == key).\
                one()
        except NoResultFound, e:
            raise ValueError("No system row found with key=%s" % key)
        return entry

    def get(self, key, **kwargs):
        if 'default' in kwargs:
            default = kwargs['default']
            have_default = True
            del kwargs['default']
        else:
            have_default = False

        if kwargs:
            raise ValueError("Invalid kwargs")

        try:
            entry = self.entry(key, **kwargs)
        except ValueError, e:
            if have_default:
                return default
            else:
                raise e
        return entry.value

    @classmethod
    def populate(cls):
        SystemEntry.populate()

class LicenseEntry(meta.Base, BaseMixin, BaseDictMixin):
    __tablename__ = 'license'

    licenseid = Column(BigInteger, primary_key=True)
    agentid = Column(BigInteger, ForeignKey("agent.agentid"),
                     nullable=False, unique=True)
    interactors = Column(Integer)
    viewers = Column(Integer)
    notified = Column(Boolean, nullable=False, default=False)
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(),
                               onupdate=func.current_timestamp())

    @classmethod
    def get_by_agentid(cls, agentid):
        try:
            entry = meta.Session.query(LicenseEntry).\
                filter(LicenseEntry.agentid == agentid).\
                one()
        except NoResultFound, e:
            return None
        return entry

    @classmethod
    def save(cls, agentid, interactors=None, viewers=None):
        session = meta.Session()
        entry = cls.get_by_agentid(agentid)
        if not entry:
            entry = LicenseEntry(agentid=agentid)

        entry.interactors = interactors
        entry.viewers = viewers

        # If the entry is valid, reset the notification field.
        if entry.valid():
            entry.notified = False

        session.merge(entry)
        session.commit()
        return entry

    @classmethod
    def update(cls, entry):
        session = meta.Session()
        session.merge(entry)
        session.commit()

        return entry

    @classmethod
    def parse(cls, output):
        pattern = '(?P<interactors>\d+) interactors, (?P<viewers>\d+) viewers'
        m = re.search(pattern, output)
        if not m:
            return {}
        return m.groupdict()

    def invalid(self):
        if self.interactors is None:
            return False
        self.interactors = int(self.interactors)
        if self.viewers is None:
            return False
        self.viewers = int(self.viewers)
        return self.interactors == 0 and self.viewers == 0

    def valid(self):
        return not self.invalid()
