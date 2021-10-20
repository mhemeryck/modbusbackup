import argparse
import asyncio
import json
import logging
import typing

import pymodbus.client.sync
import pymodbus.datastore
import pymodbus.server.sync
import pymodbus.transaction
import requests
import requests.exceptions
import websockets
import yaml

FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Global code

_UNIT = 0x01
_CONFIG_FILE: str = "config.yaml"

# Client code

ModbusClientSettings = typing.NamedTuple(
    "ModbusClientSettings",
    [("port", str), ("baudrate", int)],
)

_MODBUS_CLIENT = None
_MODBUS_CLIENT_SETTINGS: ModbusClientSettings = ModbusClientSettings(
    port="/dev/ttyNS0",
    baudrate=19200,
)
_CIRCUIT_MAP: typing.Dict[str, str] = {}


def _circuit_map() -> typing.Dict[str, str]:
    """Read config file and create a map between the circuit name and the index"""
    global _CIRCUIT_MAP
    if not _CIRCUIT_MAP:
        with open(_CONFIG_FILE, "r") as fh:
            m = yaml.safe_load(fh)
            _CIRCUIT_MAP = {entry["input"]: entry["index"] for entry in m}
    return _CIRCUIT_MAP


def _modbus_client() -> pymodbus.client.sync.ModbusSerialClient:
    """Singleton modbus client"""
    global _MODBUS_CLIENT, _MODBUS_CLIENT_SETTINGS
    if _MODBUS_CLIENT is None:
        _MODBUS_CLIENT = pymodbus.client.sync.ModbusSerialClient(
            port=_MODBUS_CLIENT_SETTINGS.port,
            baudrate=_MODBUS_CLIENT_SETTINGS.baudrate,
            method="rtu",
        )
    return _MODBUS_CLIENT


async def _ws_process(payload) -> None:
    """Process incoming websocket payload, push to modbus RTU"""
    obj = json.loads(payload)[0]
    # Ignore analog I?O
    if obj["dev"] in ("ai", "ao"):
        return
    logger.info(f"Incoming message for websocket {obj}")
    # Don't send any events related to trailing edges
    if obj["value"] == 0:
        return

    try:
        address = _circuit_map()[obj["circuit"]]
    except KeyError:
        logger.debug(f"Could not find mapping address for {obj['circuit']}")
        return

    # Blocking sync call
    logger.info(
        f"Writing {obj['value']} to address {address} for circuit {obj['circuit']}"
    )
    _modbus_client().write_coil(address, obj["value"], unit=_UNIT)


async def _run_client(websocket_uri="ws://localhost/ws") -> None:
    """Main loop polling incoming events from websockets"""
    logger.info(f"Connecting to {websocket_uri}")
    async with websockets.connect(websocket_uri) as websocket:  # type: ignore
        while True:
            payload = await websocket.recv()
            await _ws_process(payload)


def run_client(args: argparse.Namespace) -> None:
    # Update settings in global namespace
    global _CONFIG_FILE, _MODBUS_CLIENT_SETTINGS
    _CONFIG_FILE = args.config_file
    _MODBUS_CLIENT_SETTINGS = ModbusClientSettings(
        port=args.port,
        baudrate=args.baudrate,
    )
    # Start
    asyncio.run(_run_client(websocket_uri=args.websocket_uri))


# Server code

_SESSION = None
_RELAY_MAP: typing.Dict[int, str] = {}


def _relay_map() -> typing.Dict[int, str]:
    """Read config file and create a map between the index and the output"""
    global _RELAY_MAP
    if not _RELAY_MAP:
        with open(_CONFIG_FILE) as fh:
            m = yaml.safe_load(fh)
            _RELAY_MAP = {entry["index"]: entry["output"] for entry in m}
    return _RELAY_MAP


def _session() -> requests.Session:
    """Global session singleton, to pool connections"""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
    return _SESSION


def _trigger(address: int, value: bool, host="http://localhost") -> None:
    """Process incoming event"""
    # Only check for rising edges since we're dealing with lights
    if not value:
        return

    # Convert address to zero-based address
    try:
        relay = _relay_map()[address - 1]
    except KeyError:
        logger.debug(f"Could not find relay for address {address}")
        return

    try:
        response = _session().get(f"{host}/json/relay/{relay}")
        response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        logger.debug(f"Issue with API call: {error}")
        return
    try:
        current = response.json()["data"]["value"]
    except (KeyError, ValueError):
        logger.debug("Error reading current state")
        return

    # Flip the bit from current by XOR
    toggled = current ^ 0x1
    try:
        _session().post(f"{host}/json/relay/{relay}", json={"value": str(toggled)})
        response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        logger.debug(f"Issue with API call: {error}")
        return


class CallbackDataBlock(pymodbus.datastore.ModbusSparseDataBlock):
    """callbacks on operation"""

    def __init__(self) -> None:
        super().__init__({k: k for k in range(64)})

    def setValues(self, address: int, values: typing.List) -> None:
        logger.info(f"Got {values} for {address}")
        _trigger(address, values[0])
        super().setValues(address, values)


def _run_server(port: str, timeout: float, baudrate: int) -> None:
    block = CallbackDataBlock()
    store = pymodbus.datastore.ModbusSlaveContext(
        di=block, co=block, hr=block, ir=block
    )

    context = pymodbus.datastore.ModbusServerContext(slaves=store, single=True)
    pymodbus.server.sync.StartSerialServer(
        context,
        framer=pymodbus.transaction.ModbusRtuFramer,
        port=port,
        timeout=timeout,
        baudrate=baudrate,
    )


def run_server(args: argparse.Namespace) -> None:
    # Set config file
    global _CONFIG_FILE
    _CONFIG_FILE = args.config_file
    return _run_server(
        port=args.port,
        timeout=args.timeout,
        baudrate=args.baudrate,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyNS0")
    parser.add_argument("--baudrate", type=int, default=19200)
    parser.add_argument("--config-file", default="config.yaml")
    subparsers = parser.add_subparsers(required=True)

    # server part
    server_parser = subparsers.add_parser("server", help="Server mode")
    server_parser.add_argument("--timeout", type=float, default=0.005)
    server_parser.set_defaults(func=run_server)

    # client part
    client_parser = subparsers.add_parser("client", help="Client mode")
    client_parser.add_argument("--websocket-uri", default="ws://localhost/ws")
    client_parser.set_defaults(func=run_client)

    # Parse args and pass to function
    args = parser.parse_args()
    args.func(args)
