from schema import And, Use

# Keep these imports as compatibility re-exports for existing CLI callers while
# the implementations live in vantage6.common.
from vantage6.common.node_context import NodeConfiguration, NodeConfigurationManager
from vantage6.common.server_context import (
    ServerConfiguration,
    ServerConfigurationManager,
    TestConfiguration,
    TestingConfigurationManager,
)

LOGGING_VALIDATORS = {
    "level": And(
        Use(str), lambda lvl: lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    ),
    "use_console": Use(bool),
    "backup_count": And(Use(int), lambda n: n > 0),
    "max_size": And(Use(int), lambda b: b > 16),
    "format": Use(str),
    "datefmt": Use(str),
}
