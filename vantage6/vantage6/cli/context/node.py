"""
Compatibility shim for the legacy CLI NodeContext import path.

We keep this re-export in place while the shared node context lives in
``vantage6-common`` so we do not need to rewrite every CLI-side import in the
same change. Once the remaining ``vantage6.cli.context.node`` imports have been
updated to import from ``vantage6.common.node_context`` directly, we can remove
this module.
"""

from vantage6.common.node_context import NodeContext
