import json
import logging

import pymodbus.client.asynchronous
import pymodbus.client.asynchronous.serial
import websockets

FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

_UNIT = 0x01

# Dynamically generated list, i.e. [1_1, ... 1_4, 2_1, ..., 2_30, 3_1, ... 3_30]
CIRCUIT_LIST = [f"{i+1}_{j+1}" for i, j in enumerate((4, 30, 30)) for j in range(j)]
# Convert to map for easy access
CIRCUIT_MAP = {e: k for k, e in enumerate(CIRCUIT_LIST)}


async def _ws_process(modbus_client, payload) -> None:
    """Process incoming websocket payload, push to modbus RTU"""
    obj = json.loads(payload)[0]
    # Ignore analog I?O
    if obj["dev"] in ("ai", "ao"):
        return
    logger.info(
        "Incoming message for websocket %s",
        obj,
    )
    # Don't send any events related to trailing edges
    if obj["value"] == 0:
        return

    try:
        address = CIRCUIT_MAP[obj["circuit"]]
    except KeyError:
        logger.debug(f"Could not find mapping address for {obj['circuit']}")
        return

    logger.info(
        f"Writing {obj['value']} to address {address} for circuit {obj['circuit']}",
    )
    await modbus_client.write_coil(address, obj["value"], unit=_UNIT)


async def _ws_loop(modbus_client, websocket_uri="ws://localhost/ws") -> None:
    """Main loop polling incoming events from websockets"""
    logger.info(
        "Connecting to %s",
        websocket_uri,
    )
    async with websockets.connect(websocket_uri) as websocket:
        while True:
            payload = await websocket.recv()
            await _ws_process(modbus_client, payload)


if __name__ == "__main__":
    loop, client = pymodbus.client.asynchronous.serial.AsyncModbusSerialClient(
        pymodbus.client.asynchronous.schedulers.ASYNC_IO,
        port="/dev/ttyNS0",
        baudrate=19200,
        method="rtu",
    )
    # Hack around the fact that the constructor does not take in the timeout arg
    client._timeout = 10
    loop.run_until_complete(_ws_loop(client.protocol))
    loop.close()
