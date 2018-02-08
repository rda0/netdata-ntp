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

PRECISION = 1000000

ORDER = ['sys_offset', 'sys_jitter', 'sys_frequency', 'sys_wander', 'sys_rootdelay', 'sys_rootdisp', 'sys_stratum', 'sys_tc', 'sys_precision']

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
        'options': [None, "Dispersion to the primary reference clock", "ms", 'system', 'ntp.sys_rootdisp', 'area'],
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


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.payload = '\x16\x02\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00'
        self.host = 'localhost'
        self.port = 'ntp'
        addrinfo = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_DGRAM, socket.IPPROTO_UDP)[0]
        self.family = addrinfo[0]
        self.sockaddr = addrinfo[4]
        self.order = ORDER
        self.definitions = CHARTS
        self.regex = re.compile(
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
            re.DOTALL
        )

    def _get_raw_data(self):
        try:
            sock = socket.socket(self.family, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(self.payload, self.sockaddr)
            src_addr = None,
            while src_addr[0] != self.sockaddr[0]:
                raw_data, src_addr = sock.recvfrom(512)
        except socket.timeout:
            self.error('Socket timeout')
            return None
        finally:
            sock.close()

        if not raw_data:
            self.error(''.join(['No data received from socket']))
            return None

        return raw_data

    def _get_data(self):
        raw_data = self._get_raw_data()
        data = dict()
        try:
            match = self.regex.search(raw_data)
            sys_vars = match.groupdict()
            for key, value in sys_vars.items():
                data[key] = int(float(value) * PRECISION)

        except (ValueError, AttributeError, TypeError):
            self.error("Invalid data received")
            return None

        if not data:
            self.error("No data received")
            return None
        return data
