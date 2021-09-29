import argparse
import asyncio
import json
import logging

import pymodbus.datastore
import pymodbus.server.sync
import pymodbus.transaction
import websockets

FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


async def _ws_trigger(address: int, value: int, websocket_uri="ws://localhost/ws"):
    logger.info(f"trigger for address {address} value {value}")
    # TODO: address mapping
    # TODO: Check current state in order to toggle
    async with websockets.connect(websocket_uri) as websocket:
        await websocket.send(
            json.dumps({"cmd": "set", "dev": "relay", "circuit": "2_16", "value": 1})
        )


class CallbackDataBlock(pymodbus.datastore.ModbusSparseDataBlock):
    """callbacks on operation"""

    def __init__(self):
        super().__init__({k: k for k in range(64)})

    def setValues(self, address, value):
        logger.info(f"Got {value} for {address}")
        asyncio.run(_ws_trigger(address, value))
        super().setValues(address, value)


def run_server(port="/dev/ttyNS0", timeout=0.005, baudrate=19200):
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyNS0")
    parser.add_argument("--timeout", type=float, default=0.005)
    parser.add_argument("--baudrate", type=int, default=19200)
    args = parser.parse_args()

    run_server(port=args.port, timeout=args.timeout, baudrate=args.baudrate)
