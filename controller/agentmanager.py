import sys
import socket
import threading
import time
import traceback
from httplib import HTTPConnection
import threading
import json

from inits import *

# The Controller's Agent Manager.
# Communicates with the Agent.

class AgentConnection(object):
    
    def __init__(self, conn, addr):
        self.socket = conn
        self.addr = addr
        self.httpconn = False
        self.auth = {}

    def set_httpconn(self, httpconn):
        self.httpconn = httpconn

    def set_auth(self, auth):
        self.auth = auth

class AgentManager(threading.Thread):

    PORT = 8888

    def __init__(self, host='localhost', port=0):
        super(AgentManager, self).__init__()
        self.daemon = True
        self.host = host
        self.port = port and port or self.PORT
        self.socket = None

        # A dictionary with all AgentConnections
        # "primary" or "archive", etc.
        self.agents = {}

    def register(self, agent, agent_type):
        # fixme: What should we do if two primary agents connect?
        print "Remembering new agent of type:", agent_type
        self.agents[agent_type] = agent

    # Return the list of all agents
    def all_agents(self):
        return self.agents

    def agent_handle(self, agent_type):
        """Returns an instance of an Agent of the requested type."""
        if self.agents.has_key(agent_type):
            return self.agents[agent_type]

        return False

    def lock(self):
        # fixme: add
        pass

    def unlock(self):
        # fixme: add
        pass

    def run(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(8)

        while True:
            conn, addr = self.socket.accept()

            tobj = threading.Thread(target=self.new_agent_connection,
                                 args=(conn, addr))
            # Spawn a thread to handle the new agent connection
            tobj.start()

    # thread function: spawned on a new connection from an agent.
    def new_agent_connection(self, conn, addr):
        try:
            agent = AgentConnection(conn, addr)

            # sleep for 100ms to prevent:
            #  'An existing connection was forcibly closed by the remote host'
            # on the Windows client when the agent tries to connect.
            time.sleep(.1);

            httpconn = ReverseHTTPConnection(conn)

            # Send the 'auth 'command.
            httpconn.request('POST', '/auth')

            res = httpconn.getresponse()
            print >> sys.stderr, 'command: auth: ' + str(res.status) + ' ' + str(res.reason)
            # Get the auth reply.
            print "reading....",
            body_json = res.read()
            if body_json:
                body = json.loads(body_json)
                print "\nbody = ", body
            else:
                print "done."

            # todo: inspect the reply to see what kind of agent it is
            # and make sure it has all the required values.
            # Fake it for now.
            if not body.has_key("type"):
                print "missing agent type from agent"
                conn.close()
                return

            agent_type = body['type']
            if agent_type not in [ AGENT_TYPE_PRIMARY,
                        AGENT_TYPE_WORKER, AGENT_TYPE_OTHER ]:
                print "Bad agent type sent:", agent_type
                conn.close()
                return

            agent.set_httpconn(httpconn)
            agent.set_auth(body)

            self.register(agent, agent_type)

        except socket.error, e:
            print "Socket error"
            conn.close()
        except Exception, e:
            print "Exception:"
            traceback.format_exc()
            print str(e)
            print traceback.format_exc()
#            self.log.error(str(e))
#            self.log.error(traceback.format_exc())

class ReverseHTTPConnection(HTTPConnection):
    
    def __init__(self, sock):
        HTTPConnection.__init__(self, 'agent')
#        HTTPConnection.debuglevel = 1
        self.sock = sock
    
    def connect(self):
        pass

    def close(self):
        pass
