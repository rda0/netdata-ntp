# -*- coding: utf-8 -*-
# Description: ntp netdata python.d module
# Author: Sven Mäder (rda0)

from base import SimpleService
import socket
import struct
import re

# default module values
update_every = 1
priority = 90000
retries = 60

# NTP Control Message Protocol constants
MODE = 6
HEADER_FORMAT = '!BBHHHHH'
HEADER_LEN = 12
OPCODES = {
    'readstat': 1,
    'readvar': 2
}

# Maximal dimension precision
PRECISION = 1000000

# Static charts
ORDER = [
    'sys_offset',
    'sys_jitter',
    'sys_frequency',
    'sys_wander',
    'sys_rootdelay',
    'sys_rootdisp',
    'sys_stratum',
    'sys_tc',
    'sys_precision'
]

CHARTS = {
    'sys_offset': {
        'options': [None, "Combined offset of server relative to this host", "ms", 'system', 'ntp.sys_offset', 'area'],
        'lines': [
            ['offset', 'offset', 'absolute', 1, PRECISION]
        ]},
    'sys_jitter': {
        'options': [None, "Combined system jitter and clock jitter", "ms", 'system', 'ntp.sys_jitter', 'line'],
        'lines': [
            ['sys_jitter', 'system', 'absolute', 1, PRECISION],
            ['clk_jitter', 'clock', 'absolute', 1, PRECISION]
        ]},
    'sys_frequency': {
        'options': [None, "Frequency offset relative to hardware clock", "ppm", 'system', 'ntp.sys_frequency', 'area'],
        'lines': [
            ['frequency', 'frequency', 'absolute', 1, PRECISION]
        ]},
    'sys_wander': {
        'options': [None, "Clock frequency wander", "ppm", 'system', 'ntp.sys_wander', 'area'],
        'lines': [
            ['wander', 'clock', 'absolute', 1, PRECISION]
        ]},
    'sys_rootdelay': {
        'options': [None, "Total roundtrip delay to the primary reference clock", "ms", 'system', 'ntp.sys_rootdelay', 'area'],
        'lines': [
            ['rootdelay', 'delay', 'absolute', 1, PRECISION]
        ]},
    'sys_rootdisp': {
        'options': [None, "Total root dispersion to the primary reference clock", "ms", 'system', 'ntp.sys_rootdisp', 'area'],
        'lines': [
            ['rootdisp', 'dispersion', 'absolute', 1, PRECISION]
        ]},
    'sys_stratum': {
        'options': [None, "Stratum (1-15)", "1", 'system', 'ntp.sys_stratum', 'line'],
        'lines': [
            ['stratum', 'stratum', 'absolute', 1, PRECISION]
        ]},
    'sys_tc': {
        'options': [None, "Time constant and poll exponent (3-17)", "log2 s", 'system', 'ntp.sys_tc', 'line'],
        'lines': [
            ['tc', 'current', 'absolute', 1, PRECISION],
            ['mintc', 'minimum', 'absolute', 1, PRECISION]
        ]},
    'sys_precision': {
        'options': [None, "Precision", "log2 s", 'system', 'ntp.sys_precision', 'line'],
        'lines': [
            ['precision', 'precision', 'absolute', 1, PRECISION]
        ]}
}

# Dynamic charts templates
PEER_PREFIX = 'peer'

PEER_DIMENSIONS = [
    ['offset', 'Filter offset', 'ms'],
    ['delay', 'Filter delay', 'ms'],
    ['dispersion', 'Filter dispersion', 'ms'],
    ['jitter', 'Filter jitter', 'ms'],
    ['xleave', 'Interleave delay', 'ms'],
    ['rootdelay', 'Total roundtrip delay to the primary reference clock', 'ms'],
    ['rootdisp', 'Total root dispersion to the primary reference clock', 'ms'],
    ['stratum', 'Stratum (1-15)', '1'],
    ['hmode', 'Host mode (1-6)', '1'],
    ['pmode', 'Peer mode (1-5)', '1'],
    ['hpoll', 'Host poll exponent', 'log2 s'],
    ['ppoll', 'Peer poll exponent', 'log2 s'],
    ['precision', 'Precision', 'log2 s']
]

PEER_CHART_TEMPLATE = {
    'options': [None, None, None, 'peers', None, 'line'],
    'lines': None
}

PEER_DIMENSION_TEMPLATE = [None, None, 'absolute', 1, PRECISION]


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.host = 'localhost'
        self.port = 'ntp'
        addrinfo = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_DGRAM)[0]
        self.family = addrinfo[0]
        self.sockaddr = addrinfo[4]
        self.peer = None
        self.request_systemvars = None
        self.regex_srcadr = re.compile(r'srcadr=([A-Za-z0-9.-]+)')
        self.regex_refid = re.compile(r'refid=([A-Za-z]+)')
        self.regex_data = re.compile(r'([a-z_]+)=([0-9-]+(?:\.[0-9]+)?)(?=,)')
        self.order = None
        self.definitions = None

    def get_peer_order(self):
        order = list()
        for dimension in PEER_DIMENSIONS:
            order.append('_'.join([PEER_PREFIX, dimension[0]]))
        return order

    def get_peer_charts(self):
        charts = dict()
        for dimension in PEER_DIMENSIONS:
            chart_id = '_'.join([PEER_PREFIX, dimension[0]])
            chart_context = '.'.join(['ntp', chart_id])
            charts[chart_id] = dict(PEER_CHART_TEMPLATE)
            charts[chart_id]['options'][1] = dimension[1]
            charts[chart_id]['options'][2] = dimension[2]
            charts[chart_id]['options'][4] = chart_context
        return charts

    def init_charts(self):
        """
        Creates the charts dynamically
        """
        self.order = ORDER
        self.definitions = CHARTS
        if self.peer:
            self.order += self.get_peer_order()
            self.definitions.update(self.get_peer_charts())
            for dimension in PEER_DIMENSIONS:
                lines = list()
                for peer in self.peer['ids']:
                    line = list(PEER_DIMENSION_TEMPLATE)
                    line[0] = '_'.join([self.peer['names'][peer], dimension[0]])
                    lines.append(line)
                chart = '_'.join([PEER_PREFIX, dimension[0]])
                self.definitions[chart]['lines'] = lines

    def init_peers(self):
        """
        Checks ntp for available peers.
        Queries each peer once to have data for charts.
        Adds all peers whith valid data.
        If no valid peers found, disable peer charts.
        """
        # Reset peers
        peer = dict()
        peer['index'] = 0
        peer['error'] = 0
        peer['ids'] = list()
        peer['names'] = dict()
        peer['requests'] = dict()

        # Get the peer ids
        readstat = self.get_header(0, 'readstat')
        peer_ids = self.get_peer_ids(self._get_raw_data(readstat))
        peer_ids.sort()

        # Get peer data
        for peer_id in peer_ids:
            request = self.get_header(peer_id, 'readvar')
            raw = self._get_raw_data(request)
            if not raw:
                continue
            data = self.get_data_from_raw(raw)
            if not data:
                continue
            match_srcadr = self.regex_srcadr.search(raw)
            if not match_srcadr:
                continue
            name = match_srcadr.group(1).replace('.', '-')
            if name == '0-0-0-0':
                continue
            if name.startswith('127-'):
                continue
            match_refid = self.regex_refid.search(raw)
            if match_refid:
                name = '_'.join([name, match_refid.group(1).lower()])

            peer['ids'].append(peer_id)
            peer['names'][peer_id] = name
            peer['requests'][peer_id] = request

        if peer['ids']:
            self.peer = peer
        else:
            self.peer = None

    def check(self):
        """
        Checks if we can get valid systemvars.
        If not, returns None to disable module.
        """
        self.request_systemvars = self.get_header(0, 'readvar')
        raw_systemvars = self._get_raw_data(self.request_systemvars)
        if not self.get_data_from_raw(raw_systemvars):
            return None

        self.init_peers()
        self.init_charts()

        return True

    def _get_data(self):
        """
        Gets systemvars data on each update.
        Gets peervars data for only one peer on each update.
        Total amount of _get_raw_data invocations per update = 2
        """
        data = dict()

        raw_systemvars = self._get_raw_data(self.request_systemvars)
        data.update(self.get_data_from_raw(raw_systemvars))

        if self.peer:
            if self.peer['index'] >= len(self.peer['ids']):
                self.peer['index'] = 0
            peer = self.peer['ids'][self.peer['index']]
            self.peer['index'] += 1

            raw_peervars = self._get_raw_data(self.peer['requests'][peer])
            data.update(self.get_data_from_raw(raw_peervars, peer))

        if not data:
            self.error("No data received")
            return None
        return data
    
    def _get_raw_data(self, request):
        """
        Gets data via UDP socket.
        """
        try:
            sock = socket.socket(self.family, socket.SOCK_DGRAM)
            sock.connect(self.sockaddr)
            sock.settimeout(5)
            sock.send(request)
            raw = sock.recv(1024)
        except socket.timeout:
            self.error('Socket timeout')
            return None
        finally:
            sock.close()

        if not raw:
            self.error('No data received from socket')
            return None

        return raw

    def get_data_from_raw(self, raw, peer=0):
        """
        Extracts key=value pairs with float/integer from ntp response packet data.
        """
        data = dict()
        try:
            data_list = self.regex_data.findall(raw)
            for data_point in data_list:
                key, value = data_point
                if peer:
                    dimension = '_'.join([self.peer['names'][peer], key])
                else:
                    dimension = key
                data[dimension] = int(float(value) * PRECISION)
        except (ValueError, AttributeError, TypeError):
            self.error("Invalid data received")
            return None

        # If peer returns no valid data, probably due to ntpd restart,
        # then wait 5 updates and re-initialize the peers and charts
        if not data and peer:
            self.error('Peer error: No data received')
            self.peer['error'] += 1
            if self.peer['error'] > 5:
                self.error('Peer error count exceeded, re-initializing peers and charts.')
                self.init_peers()
                self.init_charts()
                self.create()

        return data
    
    def get_header(self, associd=0, operation='readvar'):
        """
        Constructs the NTP Control Message header:
         0                   1                   2                   3
         0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |LI |  VN |Mode |R|E|M| OpCode  |       Sequence Number         |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |            Status             |       Association ID          |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |            Offset             |            Count              |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        """
        try:
            opcode = OPCODES[operation]
        except KeyError:
            return None
        version = 2
        sequence = 1
        status = 0
        offset = 0
        count = 0
        try:
            header = struct.pack(HEADER_FORMAT, (version << 3 | MODE), opcode,
                                 sequence, status, associd, offset, count)
            return header
        except struct.error:
            return None

    def get_peer_ids(self, res):
        """
        Unpack the NTP Control Message header
        Get data length from header
        Get list of association ids returned in the readstat response
        """
        try:
            count = struct.unpack(HEADER_FORMAT, res[:HEADER_LEN])[6]
        except struct.error:
            return None
        if not count:
            return None

        data_end = HEADER_LEN + count
        data = res[HEADER_LEN:data_end]
        data_format = ''.join(['!', 'H' * int(count / 2)])

        try:
            return list(struct.unpack(data_format, data))[::2]
        except struct.error:
            return None
