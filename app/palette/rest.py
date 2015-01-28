from webob import exc

from akiri.framework.api import RESTApplication
from akiri.framework import GenericWSGIApplication

from controller.profile import Role
from controller.palapi import CommHandlerApp

def required_parameters(*params):
    def wrapper(f):
        def realf(self, req, *args, **kwargs):
            if req.method != 'POST':
                raise exc.HTTPMethodNotAllowed(req.method)
            for param in params:
                if param not in req.POST:
                    raise exc.HTTPBadRequest("'" + param + "' missing")
            return f(self, req, *args, **kwargs)
        return realf
    return wrapper

def required_role(name):
    def wrapper(f):
        def realf(self, req, *args, **kwargs):
            if isinstance(name, basestring):
                role = Role.get_by_name(name).roleid
            else:
                role = Role.get_by_roleid(name)
            if req.remote_user.roleid < role.roleid:
                raise exc.HTTPForbidden("The '"+role.name+"' role is required.")
            return f(self, req, *args, **kwargs)
        return realf
    return wrapper

class PaletteRESTHandler(RESTApplication):

    def __init__(self, global_conf):
        super(PaletteRESTHandler, self).__init__(global_conf)
        self.commapp = CommHandlerApp(self)

    def base_path_info(self, req):
        # REST handlers return the handle path prefix too, strip it.
        path_info = req.environ['PATH_INFO']
        if path_info.startswith('/' + self.NAME):
            path_info = path_info[len(self.NAME)+1:]
        if path_info.startswith('/'):
            path_info = path_info[1:]
        return path_info

class PaletteRESTApplication(GenericWSGIApplication):

    def __init__(self):
        super(PaletteRESTApplication, self).__init__()
        self.commapp = CommHandlerApp(self)

import logging
from akiri.framework.rest import REST

# This call is only used for testing/profiling.
# Production should use the native framework make_rest.
def make_rest(global_conf):
    formatter = logging.Formatter(fmt='[%(asctime)s] %(message)s')
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger = logging.getLogger('sqlalchemy.engine')
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)

    app = REST(global_conf)
    return app
