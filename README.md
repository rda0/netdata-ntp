# netdata-ntp

Netdata python module for NTP (Network Time Protocol)

## Requirements

- Package `ntp` (Network Time Protocol daemon and utility programs)
- Library `python3-ntplib` or `python-ntplib`

## Installation

Replace `<netdata>` with the **netdata** installation path, for example `/opt/netdata`:

- Install the required libraries (see above)
- Copy `python.d/ntp.chart.py` to `<netdata>/usr/libexec/netdata/python.d/`
- Copy `python.d/python_modules/ntpq.py` to `<netdata>/usr/libexec/netdata/python.d/python_modules/`
- Copy `conf.d/python.d/ntp.conf` to `<netdata>/etc/netdata/python.d/`
- Copy `web/dashboard_info_custom.ntp.js` to `<netdata>/usr/share/netdata/web/`

The custom dashboard can be enabled by adding the following line in `netdata.conf`:

```
[web]
custom dashboard_info.js = dashboard_info_custom.ntp.js
```
