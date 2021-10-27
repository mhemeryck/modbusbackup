import setuptools

setuptools.setup(
    name="modbusbackup",
    version="0.1",
    description="modbus-based backup connection between unipi I/O",
    url="https://github.com/mhemeryck/modbusbackup",
    install_requires=(
        "pymodbus>=2.5.3",
        "websockets>=10.0",
        "requests>=2.26.0",
        "PyYAML>=5.4.1",
    ),
    author="Martijn Hemeryck",
    license="MIT",
    zip_safe=True,
    scripts=["modbusbackup.py"],
)
