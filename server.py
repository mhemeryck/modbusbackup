import argparse
import logging
import typing

import pymodbus.datastore
import pymodbus.server.sync
import pymodbus.transaction
import requests
import requests.exceptions

FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

_SESSION = None


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

    # TODO: proper address translation
    relay = "2_16"
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

    def setValues(self, address: int, values: typing.Iterable) -> None:
        logger.info(f"Got {values} for {address}")
        _trigger(address, values[0])
        super().setValues(address, values)


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
