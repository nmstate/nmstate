from .clib_wrapper import NmstateError
from .gen_conf import generate_configurations
from .netapplier import apply
from .netapplier import commit
from .netapplier import rollback
from .netinfo import show
from .netinfo import show_running_config
from .prettystate import PrettyState
from collections.abc import Mapping
from collections.abc import Sequence

__all__ = [
    "NmstateError",
    "PrettyState",
    "apply",
    "commit",
    "generate_configurations",
    "rollback",
    "show",
    "show_running_config",
    "state_match",
]

__version__ = "2.1.4"

BASE_ON_RUST = True


def state_match(desire, current):
    if isinstance(desire, Mapping):
        return isinstance(current, Mapping) and all(
            state_match(val, current.get(key)) for key, val in desire.items()
        )
    elif isinstance(desire, Sequence) and not isinstance(desire, str):
        return (
            isinstance(current, Sequence)
            and not isinstance(current, str)
            and len(current) == len(desire)
            and all(state_match(d, c) for d, c in zip(desire, current))
        )
    else:
        return desire == current
