import argparse
import logging
import typing

import pymodbus.datastore
import pymodbus.server.sync
import pymodbus.transaction
import requests
import requests.exceptions
import yaml

_CONFIG_FILE = "config.yaml"
FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

_SESSION = None
_INPUT_MAP = None

# Dynamically generated list, i.e. [1_1, ... 1_4, 2_1, ..., 2_30, 3_1, ... 3_30]
CIRCUIT_LIST = [f"{i+1}_{j+1}" for i, j in enumerate((4, 30, 30)) for j in range(j)]
# Convert to map for easy access
CIRCUIT_MAP = {k: e for k, e in enumerate(CIRCUIT_LIST)}


def _session() -> requests.Session:
    """Global session singleton, to pool connections"""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
    return _SESSION


def _relay_for_address(address: int) -> typing.Union[str, None]:
    global _INPUT_MAP
    if _INPUT_MAP is None:
        with open(_CONFIG_FILE) as fh:
            m = yaml.safe_load(fh)
            _INPUT_MAP = {entry["input"]: entry["output"] for entry in m}

    # Decrement address by one to make it zero-based
    input_address = CIRCUIT_MAP.get(address - 1)
    if not input_address:
        logger.debug(f"Could not find input for address {address}")
        return

    return _INPUT_MAP.get(input_address)


def _trigger(address: int, value: bool, host="http://localhost") -> None:
    """Process incoming event"""
    # Only check for rising edges since we're dealing with lights
    if not value:
        return

    relay = _relay_for_address(address)
    if not relay:
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
