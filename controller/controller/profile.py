from sqlalchemy import Column, String, Integer, BigInteger, DateTime
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from akiri.framework.ext.sqlalchemy import meta

from passwd import tableau_hash
from mixin import BaseMixin, BaseDictMixin

class UserProfile(meta.Base, BaseMixin, BaseDictMixin):
    """
    Profile information is added to the 'users' table.
    """
    __tablename__ = 'users'
    userid = Column(BigInteger, unique=True, nullable=False, \
                        autoincrement=True, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    friendly_name = Column(String)
    email = Column(String)
    hashed_password = Column(String)
    salt = Column(String)
    roleid = Column(BigInteger, ForeignKey("roles.roleid"), default=0)
    login_at = Column(DateTime)
    licensing_role_id = Column(Integer)
    user_admin_level = Column(Integer)
    system_admin_level = Column(Integer)
    publisher_tristate = Column(Integer)
    system_created_at = Column(DateTime)
    timestamp = Column(DateTime)

    role = relationship("Role")

    @classmethod
    def get(cls, userid):
        try:
            entry = meta.Session.query(UserProfile).\
                            filter(UserProfile.userid == userid).one()
        except NoResultFound, e:
            entry = None
        return entry

    @classmethod
    def get_by_name(cls, name):
        try:
            entry = meta.Session.query(UserProfile).\
                            filter(UserProfile.name == name).one()
        except NoResultFound, e:
            entry = None
        return entry

    @classmethod
    def verify(cls, name, password):
        entry = cls.get_by_name(name)
        if not entry:
            return False
        return entry.hashed_password == tableau_hash(password, entry.salt)

    defaults = [{'name':'palette', 'friendly_name':'Palette',
                 'email': None, 'salt':'', 'roleid':3,
                 'hashed_password':tableau_hash('tableau2014','')}]

class Role(meta.Base, BaseMixin):
    __tablename__ = 'roles'

    roleid = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

    defaults = [{'roleid':0, 'name':"No Admin"},
                {'roleid':1, 'name':"Read-Only Admin"},
                {'roleid':2, 'name':"Manager Admin"},
                {'roleid':3, 'name':"Super Admin"}]

class License(object):
    UNLICENSED = 3
    INTERACTOR = 2
    VIEWER = 1

    @classmethod
    def str(cls, n):
        if n == License.UNLICENSED:
            return 'Unlicensed'
        if n == License.INTERACTOR:
            return 'Interactor'
        if n == License.VIEWER:
            return 'Viewer'
        return 'Unknown('+str(n)+')'

class Publisher(object):
    DENY = 0
    IMPLICIT = 1
    GRANTED = 2

    @classmethod
    def str(cls, n):
        if n == Publisher.DENY:
            return 'Deny'
        if n == Publisher.IMPLICIT:
            return 'Allow (Implicit)'
        if n == Publisher.GRANTED:
            return 'Allow (Granted)'
        return 'Unknown('+str(n)+')'

class Admin(object):

    @classmethod
    def str(cls, user, system):
        if user == 5 and system == 0:
            return 'Site Admin'
        if user == 0 and system == 10:
            return 'System Admin'
        if user == 0 and system == 0:
            return 'No Admin'
        return 'Unknown('+str(user)+','+str(system)+')'
