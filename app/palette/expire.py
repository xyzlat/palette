from sqlalchemy.orm.exc import NoResultFound

# pylint: disable=import-error,no-name-in-module
from akiri.framework.ext.sqlalchemy import meta
# pylint: enable=import-error,no-name-in-module

from datetime import datetime

from webob import exc

from akiri.framework import GenericWSGI

from controller.licensing import LicenseEntry
from controller.agent import Agent

LICENSE_EXPIRED = 'https://licensing.palette-software.com/license-expired'
TRIAL_EXPIRED = 'https://licensing.palette-software.com/trial-expired'

class ExpireMiddleware(GenericWSGI):
    """Check for expired trials/licenses and redirect if necessary."""
    def service(self, req):
        if req.palette_domain.expiration_time is None \
                or datetime.now() < req.palette_domain.expiration_time:
            return None
        if req.palette_domain.trial:
            location = TRIAL_EXPIRED
        else:
            location = LICENSE_EXPIRED

        if req.palette_domain.license_key:
            location += '?key=' + req.palette_domain.license_key
        else:
            location += '?key=' # development only

        for entry in LicenseEntry.all():
            location += '&type=' + entry.gettype().lower()
            if entry.interactors:
                location += '&n=' + str(entry.interactors)
            else:
                try:
                    agent_entry = meta.Session.query(Agent).\
                        filter(Agent.agentid == entry.agentid).\
                        one()
                except NoResultFound:
                    print 'expire: No agent with agentid', entry.agentid
                    location += '&n=0'
                else:
                    location += '&n=' + str(agent_entry.processor_count)

        raise exc.HTTPTemporaryRedirect(location=location)


def make_expire_filter(app, global_conf):
    # pylint: disable=unused-argument
    return ExpireMiddleware(app)
