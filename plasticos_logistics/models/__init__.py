from . import dispatch
from . import load
from . import transaction_inherit
from . import sale_order_inherit
from . import rate_memory

# load_dashboard MUST import last: its SQL VIEW reads plasticos_transaction.load_id,
# a column injected by transaction_inherit. Importing it earlier builds the VIEW before
# the column exists on a fresh-DB install and crashes registry load.
from . import load_dashboard
