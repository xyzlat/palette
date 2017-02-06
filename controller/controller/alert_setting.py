from sqlalchemy import Column, String, Integer, Boolean

import akiri.framework.sqlalchemy as meta
from mixin import BaseMixin, BaseDictMixin


class AlertSetting(meta.Base, BaseMixin, BaseDictMixin):
    __tablename__ = 'alert_settings'

    ALERTING_DISABLED_VALUE = 101

    process_name = Column(String, unique=True, nullable=False, primary_key=True)
    threshold_warning = Column(Integer)
    threshold_error = Column(Integer)
    period_warning = Column(Integer)
    period_error = Column(Integer)

    defaults = [
        {'process_name': '7z', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'backgrounder', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'clustercontroller', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'dataserver', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'filestore', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'httpd', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'postgres', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'redis-server', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'searchserver', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabadmin', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabadminservice', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabadmsvc', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabadmwrk', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabcmd', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tableau', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabprotosrv', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabrepo', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabspawn', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabsvc', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tabsystray', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tdeserver', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'tdeserver64', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'vizportal', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'vizqlserver', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'wgserver', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60},
        {'process_name': 'zookeeper', 'threshold_warning': 101, 'threshold_error': 101, 'period_warning': 60,
         'period_error': 60}
    ]

    @classmethod
    def is_threshold_enabled(cls, value):
        return value < cls.ALERTING_DISABLED_VALUE

    @classmethod
    def get_all(cls):
        result = meta.Session.query(cls).all()

        return [record.todict() for record in result]

    @classmethod
    def get_monitored(cls):
        result = meta.Session.query(cls.process_name).filter(
            (cls.is_threshold_enabled(cls.threshold_warning) | cls.is_threshold_enabled(cls.threshold_error))
        )
        return [record.process_name for record in result]

    @classmethod
    def update_all(cls, values):
        session = meta.Session()
        for d in values:
            session.query(cls).filter_by(process_name=d['process_name']).update(d)
        session.commit()
