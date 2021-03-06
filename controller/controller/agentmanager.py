import logging
import os
import socket
import ssl
import select
import threading
import time
import json
import traceback

import exc
import httplib

from sqlalchemy import func, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm.session import make_transient

import akiri.framework.sqlalchemy as meta

from agent import Agent, AgentVolumesEntry
from diskcheck import DiskCheck, DiskException
from state import StateManager
from event_control import EventControl
from firewall import Firewall
from odbc import ODBC
from filemanager import FileManager
from system import SystemKeys
from util import sizestr, is_ip, traceback_string, failed

logger = logging.getLogger()

def protected(f):
    """Decorater."""
    def realf(self, *args, **kwargs):
        self.lock()
        try:
            return f(self, *args, **kwargs)
        finally:
            self.unlock()
    return realf

# The Controller's Agent Manager.
# Communicates with the Agent.
# fixme: maybe combine with the Agent class.
class AgentConnection(object):
    # pylint: disable=too-many-instance-attributes
    _CID = 1

    def __init__(self, server, conn, addr, peername):
        self.server = server
        self.socket = conn
        self.addr = addr
        self.peername = peername
        self.httpconn = False   # Used by the controller
        self.auth = {}          # Used by the controller
        self.agentid = None
        self.uuid = None
        self.displayname = None
        self.agent_type = None
        self.yml_contents = None    # only valid if agent is a primary
        self.initting = True
        self.last_activity = time.time()
        self.sent_disconnect_event = False

        # Each agent connection has its own lock to allow only
        # one thread to send/recv  on the agent socket at a time.
        self.lockobj = threading.RLock()

        # A lock to allow only one user action (backup/restore/etc.)
        # at a time.
        self.user_action_lockobj = threading.RLock()

        self.filemanager = FileManager(self)

        # unique identifier
        # can never be 0
        self.conn_id = AgentConnection._CID
        AgentConnection._CID += 1
        if AgentConnection._CID == 0:
            AgentConnection._CID += 1

    def _httpexc(self, res, method='GET', body=None):
        if body is None:
            body = res.read()
        raise exc.HTTPException(res.status, res.reason,
                                method=method, body=body)

    def http_send(self, method, uri, body=None, headers=None):
        if headers is None:
            headers = {}
        # Check to see if state is not PENDING or DISCONNECTED?
        self.lock()
        try:
            self.httpconn.request(method, uri, body, headers)
            res = self.httpconn.getresponse()
            # GONE can be returned from filemanager
            if res.status not in (httplib.OK, httplib.GONE):
                self._httpexc(res, method=method)
            return res.read()
        finally:
            self.unlock()

    def http_send_json(self, uri, data, headers=None):
        if headers is None:
            headers = {}
        headers['Content-Type'] = 'application/json'
        body = json.dumps(data)
        return self.http_send('POST', uri, body=body, headers=headers)

    # This function is slighly diffent, it proxies a GET through the agent.
    # It return the HTTPResponse object but with a 'body' member which is
    #  the result of the calling read().
    def http_send_get(self, url, timeout=None):
        headers = {'Content-Type': 'application/json'}
        data = {'URL': url}
        if not timeout is None:
            data['timeout'] = timeout
        body = json.dumps(data)

        self.lock()
        try:
            self.httpconn.request('GET', '/proxy', body=body, headers=headers)
            res = self.httpconn.getresponse()
            if res.status < 200 or res.status >= 300:
                self._httpexc(res, method='GET')
            res.body = res.read()
            return res
        finally:
            self.unlock()

    def lock(self):
        self.lockobj.acquire()

    def unlock(self):
        self.lockobj.release()

    def user_action_lock(self, blocking=True):
        return self.user_action_lockobj.acquire(blocking)

    def user_action_unlock(self):
        self.user_action_lockobj.release()

# FIXME: prefix private method names with an '_'.
# pylint: disable=too-many-public-methods

# FIXME: subclass Manager
class AgentManager(threading.Thread):
    # pylint: disable=too-many-instance-attributes
    PORT = 22

    SSL_HANDSHAKE_TIMEOUT_DEFAULT = 5

    # Agent types
    AGENT_TYPE_PRIMARY = "primary"
    AGENT_TYPE_WORKER = "worker"
    AGENT_TYPE_ARCHIVE = "archive"

    AGENT_TYPE_NAMES = {AGENT_TYPE_PRIMARY:'Tableau Primary Server',
                        AGENT_TYPE_WORKER: 'Tableau Worker Server',
                        AGENT_TYPE_ARCHIVE:'Non Tableau Server'}

    # Displayname templates
    PRIMARY_TEMPLATE = "Tableau Primary" # not a template since only 1
    WORKER_TEMPLATE = "Tableau Worker %d"

    # Starting point for worker/archive displayname numbers.
    WORKER_START = 100
    ARCHIVE_START = 200

    @classmethod
    def get_type_name(cls, key):
        return AgentManager.AGENT_TYPE_NAMES[key]

    def __init__(self, server):
        super(AgentManager, self).__init__()
        self.server = server
        self.system = server.system
        self.config = self.server.config
        self.domainid = self.server.domain.domainid
        self.envid = self.server.environment.envid
        self.metrics = self.server.metrics
        self.upgrade_rwlock = self.server.upgrade_rwlock

        self.daemon = True
        # This agent is now gone
        self.lockobj = threading.RLock()

        # Trigger retrieval of tableau status for cases such as
        # primary connected, "start" finished, etc.
        self.check_status_event = threading.Event()

        self.port_main = self.config.getint('controller', 'agent_port',
                                            default=self.PORT)
        self.port_clear = self.config.getint('controller', 'agent_port_clear',
                                              default=None)
        self.socket = None
        # A dictionary with all AgentConnections with the key being
        # the unique 'conn_id'.
        self.agents = {}

        self.socket_timeout = self.system[SystemKeys.SOCKET_TIMEOUT]
        self.ping_interval = self.system[SystemKeys.PING_REQUEST_INTERVAL]

        self.ssl = self.config.getboolean('controller', 'ssl', default=True)
        if self.ssl:
            system_key = SystemKeys.SSL_HANDSHAKE_TIMEOUT
            self.ssl_handshake_timeout = self.system[system_key]

            if not self.config.has_option('controller', 'ssl_cert_file'):
                msg = "Missing 'ssl_cert_file' certificate file specification"
                logger.critical(msg)
                raise IOError(msg)
            self.cert_file = self.config.get('controller', 'ssl_cert_file')
            if not os.path.exists(self.cert_file):
                logger.critical("ssl enabled, but no ssl certificate: %s",
                                self.cert_file)
                raise IOError("Certificate file not found: " + self.cert_file)

    def update_last_disconnect_time(self):
        """Called during startup to set a disconnection time for agents that
           were still connected when we stopped."""

        session = meta.Session()

        session.query(Agent).\
            filter(or_(Agent.last_connection_time > \
                           Agent.last_disconnect_time, \
                           Agent.last_disconnect_time == None)).\
                           update({"last_disconnect_time" : func.now()}, \
                                      synchronize_session=False)
        session.commit()


    @protected
    def register(self, agent, orig_agent_type):
        """
           - Checks agent uuid and type against already connected agents.
           - Calculates a displayname and order if it is a new agent.
           - Adds the agent to the connected agents dictionary.
       """

        logger.debug("register: new agent name %s, uuid %s, conn_id %d", \
                     agent.hostname, agent.uuid, agent.connection.conn_id)

        new_agent_type = agent.agent_type

        if (agent.displayname is None or agent.displayname == "") or \
           (new_agent_type == AgentManager.AGENT_TYPE_WORKER and \
              orig_agent_type == AgentManager.AGENT_TYPE_ARCHIVE and \
              self._displayname_changeable(agent)):
            logger.debug("register: setting or changing displayname for %s",
                         str(agent.displayname))

            (displayname, display_order) = self._calc_new_displayname(agent)
            agent.displayname = displayname
            agent.display_order = display_order

        # Don't allow two primary agents to be connected and
        # don't allow two agents with the same name to be connected.
        # Keep the newest one.
        for key in self.agents:
            atmp = self.agents[key]
            if atmp.uuid == agent.uuid:
                logger.info("Agent already connected with uuid '%s': "
                            "will remove it and use the new connection.",
                            agent.uuid)
                self.remove_agent(atmp, ("An agent is already connected " + \
                    "with uuid '%s': will remove it and use the new " + \
                        "connection.") % (agent.uuid), gen_event=False)
                break
            elif new_agent_type == AgentManager.AGENT_TYPE_PRIMARY and \
                        atmp.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
                logger.info("A primary agent is already connected: "
                            "Will remove it and keep the new primary agent "
                            "connection.")
                self.remove_agent(atmp,
                        "A primary agent is already connected: Will " + \
                        "remove it and keep the new primary agent " + \
                        "connection.", gen_event=False)

        # If a previously connected agent was removed, above,
        # in "remove_agent()", the agent's last_disconnect_time was
        # updated.  Update the "last_connection_time" now to make
        # sure the connection time is later than the disconnect time
        # for the agent.
        agent.last_connection_time = func.now()

        logger.debug("register agent: %s", agent.displayname)

        self.agents[agent.connection.conn_id] = agent

        logger.debug("register: orig_agent_type: %s, new_agent_type: %s",
                       str(orig_agent_type), new_agent_type)
        if new_agent_type == AgentManager.AGENT_TYPE_PRIMARY:
            logger.debug("register: Initializing state entries on connect")
            self.server.state_manager.update(StateManager.STATE_PENDING)

            # Check to see if we need to reclassify archive agents as
            # worker agents.  For example, a worker may have
            # connected before the primary ever connected with its
            # yml file that tells us the ip addresses of workers.
            self.set_all_agent_types()

        return True

    def set_all_agent_types(self):
        """Look through the list of agents and reclassify archive agents as
        worker agents if needed.  For example, a worker may have
        connected and set as "archive" before the primary ever connected
        with its yml file that tells us the ip addresses of workers.

        Also potentially changes the displaynames if a worker
        was previously classified and named as an archive.
        """
        session = meta.Session()

        rows = session.query(Agent).\
            filter(Agent.agent_type != AgentManager.AGENT_TYPE_PRIMARY).\
            all()

        for entry in rows:
            if self.is_tableau_worker(entry):
                agent_type = AgentManager.AGENT_TYPE_WORKER
            else:
                agent_type = AgentManager.AGENT_TYPE_ARCHIVE
            logger.debug("set_all_agent_types for %s. Was %s is %s.",
                         entry.displayname, entry.agent_type, agent_type)

            if entry.agent_type != agent_type:
                logger.debug("Correcting agent type from %s to %s",
                             entry.agent_type, agent_type)
                # Set the agent to the correct type.
                entry.agent_type = agent_type

                # We correct displaynames only for workers.
                if agent_type != AgentManager.AGENT_TYPE_WORKER:
                    continue

                # Possibly correct displayname.
                if self._displayname_changeable(entry):
                    (displayname, display_order) = \
                                            self._calc_new_displayname(entry)
                    entry.displayname = displayname
                    entry.display_order = display_order

        session.commit()

    def _displayname_changeable(self, agent):
        """Determine whether or not we can change the displayname.
           We can change the displayname if the displayname isn't set yet.
           Otherwise, we can't unless the displayname unless it
           looks like the default displayname that we created (not the user)
           is still being used that was set when a worker was classified
           and named the hostname.
        """

        if agent.displayname is None or agent.displayname == "":
            # We are the first to name this one.
            logger.debug("naming: Empty displayname. Changeable.")
            return True

        if agent.agent_type != AgentManager.AGENT_TYPE_WORKER:
            # Only workers could potentially need to be renamed/classified.
            logger.debug("naming: Wrong type to change: %s", agent.agent_type)
            return False

        # Let's see if the worker is using a displayname we probably gave it
        # when we thought it was an archive.

        if agent.displayname == agent.hostname:
            logger.debug("naming: it was named earlier: Can rename: %s",
                         agent.displayname)
            return True
        else:
            return False

    def _calc_new_displayname(self, new_agent):
        """
            Returns (agent-display-name, agent-display-order)
            The current naming scheme:
                Tableau Primary
                Tableau Worker 1
                Tableau Worker 2
                    ...
                hostname of archive
                    ...
                    ...
            Note:
                We should be called with the agent lock so archive
                agents don't end up with duplicate names.
        """
        if new_agent.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
            return (AgentManager.PRIMARY_TEMPLATE, 1)

        if new_agent.agent_type == AgentManager.AGENT_TYPE_ARCHIVE:
            return self._calc_archive_name(new_agent)

        if new_agent.agent_type == AgentManager.AGENT_TYPE_WORKER:
            return self._calc_worker_name(new_agent)

        logger.error("calc_new_displayname: INVALID agent type: %s",
                     new_agent.agent_type)
        return ("INVALID AGENT TYPE: %s" % new_agent.agent_type, 0)

    def _calc_worker_name(self, new_agent):
        """Calculate the worker name and display order.
           We look for the "workerX.host" entry that has
           our ip address."""

        try:
            hosts = self.get_yml_list('worker.hosts')
        except ValueError, ex:
            logger.error("calc_worker_name: %s", str(ex))
            return (AgentManager.WORKER_TEMPLATE % 0,
                    AgentManager.WORKER_START)

        if len(hosts) <= 1:
            logger.error("calc_worker_name: host count is too small: %d: %s",
                         len(hosts), str(hosts))
            return (AgentManager.WORKER_TEMPLATE % 0,
                    AgentManager.WORKER_START)

        dot = new_agent.hostname.find('.')
        if dot == -1:
            hostname = new_agent.hostname
        else:
            # Remove domain name
            hostname = new_agent.hostname[:dot]

        for worker_num in range(1, len(hosts)+1):
            # Get entry for "worker%d.host".  Its value is worker's IP address.
            worker_key = "worker%d.host" % worker_num

            value = self.server.yml.get(worker_key, default=None)
            if not value:
                logger.error("calc_worker_name: Missing yml key: %s",
                             worker_key)
                return (AgentManager.WORKER_TEMPLATE % 0,
                        AgentManager.WORKER_START)

            # If the value is anything we're known by, then use it
            if is_ip(value):
                if value != new_agent.ip_address:
                    continue
            else:
                dot = value.find('.')
                if dot != -1:
                    worker = value[:dot]
                else:
                    worker = value
                if worker.upper() != hostname.upper():
                    continue
            logger.debug("calc_worker_name: We are %s (%s)",
                         worker_key, value)
            return (AgentManager.WORKER_TEMPLATE % worker_num,
                        AgentManager.WORKER_START + worker_num)

        logger.error("calc_worker_name: yml file was missing our " + \
                     "IP (%s) or name: %s", new_agent.ip_address,
                     new_agent.hostname)

        return (AgentManager.WORKER_TEMPLATE % 0,
                AgentManager.WORKER_START)

    def _calc_archive_name(self, new_agent):
        """Choose the archive name and initial display order."""

        if new_agent.hostname != None and new_agent.fqdn != "":
            return (new_agent.hostname,
                    AgentManager.ARCHIVE_START)

        logger.error("calc_archive_name: agent has no hostname! Don't know "
                     "what to name it: uuid: %s", new_agent.uuid)

        return ("UNNAMED NON-WORKER/PRIMARY", AgentManager.WORKER_START)


    def update_agent_pinfo_dirs(self, agent, pinfo):
        """Update the directory information returned from pinfo.
           We do not update the volume-related information here,
           since a disk-usage event requires a displayname and
           we may not know the displayname yet.

           Note: Do not call this method unless the agent_type
           is known and has been set."""

        if not agent.agent_type:
            logger.error("Unknown agent type for agent: " + agent.displayname)

        # FIXME: make automagic based on self.__table__.columns
        # Below are the only ones really needed as the others come
        # from 'auth' and are unrelated to tableau.
        if 'tableau-install-dir' in pinfo:
            agent.tableau_install_dir = pinfo['tableau-install-dir']
        if 'tableau-data-dir' in pinfo:
            agent.tableau_data_dir = pinfo['tableau-data-dir']
        if 'tableau-data-size' in pinfo:
            agent.tableau_data_size = pinfo['tableau-data-size']

        return True

    def update_agent_pinfo_other(self, agent, pinfo):
        """Update other information from pinfo, such as the IP address,
           if it has changed."""

        # If 'hostname' is ever updated from pinfo, mind 'static-hostname'

        if 'ip-address' in pinfo and pinfo['ip-address'] != agent.ip_address:
            logger.debug("update_agent_info_other: "
                         "Updating ip address from %s to %s",
                         agent.ip_address, pinfo['ip-address'])
            agent.ip_address = pinfo['ip-address']
            session = meta.Session()
            agentid = agent.agentid

            session.query(Agent).\
                filter(Agent.agentid == agentid).\
                       update({"ip_address" : agent.ip_address},
                       synchronize_session=False)
            session.commit()

    def update_agent_pinfo_vols(self, agent, pinfo):
        """Update volume-related information from pinfo.
           Checks the disk-usage of each volume and generates an
           alert if above a disk watermark.

           This should be called only after the agent type
           type is known.

           If displayname is sent, then disk-usage events will
           not be sent since the event needs that."""
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals

        if not agent.agent_type:
            logger.error("Unknown agent type for agent: " + agent.displayname)
            return False

        session = meta.Session()

        agentid = agent.agentid

        # Set all of the agent volumes to 'inactive'.
        # Each volume pinfo sent us will later be set to 'active'.
        session.query(AgentVolumesEntry).\
            filter(AgentVolumesEntry.agentid == agentid).\
                   update({"active" : False}, synchronize_session=False)

        aconn = agent.connection
        if agent.iswin:
            if aconn.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
                if not 'tableau-data-dir' in pinfo:
                    logger.error("Missing 'tableau-data-dir' in pinfo: %s",
                                 pinfo)
                    return False
                parts = pinfo['tableau-data-dir'].split(':')
                if len(parts) != 2:
                    logger.error("Bad format for tableau-install-dir: %s",
                                 pinfo['tableau-data-dir'])
                    return False

            # fixme
            parts = agent.data_dir.split(':')
            if len(parts) != 2:
                logger.error("Bad format for data-dir: %s", agent.data_dir)
                return False
            palette_data_dir = agent.path.join(parts[1], self.server.DATA_DIR)
        else:
            palette_data_dir = agent.path.join(agent.data_dir,
                                               self.server.DATA_DIR)

        (low_water, high_water) = \
            self.disk_watermark('low'), self.disk_watermark('high')

        if 'volumes' in pinfo:
            volumes_sorted = sorted(pinfo['volumes'],
                                    key=lambda k: k['name'], reverse=True)
            if not agent.iswin:
                linux_archive_volume_found = 0

            for volume in volumes_sorted:
                if 'name' in volume:
                    name = volume['name']
                    if agent.iswin:
                        name = name.upper()
                else:
                    logger.error("volume missing 'name' in pinfo for "
                                 "agentid %d. Will ignore: %s",
                                 agentid, str(volume))
                    continue

                # Check to see if the volume already exists.
                try:
                    entry = session.query(AgentVolumesEntry).\
                        filter(AgentVolumesEntry.agentid == agentid).\
                        filter(AgentVolumesEntry.name == name).\
                        one()
                except NoResultFound:
                    entry = None

                if not entry is None:
                    # Merge it into the existing volume entry.
                    # It should already have archive, archive_limit, etc.
                    if 'size' in volume:
                        entry.size = volume['size']

                    if 'type' in volume:
                        entry.vol_type = volume['type']

                    if entry.vol_type == "Fixed" or not agent.iswin:
                        # There are two cases when we need to update limit
                        # 1. The volume existed before, but was not "Fixed"
                        # (maybe a CDROM).
                        # 2. The volume size got changed.
                        entry.archive_limit = entry.size
                        entry.archive = True

                        if not entry.path:
                            if 'path' in volume:
                                entry.path = volume['path']
                            else:
                                entry.path = palette_data_dir

                    if 'label' in volume:
                        entry.label = volume['label']

                    if 'drive-format' in volume:
                        entry.drive_format = volume['drive-format']

                    if 'available-space' in volume:
                        entry.available_space = volume['available-space']

                    if agent.displayname != None and \
                            'size' in volume and 'available-space' in volume:
                        usage_color = self.disk_color(\
                            entry.size - entry.available_space,
                                            entry.size, low_water, high_water)

                        usage_color = usage_color[0:1]

                        if usage_color != entry.watermark_notified_color:
                            if (usage_color == 'g' and  \
                                        entry.watermark_notified_color) or \
                                                        usage_color != 'g':
                                # A disk usage event had been generated
                                # for low usage and now we're back to green.
                                #   OR
                                # There is a change in the disk usage
                                # color, so generate an event.
                                self.gen_disk_event(agent, usage_color, entry,
                                    ((entry.size - entry.available_space) / \
                                                    float(entry.size)) * 100.)
                                entry.watermark_notified_color = usage_color

                    entry.active = True  # Note the agent reported it
                else:
                    # Add the volume
                    if 'type' in volume:
                        entry = AgentVolumesEntry.build(agent, volume,
                                                        palette_data_dir)

                        if entry.archive and not agent.iswin:
                            if linux_archive_volume_found:
                                # Can be only one archive for Linux
                                # We sorted the volumes by name in reverse
                                # order so '/' is checked last.
                                if entry.name != '/':
                                    logger.error("entry.archive True "
                                                 "not agent.iswin, "
                                                 "linux_archive_volume_found "
                                                 "and entry.name != '/': %s",
                                                 entry.name)
                                entry.archive = False
                            else:
                                linux_archive_volume_found = True

                        if agent.displayname != None and \
                              'size' in volume and 'available-space' in volume:
                            usage_color = self.disk_color(\
                                entry.size - entry.available_space,
                                        entry.size, low_water, high_water)

                            usage_color = usage_color[0:1]

                            if usage_color != 'g':
                                self.gen_disk_event(agent, usage_color, entry,
                                    ((entry.size - entry.available_space) / \
                                                    float(entry.size)) * 100.)
                                entry.watermark_notified_color = usage_color

                        session.add(entry)

        session.commit()

        return True

    def gen_disk_event(self, agent, usage_color, entry, percent):

        if usage_color == 'g':
            event = EventControl.DISK_USAGE_OKAY
        elif usage_color == 'y':
            event = EventControl.DISK_USAGE_ABOVE_LOW_WATERMARK
        elif usage_color == 'r':
            event = EventControl.DISK_USAGE_ABOVE_HIGH_WATERMERK
        else:
            logger.error("gen_disk_event: Invalid usage color: " + usage_color)
            return

        msg = \
            ("Volume name: %s\nSize: %s\nUsed: %s\nAvailable: %s\n" +\
            "Percent used: %2.1f%%\n") % \
            (entry.name, sizestr(entry.size),
             sizestr(entry.size - entry.available_space),
             sizestr(entry.available_space), percent)

        data = agent.todict()
        data['info'] = msg
        data['volume_name'] = entry.name
        self.server.event_control.gen(event, data)

    def disk_watermark(self, name):
        """ Threshold for the disk indicator. (low|high) """
        # FIXME: remove this and use SystemKeys
        try:
            value = self.system['disk-watermark-'+name]
        except ValueError:
            return float(100)
        return float(value)

    def disk_color(self, used, size, low, high):
        if used > high / 100 * size:
            return 'red'
        if used > low / 100 * size:
            return 'yellow'
        return 'green'

    def is_tableau_worker(self, agent):
        """Returns True if the passed agent
           known to be a tableau worker host.  The type of tableau host is
           reported in the tableau primary host's yml file on the
           "worker.hosts" line.  For example:
                worker.hosts:  DEV-PRIMARY, 10.0.0.102
            The first host is the primary, and subsequent hosts
            are the workers.
        """

        try:
            hosts = self.get_yml_list('worker.hosts')
        except ValueError:
            return False

        if len(hosts) == 1:
            return False

        dot = agent.hostname.find('.')
        if dot == -1:
            hostname = agent.hostname
        else:
            # Remove domain name
            hostname = agent.hostname[:dot]

        for worker in hosts[1:]:
            if is_ip(worker):
                if worker == agent.ip_address:
                    return True
            else:
                dot = worker.find('.')
                if dot != -1:
                    # Remove domain name from this possible worker name
                    worker = worker[:dot]
                if worker.upper() == hostname.upper():
                    return True
        return False

    def get_yml_list(self, yml_key):
        """Get the yml value such as 'worker.hosts' or 'gateway.hosts'
           from the yml file and return the list."""

        # get() raises ValueError if not found.
        value = self.server.yml.get(yml_key)

        # For 'worker.hosts', the value is in the format:
        #       "DEV-PRIMARY, 10.0.0.102"
        # where the first host is the primary and the remaining are
        # Tableau workers.
        hosts = [x.strip() for x in value.split(',')]
        return hosts

    def set_displayname(self, aconn, uuid, displayname):
        session = meta.Session()
        try:
            entry = session.query(Agent).\
                filter(Agent.uuid == uuid).one()
            entry.displayname = displayname
            session.commit()
            if aconn:
                aconn.displayname = displayname
        except NoResultFound:
            raise ValueError('No agent found with uuid=%s' % (uuid))

    def forget(self, agent):
        """Looks for an agent with the same uuid and conn_id.
           Returns:
                True    success
                False   couldn't find it or invalid agent.
        """

        if not agent.agentid:
            logger.debug("forget:  Won't try to forget agentid of None")
            # Can happen if we sent a failed command to the agent
            # that hasn't been remembered yet.
            return False

        session = meta.Session()
        try:
            # FIXME: make this a method of Agent.
            session.query(Agent).\
                filter(Agent.agentid == agent.agentid).\
                filter(Agent.conn_id == agent.conn_id).\
                one()
        except NoResultFound:
            logger.debug("forget: Not found "
                         "(was probably recently updated with a "
                         "new conn_id by a new thread).  "
                         "agentid: %d, conn_id: %d",
                         agent.agentid, agent.conn_id)
        else:
            logger.debug("forget: Forgot agentid: %d, conn_id: %d",
                         agent.agentid, agent.conn_id)

        session.query(Agent).\
            filter(Agent.agentid == agent.agentid).\
            update({'last_disconnect_time': func.now()},
                   synchronize_session=False)

        #If we do this, conn_id is overwritten with the wrong/old value.
        #entry.last_disconnect_time = func.now()
        session.commit()
        return True

    def all_agents(self, enabled_only=True):
        """Return the list of connected agents.
           Argument enabled_only:  If True, return only enabled agents.
        """

        if not enabled_only:
            return self.agents

        # Return only enabled agents
        enabled_agents = {}
        for key in self.agents.keys():
            try:
                agent = self.agents[key]
            except KeyError:
                continue

            temp_agent = Agent.get_by_uuid(self.envid, agent.uuid)
            make_transient(temp_agent)
            if temp_agent == None:
                logger.info("all_agents: agent unexpected gone from db: %s",
                            agent.displayname)
                continue

            if not temp_agent.enabled:
                continue

            enabled_agents[key] = agent

        return enabled_agents

    def agent_by_agentid(self, agentid):

        agents = self.all_agents()  # gets the list of ENABLED agents

        agent = None
        for key in agents.keys():

            try:
                agent = agents[key]
            except KeyError:
                # This agent is now gone
                continue

            if agent.agentid == agentid:
                return agent

        return agent

    def agent_connected(self, aconn):
        """Check to see if the passed AgentConnection is still connected.
            The agent may be disabled.

        Returns:
            True if still conencted.
            False if not connected.
        """
        return aconn.conn_id in self.agents

    def agent_by_type(self, agent_type):
        """Returns an instance of an agent of the requested type
           if the agent is connected and enabled.

            Returns None if no agents of that type are connected.
        """

        for key in self.all_agents():   # The list of ENABLED agents
            try:
                if self.agents[key].agent_type == agent_type:
                    agent = self.agents[key]
                    return agent
            # agent can go away while we are in this loop.
            except KeyError:
                continue

        return None

    def agent_conn_by_type(self, agent_type):
        """Returns an instance of a connected agent of the requested type,
        or a list of instances if more than one agent of that type
        is connected.

        Only ENABLED agents are returned.

        Returns None if no agents of that type are connected."""

        for key in self.all_agents():
            try:
                if self.agents[key].agent_type == agent_type:
                    return self.agents[key].connection
            except KeyError:
                continue

        return None

    def agent_by_uuid(self, uuid):
        """Search for agents with the given uuid.
            Return an instance of it, or None if none match.
        """
        for key in self.all_agents():   # Returns ENABLED agents
            try:
                if self.agents[key].uuid == uuid:
                    return self.agents[key]
            except KeyError:
                continue
        return None

    def agent_by_id(self, agentid):
        """Search for agents with the given agentid.
            Return an instance of it, or None if none match.
        """
        for key in self.all_agents():   # Returns ENABLED agents
            try:
                if self.agents[key].agentid == agentid:
                    return self.agents[key]
            except KeyError:
                continue
        return None

    # DEPRECATED
    def agent_conn_by_uuid(self, uuid):
        """Search for agents with the given uuid.
            Return an instance of it, or None if none match.
        """
        agent = self.agent_by_uuid(uuid)
        return agent and agent.connection or None

    @protected
    def remove_agent(self, agent, reason="", gen_event=True):
        """Remove an agent.
            Args:
                agent:       The agent to remove.
                reason:      An optional message, describing why.
                gen_event:   True or False.  If True, generates an event.
                             If False does not generate an event.
        """
        gen_event = True    # Force it for now (fixme)

        if reason == "":
            reason = "Agent communication failure"

        session = meta.Session()
        make_transient(agent)

        uuid = agent.uuid
        conn_id = agent.connection.conn_id
        forgot = False
        if self.agents.has_key(conn_id):
            logger.debug("Removing agent with conn_id %d, uuid %s, " + \
                         "name %s, reason: %s", conn_id, uuid,
                         self.agents[conn_id].connection.auth['hostname'],
                         reason)

            # Need to update the last_disconect_time before generating
            # the event so the disconnect event has the correct
            # last_disconnect_time.
            forgot = self.forget(agent)
            if gen_event:
                # get the latest from the DB incase the display name changed
                temp_agent = Agent.get_by_id(agent.agentid)
                data = temp_agent.todict()
                data['error'] = reason
                data['info'] = ("\nAgent type: %s\n" + \
                                "Agent connection-id: %d\n" + \
                                "Agent uuid %s") % \
                                (temp_agent.displayname, conn_id, uuid)
                if not agent.connection.sent_disconnect_event:
                    self.server.event_control.gen(EventControl.AGENT_DISCONNECT,
                                                  data)
                    agent.connection.sent_disconnect_event = True
                else:
                    logger.debug("Already sent the disconnect for conn_id %d",
                                 conn_id)
            logger.debug("remove_agent: closing agent socket.")
            if self._close(agent.connection.socket):
                logger.debug("remove_agent: close agent socket succeeded")
            else:
                logger.debug("remove_agent: close agent socket failed")

            del self.agents[conn_id]    # Deletes original one
        else:
            logger.debug("remove_agent: No agent with conn_id %d", conn_id)

        if not forgot:
            return False

        if agent.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
            logger.debug("remove_agent: Initializing state entries on removal")
            self.server.state_manager.update(StateManager.STATE_DISCONNECTED)
            # Note: We don't update/clear the "reported" state from
            # a previous agent, so the user will see the last
            # real state.

        try:
            session.expunge(agent)      # Removes the other one
        except InvalidRequestError, ex:
            logger.error("remove_agent expunge error: %s", str(ex))
        #make_transient(agent)  # done above
        logger.error("after expunge: %s", str(agent.todict()))

        try:
            meta.Session.remove()
        except InvalidRequestError, ex:
            logger.error("remove_agent remove error: %s", str(ex))

    def _close(self, sock):
        logger.warn("agentmanager._close socket")
        try:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except socket.error as ex:
            logger.debug("agentmanager._close socket failure: " + str(ex))
            return False
        return True

    def lock(self):
        """Locks the agents list"""
        self.lockobj.acquire()

    def unlock(self):
        """Unlocks the agents list"""
        self.lockobj.release()

    def _create_listen_socket(self, port, host):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except socket.error as ex:
            logger.error("Fatal error: Could not bind to port %d: %s",
                         port, str(ex))
            # NOTE: this call to _exit is correct.
            # pylint: disable=protected-access
            os._exit(99)

        sock.listen(8)
        logger.debug("Listening on port %d on %s", port, host)
        return sock

    def run(self):
        # For the main port, listen on all interfaces/public
        sock_main = self._create_listen_socket(self.port_main, '0.0.0.0')

        socks = [sock_main] # sockets we're listening on

        if self.port_clear:
            sock_clear = self._create_listen_socket(self.port_clear, '0.0.0.0')
            socks.append(sock_clear)    # Also listen on this one
        else:
            sock_clear = None

        session = meta.Session()
        self.server.system.save(SystemKeys.UPGRADING, 'no')
        self.server.state_manager.update(StateManager.STATE_DISCONNECTED)
        session.commit()

        while True:
            logger.debug("about to select on %s", str(socks))
            readable, _, _ = select.select(socks, [], [])
            logger.debug("select returned: %s", readable)
            for sock in readable:
                try:
                    conn, addr = sock.accept()
                except socket.error:
                    logger.debug("Accept failed on socket %d.", sock.fileno())
                    continue

                if sock.fileno() == sock_main.fileno():
                    ssl_enable = self.ssl
                elif sock_clear.fileno() and \
                                    sock.fileno() == sock_clear.fileno():
                    ssl_enable = False
                else:
                    logger.debug("Bad code: sock fileno %d, main %d",
                                    sock.fileno(), sock_main.fileno())
                    if sock_clear:
                        logger.debug("sock_clear fileno %d",
                                                    sock_clear.fileno())
                    # pylint: disable=protected-access
                    os._exit(101)

                tobj = threading.Thread(target=self.handle_agent_connection_pre,
                                        args=(conn, addr, ssl_enable))
                # Spawn a thread to handle the new agent connection
                tobj.start()

    def _shutdown(self, sock):
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except EnvironmentError:
            pass

    def socket_fd_closed(self, filedes):
        """called with agentmanager lock"""
        for key in self.agents:
            agent = self.agents[key]
            logger.debug("agent fileno to close: %d", agent.socket.fileno())
            if agent.connection.socket.fileno() == filedes:
                logger.debug("Agent closed connection for: %s", key)
                agent.socket.close()
                del self.agents[key]
                return

        logger.error("Couldn't find agent with fd: %d", filedes)

    def handle_agent_connection_pre(self, conn, addr, ssl_enable):
        """Thread function: spawned on a new connection from an agent."""

        try:
            self.handle_agent_connection(conn, addr, ssl_enable)
        except (SystemExit, KeyboardInterrupt, GeneratorExit):
            raise
        except BaseException:
            line = traceback_string(all_on_one_line=False)
            self.server.event_control.gen(EventControl.SYSTEM_EXCEPTION,
                                      {'error': line,
                                       'version': self.server.version})
            logger.error("Fatal: Exiting agent_handle_connection_pre " + \
                         "on exception.")
            # pylint: disable=protected-access
            os._exit(90)

    def handle_agent_connection(self, conn, addr, ssl_enable):
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-return-statements
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        try:
            peername = conn.getpeername()[0]
        except socket.error, ex:
            peername = "Unknown peername: %s" % str(ex)

        if ssl_enable:
            try:
                conn.settimeout(self.ssl_handshake_timeout)
                ssl_sock = ssl.wrap_socket(conn, server_side=True,
                                           certfile=self.cert_file)
                conn = ssl_sock
            except (ssl.SSLError, socket.error), ex:
                logger.info("Exception with ssl wrap from addr %s, " + \
                            "peername %s: %s", addr, peername, str(ex))
                # http://bugs.python.org/issue9211, though takes
                # a while to garbage collect and close the fd.
                self._shutdown(conn)
                return

        conn.settimeout(self.socket_timeout)

        session = meta.Session()

        self.upgrade_rwlock.read_acquire()
        acquired = True
        agent = None

        try:
            aconn = AgentConnection(self.server, conn, addr, peername)
            logger.debug("New socket accepted from addr %s, "
                         "peername %s, conn_id %d",
                         addr, peername, aconn.conn_id)

            # sleep for 100ms to prevent:
            #  'An existing connection was forcibly closed by the remote host'
            # on the Windows client when the agent tries to connect.
            time.sleep(.1)

            aconn.httpconn = ReverseHTTPConnection(conn, aconn)
            # FIXME: why is this a POST?
            body_json = aconn.http_send('POST', '/auth')
            if body_json:
                logger.debug("/auth returned " + str(body_json))
                try:
                    body = json.loads(body_json)
                except ValueError as ex:
                    logger.info("agentmanager with new connection from %s "
                                "sent bad json data for /auth response: "
                                "'%s'. Error: '%s'.  "
                                "Will close the connection.",
                                peername, body_json, str(ex))
                    self._close(conn)
                    return
            else:
                body = {}
                logger.debug("done.")

            # Inspect the reply to make sure it has all the required values.
            required = ['version',      # original
                        'os-version',
                        'processor-type',
                        'processor-count',
                        'installed-memory',
                        'hostname',     # original
                        'fqdn',
                        'ip-address',   # original
                        'listen-port',  # original
                        'uuid',         # original
                        'install-dir',  # original
                        'data-dir'
                        ]

            for item in required:
                if not body.has_key(item):
                    logger.error("Missing '%s' from agent", item)
                    self._close(conn)
                    return

            # Get the latest controller license key in case it has changed.
            domain_entry = \
                        self.server.domain.get_by_name(self.server.domainname)
            license_key = domain_entry.license_key
            if license_key:
                if not body.has_key('license-key'):
                    logger.error("Agent missing required 'license-key'")
                    self._close(conn)
                    return
                agent_key = body['license-key'].strip()
                if agent_key != license_key:
                    logger.error("Agent license is incorrect '%s' != '%s'",
                                 agent_key, license_key)
                    self._close(conn)
                    return

            aconn.auth = body

            agent = Agent.build(self.envid, aconn)
            agent.connection = aconn
            if agent.enabled:
                self.setup_agent(agent)
            else:
                # If the agent isn't enabled, only ping and don't go through
                # all of the agent initialization until/if the agent is enabled
                # by the user.
                self.upgrade_rwlock.read_release()
                acquired = False
                if self.ping_check(agent, init_enabled=False):
                    # The agent has been enabled and is still there,
                    # so continue on with the initialization.
                    self.upgrade_rwlock.read_acquire()
                    acquired = True

                    agent = Agent.build(self.envid, aconn)
                    # connection is initialized in reconstruct().
                    agent.connection = aconn
                    self.setup_agent(agent)
                else:
                    logger.debug("handle_agent_connection: unmonitored agent "
                                 "with displayname %s, uuid %s, conn_id %d"
                                 "has disconnected.",
                                 str(agent.displayname), agent.uuid,
                                 agent.connection.conn_id)
                    return

            session = meta.Session()
            session.commit()

            # Tell the status thread to start getting status on
            # the new primary.
            if agent.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
                self.trigger_check_status_event()

            make_transient(agent)

            self.upgrade_rwlock.read_release()
            acquired = False

            self.ping_check(agent)

        except (socket.error, IOError, httplib.HTTPException) as ex:
            logger.warn("handle_agent_connection_error: " + str(ex))
            self._close(aconn.socket)

            if agent:
                # Make sure the agent is marked as disconnected by
                # updating the last_disconnect_time.
                try:
                    session.query(Agent).\
                        filter(Agent.agentid == agent.agentid).\
                        update({'last_disconnect_time': func.now()},
                        synchronize_session=False)
                    session.commit()
                except BaseException as ex:
                    logger.info("Updating failed agent "
                                "last_disconnect_time failed: %s", str(ex))
        finally:
            if acquired:
                self.upgrade_rwlock.read_release()
            try:
                # Use " ifinspect(agent).session" when we go to sqlalchemy
                # > 0.8
                make_transient(agent)
            except StandardError:
                pass

            meta.Session.remove()   # does a rollback()

    def trigger_check_status_event(self):
        self.check_status_event.set()

    def clear_check_status_event(self):
        self.check_status_event.clear()

    def setup_agent(self, agent):
        aconn = agent.connection
        uuid = aconn.auth['uuid']
        agent.server = self.server
        agent.firewall = Firewall(agent)
        agent.odbc = ODBC(agent)
        agent.filemanager = FileManager(agent)

        orig_agent_type = agent.agent_type

        try:
            pinfo = self.server.init_new_agent(agent)
        except (IOError, ValueError, exc.InvalidStateError,
                exc.HTTPException, httplib.HTTPException) as ex:
            self._close(aconn.socket)
            logger.error(str(ex))
            logger.debug(traceback.format_exc())
            raise IOError(
                "Bad agent with uuid: '%s', Disconnecting. Error: %s" % \
                (uuid, str(ex)))

        if agent.agent_type is None:
            agent.agent_type = aconn.agent_type

        if agent.displayname is None or agent.displayname == "":
            displayname_needed_setting = True
        else:
            displayname_needed_setting = False

        # Now that we know the agent type, we can update the
        # volume information from pinfo.
        if not self.update_agent_pinfo_vols(agent, pinfo):
            self._close(aconn.socket)
            raise IOError(("pinfo vols bad for agent with uuid: '%s'.  " +
                    "Disconnecting.") % uuid)

        if not self.register(agent, orig_agent_type):
            self._close(aconn.socket)
            raise IOError("Bad agent with uuid: %s'.  Disconnecting." % uuid)

        session = meta.Session()
        session.commit()

        #fixme: not a great place to do this
        #aconn.displayname = agent.displayname

        if not self.save_routes(agent):
            self._close(aconn.socket)
            raise IOError(("Couldn't save_routes for agent with " + \
                           "uuid: %s'.  Disconnecting.") % uuid)

        aconn.initting = False

        self.server.event_control.gen(
            EventControl.AGENT_COMMUNICATION, agent.todict())

        if displayname_needed_setting:
            # Go through the vols again to send any disk events
            # since the agent previously didn't have a displayname
            # and will only send events if it has a displayname.
            # Do this after we send the "AGENT_COMMUNICATION" event
            # or the event order looks wrong.
            if not self.update_agent_pinfo_vols(agent, pinfo):
                self._close(aconn.socket)
                raise IOError(
                    "pinfo vols failed second time for agent with " + \
                    "uuid: '%s'.  Disconnecting." % uuid)

        if agent.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
            self.set_default_backup_destid(agent)

    def set_default_backup_destid(self, agent):
        if agent.agent_type != AgentManager.AGENT_TYPE_PRIMARY:
            # The default would be set to the primary, so wait for
            # the primary to connect and tell us the palette data-dir.
            return

        # If there is no backup configuration BACKUP_DEST_ID yet,
        # create one now.
        backup_dest_id = self.server.system[SystemKeys.BACKUP_DEST_ID]
        if not backup_dest_id is None:
            # It was found, so don't need to add it.
            return

        try:
            (_, primary_entry) = DiskCheck.get_primary_loc(agent, "")
        except DiskException, ex:
            logger.error("set_default_backup_destid: %s", str(ex))
            return

        logger.debug("set_default_backup_destid: volid: %d name %s, path %s",
                     primary_entry.volid, primary_entry.name,
                     primary_entry.path)

        self.server.system.save(SystemKeys.BACKUP_DEST_ID, primary_entry.volid)

    def save_routes(self, agent):
        lines = ""
        rows = meta.Session().query(AgentVolumesEntry).\
            filter(AgentVolumesEntry.agentid == agent.agentid).\
            all()

        lines = []
        for volentry in rows:
            if not volentry.archive:
                continue
            lines.append("%s:%s\r\n" % (volentry.name, volentry.path))

        lines = ''.join(lines)
        route_path = agent.path.join(agent.data_dir, "archive", "routes.txt")

        logger.debug("save_routes: agent hostname '%s': saving to %s: '%s'",
                                    agent.hostname, route_path, lines)
        try:
            body = agent.filemanager.put(route_path, lines)
            if failed(body):
                logger.error("filemanager.put(%s) on %s failed with: %s",
                               agent.displayname, route_path, body['error'])
                return False
        except IOError as ex:
            logger.error("filemanager.put(%s) on %s failed with: %s",
                           agent.displayname, route_path, str(ex))
            return False

        logger.debug("Saved agent file '%s' with contents: %s",
                       route_path, lines)
        return True

    def ping_check(self, agent, init_enabled=True):
        """Each agent has a ping thread that starts out as the initial
           thread processing a new agent's connection.  This thread
           periodically pings the agent to let the agent know we're
           still here and to let us know the agent is still there.

           We are called with 'init_enabled=False' when the
           agent is disabled on initial connection.  In this case,
           we periodically check to see if the agent is now enabled
           and if so, return True which allows continuation of the agent
           initialization.

           Returns:
                True:   Agent is alive.
                False:  Agent did not responsd
            """

        aconn = agent.connection
        conn_id = aconn.conn_id
        while not self.server.noping:
            # Update log level in case it changed
            logger.setLevel(self.system[SystemKeys.DEBUG_LEVEL])

            if agent.enabled:
                if conn_id not in self.all_agents(enabled_only=False):
                    logger.info(
                            "ping_check: agent with connid %d is now gone",
                            conn_id)
                    return False    # end ping thread

            # Check to see if the agent is enabled.  If so,
            # return True to continue on the agent initialization.
            temp_agent = Agent.get_by_uuid(self.envid, agent.uuid)
            make_transient(temp_agent)
            if temp_agent == None:
                logger.error(
                    "ping_check: Agent no longer exists with uuid: %s",
                    agent.uuid)
                return False

            if init_enabled == False and temp_agent.enabled == True:
                # It was disabled on initial connection, but is now enabled,
                # so return to continue the agent initialization.
                logger.debug("ping_check: Initially disabled agent " +
                                "'%s', is now enabled.", agent.displayname)
                return True

            logger.debug("ping: check for agent '%s', type '%s', " + \
                           "uuid '%s', conn_id %d, enabled %s.",
                           str(temp_agent.displayname),
                           str(temp_agent.agent_type),
                           agent.uuid, conn_id,
                           str(temp_agent.enabled))

            if not self.ping_agent(agent):
                logger.info("ping: failed. agent with conn_id %d is gone",
                               conn_id)
                return False
            time.sleep(self.ping_interval)

    def ping_agent(self, agent):
        # pylint: disable=too-many-branches
        """Send a ping to an agent. Returns:
                True:   The ping succeeded
                False:  The ping failed
            """

        stateman = self.server.state_manager

        body = self.server.ping(agent)
        if body.has_key('error'):
            if stateman.upgrading():
                logger.info("Ping During UPDATE: Agent '%s', type '%s', "
                            "uuid '%s', conn_id %d did  not respond to a "
                            "ping.  Ignoring while UPGRADING.",
                            agent.displayname, agent.agent_type,
                            agent.uuid, agent.conn_id)
                return True     # considered a success

            else:
                logger.info(
                    "Ping: Agent '%s', type '%s', uuid '%s', " + \
                    "conn_id %d, did not respond to a ping.  Removing.",
                    agent.displayname, agent.agent_type, agent.uuid,
                    agent.conn_id)

                # Check to see if the agent still exists and is enabled.
                # It could have taken some time for the ping to fail,
                # so maybe the agent is gone or disabled now.
                temp_agent = Agent.get_by_uuid(self.envid, agent.uuid)
                make_transient(temp_agent)
                if temp_agent == None:
                    logger.error(
                        "ping_check: Agent no longer exists with uuid: %s",
                        agent.uuid)
                    return False
                if temp_agent.enabled:
                    # Note we used agent, not temp_agent, since
                    # remove_agent needs the agent.connection.aconn
                    self.remove_agent(agent, "Lost contact with an agent")
                return False
        else:
            logger.debug(
                "Ping: Reply from agent '%s', type '%s', uuid %s, " + \
                "conn_id %d, body: %s",
                    agent.displayname, agent.agent_type, agent.uuid,
                    agent.conn_id, str(body))
            if 'counters' in body:
                for counter in body['counters']:
                    if 'counter-name' not in counter or 'value' not in counter or 'instance-name' not in counter:
                        logger.debug("Missing counter information, skip it")
                        continue

                    counter_name = counter['counter-name']
                    counters_to_metrics = {'cpu': '% Processor Time', 'memory': 'Working Set - private'}

                    if counter_name not in counters_to_metrics.values():
                        # No need to add to metrics
                        continue

                    try:
                        # The values reported by the agents are float numbers
                        value = float(counter['value'])
                    except ValueError as ex:
                        logger.error(
                            "ping: Error obtaining counter value: %s: %s",
                            str(ex), str(body))
                        continue
                    process_name = counter['instance-name']

                    # The counter name adds meaning to the value
                    if counter_name == counters_to_metrics['cpu']:
                        self.metrics.add(agent, process_name, value, None)
                    elif counter_name == counters_to_metrics['memory']:
                        self.metrics.add(agent, process_name, None, value)
                    else:
                        logger.error("Unexpected counter name: '%s' while adding to metrics table!", counter_name)
            return True


class ReverseHTTPConnection(httplib.HTTPConnection):

    def __init__(self, sock, aconn):
        httplib.HTTPConnection.__init__(self, 'agent')
        self.sock = sock
        self.aconn = aconn
        self.aconn.last_activity = time.time()    # update for ping check

    def getresponse(self, buffering=False):
        self.aconn.last_activity = time.time()    # update for ping check
        return httplib.HTTPConnection.getresponse(self, buffering)

    def request(self, method, url, body=None, headers=None):
        if headers is None:
            headers = {}
        self.aconn.last_activity = time.time()    # update for ping check
        httplib.HTTPConnection.request(self, method, url, body, headers)

    def connect(self):
        pass

    def close(self):
        pass
