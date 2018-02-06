# -*- coding: utf-8 -*-
# Description: ntp netdata python.d module
# Author: Sven Mäder (rda0)

from base import SimpleService
import socket
import re

# default module values
update_every = 1
priority = 90000
retries = 60

ORDER = ['offset', 'jitter', 'frequency', 'wander', 'root', 'stratum', 'tc', 'precision']

CHARTS = {
    'offset': {
        'options': [None, "Combined offset of server relative to this host", "ms", 'system', 'ntp.offset', 'area'],
        'lines': [
            ['offset', None, 'absolute', 1, 1000000]
        ]},
    'jitter': {
        'options': [None, "Combined system jitter and clock jitter", "ms", 'system', 'ntp.jitter', 'line'],
        'lines': [
            ['sys_jitter', 'system', 'absolute', 1, 1000000],
            ['clk_jitter', 'clock', 'absolute', 1, 1000]
        ]},
    'frequency': {
        'options': [None, "Frequency offset relative to hardware clock", "ppm", 'frequencies', 'ntp.frequency', 'area'],
        'lines': [
            ['frequency', None, 'absolute', 1, 1000]
        ]},
    'wander': {
        'options': [None, "Clock frequency wander", "ppm", 'frequencies', 'ntp.wander', 'area'],
        'lines': [
            ['clk_wander', None, 'absolute', 1, 1000]
        ]},
    'root': {
        'options': [None, "Total roundtrip delay and dispersion to the primary reference clock", "ms", 'root', 'ntp.root', 'line'],
        'lines': [
            ['rootdelay', 'delay', 'absolute', 1, 1000],
            ['rootdisp', 'dispersion', 'absolute', 1, 1000]
        ]},
    'stratum': {
        'options': [None, "Stratum (1-15)", "1", 'root', 'ntp.stratum', 'line'],
        'lines': [
            ['stratum', None, 'absolute', 1, 1]
        ]},
    'tc': {
        'options': [None, "Time constant and poll exponent (3-17)", "log2 s", 'constants', 'ntp.tc', 'line'],
        'lines': [
            ['tc', 'current', 'absolute', 1, 1],
            ['mintc', 'minimum', 'absolute', 1, 1]
        ]},
    'precision': {
        'options': [None, "Precision", "log2 s", 'constants', 'ntp.precision', 'line'],
        'lines': [
            ['precision', 'precision', 'absolute', 1, 1]
        ]}
}


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.payload = '\x16\x02\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00'
        addrinfo = socket.getaddrinfo('127.0.0.1', '123')[0]
        self.family = addrinfo[0]
        self.sockaddr = addrinfo[4]
        self.sock = socket.socket(self.family, socket.SOCK_DGRAM)
        self.rgx_sys = re.compile(
                r'stratum=(?P<stratum>[0-9.-]+).*?'
                r'precision=(?P<precision>[0-9.-]+).*?'
                r'rootdelay=(?P<rootdelay>[0-9.-]+).*?'
                r'rootdisp=(?P<rootdisp>[0-9.-]+).*?'
                r'tc=(?P<tc>[0-9.-]+).*?'
                r'mintc=(?P<mintc>[0-9.-]+).*?'
                r'offset=(?P<offset>[0-9.-]+).*?'
                r'frequency=(?P<frequency>[0-9.-]+).*?'
                r'sys_jitter=(?P<sys_jitter>[0-9.-]+).*?'
                r'clk_jitter=(?P<clk_jitter>[0-9.-]+).*?'
                r'clk_wander=(?P<clk_wander>[0-9.-]+)',
                re.DOTALL)

    def check(self):
        self.create_charts()

        self.info('Plugin was started successfully')
        return True

    def _get_raw_data(self):
        try:
            self.sock.settimeout(0.5)
            self.sock.sendto(self.payload, self.sockaddr)
            src_addr = None,
            while src_addr[0] != self.sockaddr[0]:
                raw_data, src_addr = self.sock.recvfrom(512)
        except socket.timeout:
            self.error('Socket timeout')
            self.sock.close()
            self.sock = socket.socket(self.family, socket.SOCK_DGRAM)
            return None

        if not raw_data:
            self.error(''.join(['No data received from socket']))
            return None

        return raw_data

    def get_variables(self):
        raw_data = self._get_raw_data()

        if not raw_data:
            return None

        match = self.rgx_sys.search(raw_data)

        if match is not None:
            sys_vars = match.groupdict()
        else:
            return None

        return sys_vars

    def _get_data(self):
        data = {}

        sys_vars = self.get_variables()
        if (sys_vars is not None):
            data['offset'] = float(sys_vars['offset']) * 1000000
            data['clk_jitter'] = float(sys_vars['clk_jitter']) * 1000
            data['sys_jitter'] = float(sys_vars['sys_jitter']) * 1000000
            data['frequency'] = float(sys_vars['frequency']) * 1000
            data['clk_wander'] = float(sys_vars['clk_wander']) * 1000
            data['rootdelay'] = float(sys_vars['rootdelay']) * 1000
            data['rootdisp'] = float(sys_vars['rootdisp']) * 1000
            data['stratum'] = float(sys_vars['stratum'])
            data['tc'] = float(sys_vars['tc'])
            data['mintc'] = float(sys_vars['mintc'])
            data['precision'] = float(sys_vars['precision'])

        return data

    def create_charts(self):
        self.order = ORDER[:]

        # Create static charts
        self.definitions = CHARTS
