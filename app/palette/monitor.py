from sqlalchemy import or_
from webob import exc

from collections import OrderedDict

# pylint: disable=import-error,no-name-in-module
from akiri.framework.ext.sqlalchemy import meta
# pylint: enable=import-error,no-name-in-module

from controller.tableau import TableauProcess
from controller.state import StateManager
from controller.agent import Agent, AgentVolumesEntry
from controller.agentmanager import AgentManager
from controller.firewall_manager import FirewallEntry
from controller.ports import PortEntry
from controller.profile import Role
from controller.state_control import StateControl
from controller.util import sizestr, DATEFMT, utc2local
from controller.licensing import LicenseEntry
from controller.extracts import ExtractManager
from controller.event_control import EventControl

from event import EventApplication
from rest import PaletteRESTHandler

__all__ = ["MonitorApplication"]

class Colors(object):
    RED_NUM = 1
    YELLOW_NUM = 2
    GREEN_NUM = 3

    color_to_str = {
        RED_NUM: "red",
        YELLOW_NUM: "yellow",
        GREEN_NUM: "green"
    }

    color_to_num = {
        'red': RED_NUM,
        'yellow': YELLOW_NUM,
        'green': GREEN_NUM
    }

class MonitorApplication(PaletteRESTHandler):

    NAME = 'monitor'

    def __init__(self, global_conf):
        super(MonitorApplication, self).__init__(global_conf)
        self.event = EventApplication(global_conf)

    def getindex(self, req, name):
        try:
            return int(req.GET[name])
        except (TypeError, ValueError):
            pass
        return 0

    def status_options(self, req):
        current_key = 'status' in req.GET and req.GET['status'] or '0'
        options = [{'option':'All Status', 'id':0}]
        for x in ['E', 'W', 'I']:
            options.append({'option':EventControl.level_strings[x], 'id':x})
        if current_key == '0':
            value = options[0]['option']
        else:
            value = EventControl.level_strings[current_key]
        return {'name':'status', 'value':value,
                'id':current_key, 'options':options}

    def type_options(self, req):
        current_key = 'type' in req.GET and req.GET['type'] or '0'
        options = [{'option':'All Types', 'id':0}]

        d = {'name':'type'}
        types = OrderedDict()
        items = sorted(EventControl.types().items(), key=lambda x: x[1])
        for key, value in items:
            types[key] = value
        for key in types:
            if key == current_key:
                d['value'] = types[key]
                d['id'] = key
            options.append({'option':types[key], 'id':key})
        if 'id' not in d:
            d['value'] = options[0]['option']
            d['id'] = 0
        d['options'] = options
        return d

    def publisher_options(self, req):
        sysid = self.getindex(req, 'publisher')

        options = [{'option':'All Publishers', 'id':0}]
        d = {'name':'publisher'}
        for publisher in ExtractManager.publishers():
            if publisher.system_user_id == sysid:
                d['value'] = publisher.friendly_name
                d['id'] = publisher.system_user_id
            options.append({'option':publisher.friendly_name,
                      'id':publisher.system_user_id})
        if not 'id' in d:
            d['value'] = options[0]['option']
            d['id'] = options[0]['id']
        d['options'] = options
        return d

    def disk_watermark(self, req, name):
        """ Threshold for the disk indicator. (low|high) """
        try:
            value = req.system.get('disk-watermark-'+name)
        except ValueError:
            return float(100)
        return float(value)

    def disk_color(self, used, size, low, high):
        if used > high / 100 * size:
            return 'red'
        if used > low / 100 * size:
            return 'yellow'
        return 'green'

    def volume_info(self, req, agent):
        low = self.disk_watermark(req, 'low')
        high = self.disk_watermark(req, 'high')

        volumes = []
        query = meta.Session.query(AgentVolumesEntry).\
            filter(AgentVolumesEntry.agentid == agent.agentid)
        if agent.iswin:
            query = query.filter(or_(AgentVolumesEntry.vol_type == 'Fixed',
                             AgentVolumesEntry.vol_type == 'Network'))
        for vol in query.order_by(AgentVolumesEntry.name).all():
            if not vol.size or vol.available_space is None:
                continue
            used = vol.size - vol.available_space
            value = '%s free of %s' % \
                (sizestr(vol.available_space), sizestr(vol.size))
            color = self.disk_color(used, vol.size, low, high)
            volumes.append({'name': vol.name, 'value': value, 'color': color})
        return volumes

    def firewall_info(self, agent):
        rows = meta.Session.query(FirewallEntry).\
            filter(FirewallEntry.agentid == agent.agentid).\
            order_by(FirewallEntry.port).\
            all()

        ports = []
        for entry in rows:
            fw_dict = {'name': entry.name,
                        'num': entry.port,
                        'color': entry.color
            }
            ports.append(fw_dict)

        return ports

    def out_ports(self, agent):

        rows = meta.Session.query(PortEntry).\
            filter(PortEntry.agentid == agent.agentid).\
            filter(PortEntry.color != None).\
            order_by(PortEntry.dest_port).\
            all()

        ports = []
        for entry in rows:
            out_dict = {'name': entry.service_name,
                        'num': entry.dest_port,
                        'color': entry.color}
            ports.append(out_dict)

        return ports

    def license_info(self, agentid):
        entry = LicenseEntry.get_by_agentid(agentid)
        if entry is None:
            return {'value':'unknown', 'color':'yellow'}
        if entry.valid():
            return {'value':'valid', 'color':'green'}
        else:
            return {'value':'invalid', 'color':'red'}

    def lowest_color(self, info_list):
        lowest_color_num = Colors.GREEN_NUM

        for info in info_list:
            if not 'color' in info:
                continue
            color_num = Colors.color_to_num[info['color']]
            if color_num < lowest_color_num:
                lowest_color_num = color_num

        return lowest_color_num

    def handle_monitor(self, req):
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements
        # Get the state

        agent_entries = meta.Session.query(Agent).\
            filter(Agent.envid == req.envid).\
            order_by(Agent.display_order).\
            order_by(Agent.displayname).\
            all()

        main_state = None
        for entry in agent_entries:
            if entry.agent_type == AgentManager.AGENT_TYPE_PRIMARY and \
                                                            not entry.enabled:
                main_state = StateManager.STATE_PRIMARY_NOT_ENABLED

        if not main_state:
            main_state = StateManager.get_state_by_envid(req.envid)

        state_control_entry = StateControl.get_state_control_entry(main_state)
        if not state_control_entry:
            print "UNKNOWN STATE!  State:", main_state
            # fixme: stop everything?  Log this somewhere?
            return

        allowable_actions = []
        if req.remote_user.roleid >= Role.MANAGER_ADMIN:
            # Convert the space-separated string to a list, e.g.
            # "start stop reset" --> ["start", "stop", "reset"]
            s = state_control_entry.allowable_actions
            if s:
                allowable_actions = s.split(' ')

        # The overall color starts at the state_control color.
        # It can get worse (e.g. green to yellow or red) , but not better
        # (e.g. red to yellow or green).
        color = state_control_entry.color
        if color in Colors.color_to_num:
            color_num = Colors.color_to_num[color]
        else:
            color_num = Colors.RED_NUM

        if main_state in (StateManager.STATE_STOPPED,
                StateManager.STATE_STOPPED_UNEXPECTED,
                StateManager.STATE_STARTED, StateManager.STATE_DEGRADED,
                StateManager.STATE_PENDING, StateManager.STATE_DISCONNECTED):
            user_action_in_progress = False
        else:
            user_action_in_progress = True

        agent_worker_stopped = False
        agents = []
        for entry in agent_entries:
            if not entry.enabled:
                continue
            # Start out green until proven otherwise
            agent_color_num = Colors.GREEN_NUM

            agent = {}
            agent['uuid'] = entry.uuid
            agent['displayname'] = entry.displayname
            agent['display_order'] = entry.display_order
            agent['hostname'] = entry.hostname
            agent['agent_type'] = entry.agent_type
            agent['version'] = entry.version
            agent['ip_address'] = entry.ip_address
            agent['listen_port'] = entry.listen_port

            if entry.creation_time:
                # Since creation_time is set on commit() there is a very
                # small window where the creation_time may be None.
                creation_time = utc2local(entry.creation_time)
                agent['creation-time'] = creation_time.strftime(DATEFMT)
            if entry.modification_time != None:
                modtime = utc2local(entry.modification_time)
                agent['modification_time'] = modtime.strftime(DATEFMT)
            else:
                agent['modification_time'] = ""

            last_connection_time = utc2local(entry.last_connection_time)
            agent['last-connnection-time'] = \
                                    last_connection_time.strftime(DATEFMT)
            if entry.last_disconnect_time:
                last_disconnect_time = utc2local(entry.last_disconnect_time)
                agent['last-disconnect-time'] = \
                                    last_disconnect_time.strftime(DATEFMT)

            if main_state in (StateManager.STATE_DISCONNECTED,
                              StateManager.STATE_PENDING) and \
                          entry.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
                agent_color_num = Colors.RED_NUM
                if main_state == StateManager.STATE_DISCONNECTED:
                    # "Tableau Status Unknown"
                    msg = 'Disconnected'
                    if 'last-disconnect-time' in agent:
                        msg = msg + ' ' + agent['last-disconnect-time']
                elif main_state == StateManager.STATE_PENDING:
                    # "Retrieving Tableau Status"
                    msg = "Retrieving Tableau Status"
                else:
                    # UNKNOWN: An agent has never connected
                    msg = 'No agent has ever connected'
                agent['warnings'] = [{'color':'red', 'message': msg}]
            elif entry.connected():
                if entry.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
                    agent['license'] = self.license_info(entry.agentid)

                    lic_color = Colors.color_to_num[agent['license']['color']]
                    if lic_color < agent_color_num:
                        agent_color_num = lic_color

                agent['volumes'] = self.volume_info(req, entry)
                agent['in_ports'] = self.firewall_info(entry)
                agent['out_ports'] = self.out_ports(entry)

                vol_lowest_color = self.lowest_color(agent['volumes'])
                firewall_lowest_color = self.lowest_color(agent['in_ports'])
                out_ports_lowest_color = self.lowest_color(agent['out_ports'])

                if vol_lowest_color < agent_color_num:
                    agent_color_num = vol_lowest_color
                if firewall_lowest_color < agent_color_num:
                    agent_color_num = firewall_lowest_color
                if out_ports_lowest_color < agent_color_num:
                    agent_color_num = out_ports_lowest_color
            else:
                agent_color_num = Colors.RED_NUM
                msg = 'Disconnected'
                if 'last-disconnect-time' in agent:
                    msg = msg + ' ' + agent['last-disconnect-time']
                agent['warnings'] = [{'color':'red', 'message': msg}]

            if entry.agent_type in (AgentManager.AGENT_TYPE_PRIMARY,
                                    AgentManager.AGENT_TYPE_WORKER) and \
                                    main_state == StateManager.STATE_STOPPED:
                agent_color_num = Colors.YELLOW_NUM
                agent['warnings'] = [{'color':'yellow',
                                      'message': 'Tableau stopped'}]
                if entry.agent_type == AgentManager.AGENT_TYPE_WORKER:
                    agent_worker_stopped = True
            elif entry.agent_type in (AgentManager.AGENT_TYPE_PRIMARY,
                                    AgentManager.AGENT_TYPE_WORKER) and \
                        main_state == StateManager.STATE_STOPPED_UNEXPECTED:
                agent_color_num = Colors.RED_NUM
                agent['warnings'] = [{'color':'red',
                                      'message': 'Tableau stopped'}]
                if entry.agent_type == AgentManager.AGENT_TYPE_WORKER:
                    agent_worker_stopped = True

            if entry.agent_type == AgentManager.AGENT_TYPE_PRIMARY or \
                        entry.agent_type == AgentManager.AGENT_TYPE_WORKER:

                # Add tableau processes for this agent
                status_entries = meta.Session.query(TableauProcess).\
                    filter(TableauProcess.agentid == entry.agentid).\
                    order_by(TableauProcess.name).\
                    all()

                tableau_procs = []
                for tab_entry in status_entries:
                    proc = {}

                    if tab_entry.pid == 0:
                        continue

                    if tab_entry.pid == -1:
                        # Special case: Error such as
                        # ""Connection error contacting worker 1"
                        agent_color_num = Colors.RED_NUM
                        agent['warnings'] = [{'color':'red',
                                              'message': tab_entry.name}]
                        # This is close to the truth and results in
                        # the main state being set to DEGRADED.
                        agent_worker_stopped = True
                        continue

                    proc['pid'] = tab_entry.pid
                    proc['name'] = tab_entry.name
                    proc['status'] = tab_entry.status
                    if tab_entry.status == 'running':
                        proc['color'] = 'green'
                    else:
                        proc['color'] = 'red'
                        # The agent needs to be red too.
                        agent_color_num = Colors.RED_NUM

                    tableau_procs.append(proc)

                agent['details'] = tableau_procs

                if entry.agent_type == AgentManager.AGENT_TYPE_WORKER and \
                                                    not len(status_entries):
                    # If a worker doesn't have any Tableau processes listed,
                    # then make the worker RED with a message.
                    # This is probably due to the primary not being
                    # connected or not receiving tableau status yet.
                    warning = {'color': 'red',
                               'message': 'Tableau processes unavailable'}

                    if 'warnings' in agent:
                        agent['warnings'].append(warning)
                    else:
                        agent['warnings'] = warning

                    agent_color_num = Colors.RED_NUM

            else:
                # For now, only primaries and workers have details
                agent['details'] = []

            agent['color'] = Colors.color_to_str[agent_color_num]
            agents.append(agent)

            # Set the overall status lower if this agent status was lower.
            if agent_color_num < color_num:
                color_num = agent_color_num

        # If the primary is running and any worker is stopped, set
        # the status to DEGRADED.
        if main_state == StateManager.STATE_STARTED and agent_worker_stopped:
            main_state = StateManager.STATE_DEGRADED
            # allowable_actions are the same for STARTED and DEGRADED, so
            # we don't need to update.
            state_control_entry = \
                            StateControl.get_state_control_entry(main_state)
            if not state_control_entry:
                print "UNKNOWN STATE.  State:", main_state
                # fixme: stop everything?  Log this somewhere?
                return

            color_num = Colors.RED_NUM

        # Special case: If Upgrading, set the main state to
        # "upgrading", etc.
        if StateManager.upgrading_by_envid(req.envid):
            main_state = StateManager.STATE_UPGRADING

            state_control_entry = \
                            StateControl.get_state_control_entry(main_state)
            if not state_control_entry:
                print "UNKNOWN STATE!  State:", main_state
                # fixme: stop everything?  Log this somewhere?
                return

            allowable_actions = []
            if req.remote_user.roleid >= Role.MANAGER_ADMIN:
                # Convert the space-separated string to a list, e.g.
                # "start stop reset" --> ["start", "stop", "reset"]
                s = state_control_entry.allowable_actions
                if s:
                    allowable_actions = s.split(' ')

            color = state_control_entry.color
            if color in Colors.color_to_num:
                color_num = Colors.color_to_num[color]
            else:
                color_num = Colors.RED_NUM

        environments = [{"name": "My Servers", "agents": agents}]

        config = [self.status_options(req),
                  self.type_options(req)]

        monitor_ret = {'state': main_state,
                       'allowable-actions': allowable_actions,
                       'text': state_control_entry.text,
                       'icon': state_control_entry.icon,
                       'color': Colors.color_to_str[color_num],
                       'user-action-in-progress': user_action_in_progress,
                       'environments': environments,
                       'config': config
                      }

        seq = req.getint('seq')
        if not seq is None:
            monitor_ret['seq'] = seq

        if not 'event' in req.GET or \
           ('event' in req.GET and req.GET['event'] != 'false'):

            events = self.event.handle_GET(req)
            monitor_ret['events'] = events['events']
            monitor_ret['item-count'] = events['count']

        return monitor_ret

    def handle(self, req):
        if req.environ['PATH_INFO'] == '/monitor':
            return self.handle_monitor(req)
        raise exc.HTTPBadRequest()
