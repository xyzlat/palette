from collections import OrderedDict
from sqlalchemy import DateTime, func
from sqlalchemy.orm.exc import NoResultFound

import akiri.framework.sqlalchemy as meta

from util import DATEFMT, utc2local

import os
import json

class BaseDictMixin(object):

    def todict(self, pretty=False, exclude=None):
        if exclude is None:
            exclude = []
        if not isinstance(self, meta.Base):
            raise Exception("meta.Base instance required.")
        d = OrderedDict({})
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
            value = getattr(self, column.name)
            if value is None:
                continue
            if isinstance(column.type, DateTime):
                try:
                    value = utc2local(value) # FIXME
                    value = value.strftime(DATEFMT)
                except AttributeError:
                     # It is possible this value has been set directly but
                     # not yet converted by the ORM.
                     # i.e. It is not a DateTime instance but something else
                     # that can be later converted to a DateTime instance.
                    value = str(value)
            elif not isinstance(value, (int, long)):
                value = unicode(value)
            name = pretty and column.name.replace('_', '-') or column.name
            d[name] = value
        return d


class BaseMixin(object):

    defaults = []
    defaults_filename = None

    @classmethod
    def populate(cls):
        session = meta.Session()
        entry = session.query(cls).first()
        if entry:
            return
        if not cls.defaults_filename is None:
            rows = cls.populate_from_file(cls.defaults_filename)
        else:
            rows = cls.defaults
        for d in rows:
            obj = cls(**d)
            session.add(obj)
        session.commit()

    @classmethod
    def populate_upgrade(cls, previous_version, version):
        """
            For an empty table:
                Populates it.
            For an existing table when upgrading:
                Replace rows only if the 'custom' column is False.
            Requires 'key' and 'custom' columns in the table.
        """

        if not previous_version or previous_version == version:
            cls.populate()
            return

        session = meta.Session()
        entry = session.query(cls).first()
        if not entry:
            # Table is empty, add all rows.
            cls.populate()
            return

        if not cls.defaults_filename is None:
            rows = cls.populate_from_file(cls.defaults_filename)
        else:
            rows = cls.defaults

        # We are upgrading.
        # Delete all rows that aren't custom.
        session.query(cls).\
            filter(cls.custom != True).\
            delete()

        for d in rows:
            entry = session.query(cls).\
                                  filter(cls.key == d['key']).\
                                  first()
            # If the row didn't exist, add it.
            if not entry:
                obj = cls(**d)
                session.add(obj)
        session.commit()

    @classmethod
    def populate_from_file(cls, filename):
        path = os.path.dirname(os.path.realpath(__file__)) + "/" + filename

        with open(path, "r") as f:
            rows = json.load(f)
            return rows['RECORDS']

    @classmethod
    def apply_filters(cls, query, filters):
        for key, value in filters.items():
            query = query.filter(getattr(cls, key) == value)
        return query

    @classmethod
    def get_unique_by_keys(cls, keys, **kwargs):
        if 'default' in kwargs:
            default = kwargs['default']
            have_default = True
            del kwargs['default']
        else:
            have_default = False

        if kwargs:
            raise ValueError("Invalid kwargs: " + str(kwargs))

        query = meta.Session.query(cls)
        query = cls.apply_filters(query, keys)

        try:
            entry = query.one()
        except NoResultFound:
            if have_default:
                return default
            raise ValueError("No such value: " + str(keys))
        return entry

    @classmethod
    def get_all_by_keys(cls, keys, order_by=None, limit=None):
        if order_by is None:
            order_by = []

        query = meta.Session.query(cls)
        query = cls.apply_filters(query, keys)

        if isinstance(order_by, basestring):
            order_by = [order_by]
        for clause in order_by:
            query = query.order_by(clause)
        if not limit is None:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def max(cls, column, filters=None, default=None):
        query = meta.Session().query(func.max(getattr(cls, column)))

        if filters:
            query = cls.apply_filters(query, filters)

        # pylint: disable=maybe-no-member
        value = query.scalar()
        if value is None:
            return default
        return value

    @classmethod
    def count(cls, filters=None):
        query = meta.Session().query(cls)
        if filters:
            query = cls.apply_filters(query, filters)
        # pylint: disable=maybe-no-member
        return query.count()

    @classmethod
    def delete(cls, filters=None, synchronize_session='evaluate'):
        query = meta.Session().query(cls)
        if filters:
            query = cls.apply_filters(query, filters)
        return query.delete(synchronize_session=synchronize_session)

    @classmethod
    def cache_by_key(cls, envid, key=None):
        if key is None:
            tokey = lambda k: k
        elif isinstance(key, basestring):
            tokey = lambda k: getattr(k, key)
        else:
            tokey = key
        objs = [(tokey(obj), obj) for obj in cls.all(envid)]
        return OrderedDict(objs)

class OnlineMixin(object):

    @classmethod
    def exists_in_envid(cls, envid):
        try:
            meta.Session.query(cls).filter(cls.envid == envid).one()
            return True
        except NoResultFound:
            return False

from credential import CredentialEntry

class CredentialMixin(object):

    PRIMARY_KEY = 'primary'
    SECONDARY_KEY = 'secondary'
    READONLY_KEY = 'readonly'

    def get_cred(self, envid, name):
        return CredentialEntry.get_by_envid_key(envid, name, default=None)
