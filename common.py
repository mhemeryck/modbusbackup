# Dynamically generated list, i.e. [1_1, ... 1_4, 2_1, ..., 2_30, 3_1, ... 3_30]
CIRCUIT_LIST = [f"{i+1}_{j+1}" for i, j in enumerate((4, 30, 30)) for j in range(j)]
# Convert to map for easy access
CIRCUIT_MAP = {e: k for k, e in enumerate(CIRCUIT_LIST)}
