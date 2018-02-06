# netdata-ntp

Netdata python module for NTP (Network Time Protocol)

## Requirements

- `ntp`: [Network Time Protocol daemon](http://www.ntp.org/)

## Installation

Replace `<netdata>` with the **netdata** installation path, for example `/opt/netdata`:

- Copy `python.d/ntp.chart.py` to `<netdata>/usr/libexec/netdata/python.d/`
- Copy `conf.d/python.d/ntp.conf` to `<netdata>/etc/netdata/python.d/`

```
NETDATA_ROOT=<netdata>
git clone https://github.com/rda0/netdata-ntp.git
cd netdata-ntp
cp python.d/ntp.chart.py ${NETDATA_ROOT}/usr/libexec/netdata/python.d/
cp conf.d/python.d/ntp.conf ${NETDATA_ROOT}/etc/netdata/python.d/
chown root:root ${NETDATA_ROOT}/usr/libexec/netdata/python.d/ntp.chart.py
chmod 644 ${NETDATA_ROOT}/usr/libexec/netdata/python.d/ntp.chart.py
chown root:netdata ${NETDATA_ROOT}/etc/netdata/python.d/ntp.conf
chmod 640 ${NETDATA_ROOT}/etc/netdata/python.d/ntp.conf
```
