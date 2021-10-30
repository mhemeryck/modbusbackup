# modbusbackup

Small script that serves as a backup connection between two unipi units, using modbus over RS-485.

## Installation

Installation is simple with the included `setup.py` script.
With a virtualenv:

```python
virtualenv venv
source venv/bin/activate
python setup.py install
```

### Autorun with systemd

Example systemd unit file.

Place this e.g. under `/etc/systemd/system/modbusbackupserver.service`

```
[Unit]
Description=modbusbackup
After=network-online.target

[Service]
Type=simple
ExecStart=/opt/modbusbackup/bin/modbusbackup.py --config-file /opt/modbusbackup/config.yaml server
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable the service with (possibly as `sudo`)

```
systemctl daemon-reload
systemctl start modbusbackupserver
systemctl enable modbusbackupserver
```

A similar config can be done for the client.

## Running

The main script can run in both server mode and client mode:

```
usage: modbusbackup.py [-h] [--port PORT] [--baudrate BAUDRATE]
                       [--config-file CONFIG_FILE]
                       {server,client} ...

positional arguments:
  {server,client}
    server              Server mode
    client              Client mode

optional arguments:
  -h, --help            show this help message and exit
  --port PORT
  --baudrate BAUDRATE
  --config-file CONFIG_FILE
```

Note:

- Server mode is for the unipi module that will accept incoming modbus requests (modbus slaves).
- Client mode is for the unipi module that will send out modbus message (modbus masters).

A sample config file is included (mine, actually).
It needs a list of configurations, each involving:

- index: a unique number
- input: the digital input
- output: relay output to toggle
- name: optional, just for readability
