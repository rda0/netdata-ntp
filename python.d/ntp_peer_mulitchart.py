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

ORDER = ['peer_offset', 'peer_delay', 'peer_dispersion', 'peer_jitter', 'peer_rootdelay', 'peer_rootdisp', 'peer_stratum',
         'peer_hmode', 'peer_pmode', 'peer_hpoll', 'peer_ppoll', 'peer_precision']

CHARTS = {
    'peer_offset': {
        'options': [None, "Combined offset of server relative to this host", "ms", 'peers', 'ntp.peer_offset', 'area'],
        'lines': [
            ['offset']
        ]},
    'peer_delay': {
        'options': [None, "Total roundtrip delay", "ms", 'peers', 'ntp.peer_delay', 'area'],
        'lines': [
            ['delay']
        ]},
    'peer_dispersion': {
        'options': [None, "Dispersion", "ms", 'peers', 'ntp.peer_dispersion', 'area'],
        'lines': [
            ['dispersion']
        ]},
    'peer_jitter': {
        'options': [None, "Combined system jitter and clock jitter", "ms", 'peers', 'ntp.peer_jitter', 'line'],
        'lines': [
            ['jitter']
        ]},
    'peer_rootdelay': {
        'options': [None, "Total roundtrip delay to the primary reference clock", "ms", 'peers', 'ntp.peer_rootdelay', 'area'],
        'lines': [
            ['rootdelay']
        ]},
    'peer_rootdisp': {
        'options': [None, "Dispersion to the primary reference clock", "ms", 'peers', 'ntp.peer_rootdisp', 'area'],
        'lines': [
            ['rootdisp']
        ]},
    'peer_stratum': {
        'options': [None, "Stratum (1-15)", "1", 'peers', 'ntp.peer_stratum', 'line'],
        'lines': [
            ['stratum']
        ]},
    'peer_hmode': {
        'options': [None, "hmode", "log2 s", 'peers', 'ntp.peer_hmode', 'line'],
        'lines': [
            ['hmode']
        ]},
    'peer_pmode': {
        'options': [None, "pmode", 'peers', 'ntp.peer_pmode', 'line'],
        'lines': [
            ['pmode']
        ]},
    'peer_hpoll': {
        'options': [None, "hpoll", "log2 s", 'peers', 'ntp.peer_hpoll', 'line'],
        'lines': [
            ['hpoll']
        ]},
    'peer_ppoll': {
        'options': [None, "ppoll", "log2 s", 'peers', 'ntp.peer_ppoll', 'line'],
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
        self.peer_types = dict()
        self.requests = dict()
        self.index = 0
        self.order = list()
        self.definitions = dict()
        self.regex_srcadr = re.compile(r'srcadr=(?P<srcadr>[A-Za-z0-9.-]+)')
        self.regex_refid = re.compile(r'refid=(?P<refid>[A-Za-z]+)')
        self.regex = re.compile(
            r'stratum=(?P<stratum>[0-9.-]+).*?'
            r'precision=(?P<precision>[0-9.-]+).*?'
            r'rootdelay=(?P<rootdelay>[0-9.-]+).*?'
            r'rootdisp=(?P<rootdisp>[0-9.-]+).*?'
            r'hmode=(?P<hmode>[0-9.-]+).*?'
            r'pmode=(?P<pmode>[0-9.-]+).*?'
            r'hpoll=(?P<hpoll>[0-9.-]+).*?'
            r'ppoll=(?P<ppoll>[0-9.-]+).*?'
            r'offset=(?P<offset>[0-9.-]+).*?'
            r'delay=(?P<delay>[0-9.-]+).*?'
            r'dispersion=(?P<dispersion>[0-9.-]+).*?'
            r'jitter=(?P<jitter>[0-9.-]+).*?',
            re.DOTALL
        )

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
        readstat = self.get_header(0, 'readstat')
        assocs = self.get_assoc_ids(self._get_raw_data(readstat))
        assocs.sort()
        for assoc in assocs:
            req = self.get_header(assoc, 'readvar')
            res = self._get_raw_data(req)
            if not res:
                continue
            match_data = self.regex.search(res)
            if not match_data:
                continue
            match_srcadr = self.regex_srcadr.search(res)
            if match_srcadr:
                srcadr = match_srcadr.groupdict()
                name = srcadr['srcadr'].replace('.', '-')
                if name == '0-0-0-0':
                    continue
                if name.startswith('127-'):
                    peer_type = 'local'
                else:
                    peer_type = 'remote'
            else:
                name = str(assoc)
                peer_type = 'unknown'
            match_refid = self.regex_refid.search(res)
            if match_refid:
                refid = match_refid.groupdict()['refid'].lower()
                name = '_'.join([name, refid])
            self.assocs.append(assoc)
            self.peers[assoc] = name
            self.requests[assoc] = req
            self.peer_types[assoc] = peer_type

        chart_types = list(set(self.peer_types.values()))
        for chart_type in chart_types:
            for chart in ORDER:
                self.order.append('_'.join([chart_type, chart]))
            charts = dict()
            for chart_key in CHARTS.keys():
                chart_name = '_'.join([chart_type, chart_key])
                charts[chart_name] = dict(CHARTS[chart_key])
                family = ' '.join([chart_type, charts[chart_name]['options'][3]])
                charts[chart_name]['options'][3] = family
                dimension_template = CHARTS[chart_key]['lines'][0][0]
                charts[chart_name]['lines'] = list()
                for assoc in self.assocs:
                    if chart_type != self.peer_types[assoc]:
                        continue
                    dimension = '_'.join([self.peers[assoc], dimension_template])
                    line = [dimension, None, 'absolute', 1, PRECISION]
                    charts[chart_name]['lines'].append(line)
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
        #for assoc in self.assocs:
        #    raw_data = self._get_raw_data(self.requests[assoc])
        #    try:
        #        match = self.regex.search(raw_data)
        #        peer_vars = match.groupdict()
        #        for key, value in peer_vars.items():
        #            dimension = '_'.join([self.peers[assoc], key])
        #            data[dimension] = int(float(value) * PRECISION)

        #    except (ValueError, AttributeError, TypeError):
        #        self.error("Invalid data received")
        #        return None

        if self.index >= len(self.assocs):
            self.index = 0
        assoc = self.assocs[self.index]
        self.index += 1
        raw_data = self._get_raw_data(self.requests[assoc])
        try:
            match = self.regex.search(raw_data)
            peer_vars = match.groupdict()
            for key, value in peer_vars.items():
                dimension = '_'.join([self.peers[assoc], key])
                data[dimension] = int(float(value) * PRECISION)

        except (ValueError, AttributeError, TypeError):
            self.error("Invalid data received")
            return None

        if not data:
            self.error("No data received")
            return None
        return data
