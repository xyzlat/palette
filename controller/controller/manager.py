import threading

def synchronized(label=None):
    def wrapper(f):
        def realf(self, *args, **kwargs):
            if not self.lock(blocking=False):
                if label is None:
                    error = 'load: busy.'
                else:
                    error = '%s: busy' % label
                return {u'error': error}
            try:
                return f(self, *args, **kwargs)
            finally:
                self.unlock()
        return realf
    return wrapper

class Manager(object):

    def __init__(self, server):
        self.server = server
        if hasattr(server, 'system'):
            # SystemManager is a Manager which doesn't need self.system
            self.system = server.system
        self.envid = self.server.environment.envid
        self._lock = threading.RLock()

    def lock(self, blocking=True):
        return self._lock.acquire(blocking=blocking)

    def unlock(self):
        self._lock.release()

