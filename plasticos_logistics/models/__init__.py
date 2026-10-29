from . import dispatch
from . import freight_estimate
from . import freight_governance
from . import freight_quote
from . import load
from . import transaction_inherit
from . import sale_order_inherit
from . import rate_memory
from . import linda_request
from . import linda_response
from . import purchase_order_inherit
from . import mail_mail_inherit

# load_dashboard MUST import last: its SQL VIEW reads plasticos_load.transaction_id.
# Importing it before load.py builds the VIEW before that column exists on a fresh
# install and crashes registry load.
from . import load_dashboard
