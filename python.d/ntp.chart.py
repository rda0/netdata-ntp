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

MODE = 6
HEADER_FORMAT = '!BBHHHHH'
HEADER_LEN = 12
OPCODES = {
    'readstat': 1,
    'readvar': 2
}

PRECISION = 1000000

ORDER_SYSTEM = [
    'sys_offset',
    'sys_jitter',
    'sys_frequency',
    'sys_wander',
    'sys_rootdelay',
    'sys_rootdisp',
    'sys_stratum',
    'sys_tc',
    'sys_precision']

ORDER_PEER = [
    'peer_offset',
    'peer_delay',
    'peer_dispersion',
    'peer_jitter',
    'peer_xleave',
    'peer_rootdelay',
    'peer_rootdisp',
    'peer_stratum',
    'peer_hmode',
    'peer_pmode',
    'peer_hpoll',
    'peer_ppoll',
    'peer_precision']

CHARTS_SYSTEM = {
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

CHARTS_PEER = {
    'peer_offset': {
        'options': [None, "Filter offset", "ms", 'peers', 'ntp.peer_offset', 'line'],
        'lines': [
            ['offset']
        ]},
    'peer_delay': {
        'options': [None, "Filter delay", "ms", 'peers', 'ntp.peer_delay', 'line'],
        'lines': [
            ['delay']
        ]},
    'peer_dispersion': {
        'options': [None, "Filter dispersion", "ms", 'peers', 'ntp.peer_dispersion', 'line'],
        'lines': [
            ['dispersion']
        ]},
    'peer_jitter': {
        'options': [None, "Filter jitter", "ms", 'peers', 'ntp.peer_jitter', 'line'],
        'lines': [
            ['jitter']
        ]},
    'peer_xleave': {
        'options': [None, "Interleave delay", "ms", 'peers', 'ntp.peer_xleave', 'line'],
        'lines': [
            ['xleave']
        ]},
    'peer_rootdelay': {
        'options': [None, "Total roundtrip delay to the primary reference clock", "ms", 'peers', 'ntp.peer_rootdelay', 'line'],
        'lines': [
            ['rootdelay']
        ]},
    'peer_rootdisp': {
        'options': [None, "Total root dispersion to the primary reference clock", "ms", 'peers', 'ntp.peer_rootdisp', 'line'],
        'lines': [
            ['rootdisp']
        ]},
    'peer_stratum': {
        'options': [None, "Stratum (1-15)", "1", 'peers', 'ntp.peer_stratum', 'line'],
        'lines': [
            ['stratum']
        ]},
    'peer_hmode': {
        'options': [None, "Host mode (1-6)", "1", 'peers', 'ntp.peer_hmode', 'line'],
        'lines': [
            ['hmode']
        ]},
    'peer_pmode': {
        'options': [None, "Peer mode (1-5)", "1", 'peers', 'ntp.peer_pmode', 'line'],
        'lines': [
            ['pmode']
        ]},
    'peer_hpoll': {
        'options': [None, "Host poll exponent", "log2 s", 'peers', 'ntp.peer_hpoll', 'line'],
        'lines': [
            ['hpoll']
        ]},
    'peer_ppoll': {
        'options': [None, "Peer poll exponent", "log2 s", 'peers', 'ntp.peer_ppoll', 'line'],
        'lines': [
            ['ppoll']
        ]},
    'peer_precision': {
        'options': [None, "Precision", "log2 s", 'peers', 'ntp.peer_precision', 'line'],
        'lines': [
            ['precision']
        ]}
}


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.host = 'localhost'
        self.port = 'ntp'
        addrinfo = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_DGRAM, socket.IPPROTO_UDP)[0]
        self.family = addrinfo[0]
        self.sockaddr = addrinfo[4]
        self.assocs = list()
        self.peers = dict()
        self.requests = dict()
        self.index = 0
        self.order = ORDER_SYSTEM + ORDER_PEER
        self.definitions = CHARTS_SYSTEM
        self.regex_srcadr = re.compile(r'srcadr=(?P<srcadr>[A-Za-z0-9.-]+)')
        self.regex_refid = re.compile(r'refid=(?P<refid>[A-Za-z]+)')
        self.regex_data = re.compile(r'([a-z_]+)=([0-9-]+(?:\.[0-9]+)?)(?=,)')

    def get_header(self, associd=0, operation='readvar'):
        """Construct the NTP Control Message header
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

    def get_assoc_ids(self, res):
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

    def check(self):
        systemvars = self.get_header(0, 'readvar')
        if not self._get_raw_data(systemvars):
            return None
        self.requests[0] = systemvars

        readstat = self.get_header(0, 'readstat')
        assocs = self.get_assoc_ids(self._get_raw_data(readstat))
        assocs.sort()
        for assoc in assocs:
            req = self.get_header(assoc, 'readvar')
            res = self._get_raw_data(req)
            if not res:
                continue
            match_data = self.regex_data.findall(res)
            if not match_data:
                continue
            match_srcadr = self.regex_srcadr.search(res)
            if match_srcadr:
                srcadr = match_srcadr.groupdict()
                name = srcadr['srcadr'].replace('.', '-')
                if name == '0-0-0-0':
                    continue
                if name.startswith('127-'):
                    continue
            else:
                name = str(assoc)
            match_refid = self.regex_refid.search(res)
            if match_refid:
                refid = match_refid.groupdict()['refid'].lower()
                name = '_'.join([name, refid])
            self.assocs.append(assoc)
            self.peers[assoc] = name
            self.requests[assoc] = req

        charts = CHARTS_PEER
        for chart in charts:
            dimension_template = charts[chart]['lines'][0][0]
            charts[chart]['lines'] = list()
            for assoc in self.assocs:
                dimension = '_'.join([self.peers[assoc], dimension_template])
                line = [dimension, None, 'absolute', 1, PRECISION]
                charts[chart]['lines'].append(line)
        self.definitions.update(charts)

        if not self.assocs:
            return None
        return True

    def _get_raw_data(self, request):
        try:
            sock = socket.socket(self.family, socket.SOCK_DGRAM)
            sock.connect(self.sockaddr)
            sock.settimeout(5)
            sock.send(request)
            raw_data = sock.recv(1024)
        except socket.timeout:
            self.error('Socket timeout')
            return None
        finally:
            sock.close()

        if not raw_data:
            self.error('No data received from socket')
            return None

        return raw_data

    def _get_data(self):
        data = dict()

        raw_data = self._get_raw_data(self.requests[0])
        try:
            data_list = self.regex_data.findall(raw_data)
            for data_point in data_list:
                key, value = data_point
                data[key] = int(float(value) * PRECISION)

        except (ValueError, AttributeError, TypeError):
            self.error("Invalid data received")
            return None

        if self.index >= len(self.assocs):
            self.index = 0
        assoc = self.assocs[self.index]
        self.index += 1
        raw_data = self._get_raw_data(self.requests[assoc])
        try:
            data_list = self.regex_data.findall(raw_data)
            for data_point in data_list:
                key, value = data_point
                dimension = '_'.join([self.peers[assoc], key])
                data[dimension] = int(float(value) * PRECISION)

        except (ValueError, AttributeError, TypeError):
            self.error("Invalid data received")
            return None

        if not data:
            self.error("No data received")
            return None
        return data
