import asyncio
import json
import logging
import typing

import pymodbus.client.asynchronous
import pymodbus.client.asynchronous.serial
import pymodbus.client.sync
import websockets
import yaml

FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

_UNIT = 0x01

_MODBUS_CLIENT = None
_CIRCUIT_MAP: typing.Dict[str, str] = {}
_CONFIG_FILE: str = "config.yaml"


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
    global _MODBUS_CLIENT
    if _MODBUS_CLIENT is None:
        _MODBUS_CLIENT = pymodbus.client.sync.ModbusSerialClient(
            port="/dev/ttyNS0",
            baudrate=19200,
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


async def _ws_loop(websocket_uri="ws://localhost/ws") -> None:
    """Main loop polling incoming events from websockets"""
    logger.info(f"Connecting to {websocket_uri}")
    async with websockets.connect(websocket_uri) as websocket:
        while True:
            payload = await websocket.recv()
            await _ws_process(payload)


if __name__ == "__main__":
    asyncio.run(_ws_loop())
