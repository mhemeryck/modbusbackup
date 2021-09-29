import argparse
import logging

import pymodbus.datastore
import pymodbus.server.sync
import pymodbus.transaction

FORMAT = (
    "%(asctime)-15s %(threadName)-15s"
    " %(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s"
)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class CallbackDataBlock(pymodbus.datastore.ModbusSparseDataBlock):
    """callbacks on operation"""

    def __init__(self):
        super().__init__({k: k for k in range(64)})

    def setValues(self, address, value):
        logger.info(f"Got {value} for {address}")
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
