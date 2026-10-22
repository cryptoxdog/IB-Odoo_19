The two registry lines come from `tracking=True` on `plasticos.freight.estimate.status` and `plasticos.freight.quote.selected`. Those models do not inherit `mail.thread`, so Odoo treats `tracking` as an unknown field parameter and logs one warning per field while the registry loads.

Odoo checks every non-core field argument in `Field.setup`. The base model only accepts `related_sudo`. `mail.thread` is what adds `tracking`:

```502:504:/Users/ib-mac/dev/odoo-19/addons/mail/models/mail_thread.py
    def _valid_field_parameter(self, field, name):
        # allow tracking on models inheriting from 'mail.thread'
        return name == 'tracking' or super()._valid_field_parameter(field, name)
```

When that check fails, the field name is printed as `model.field`:

```530:538:/Users/ib-mac/dev/odoo-19/odoo/orm/fields.py
            for key in self._extra_keys__:
                if not model._valid_field_parameter(self, key):
                    _logger.warning(
                        "Field %s: unknown parameter %r, if this is an actual"
                        " parameter you may want to override the method"
                        " _valid_field_parameter on the relevant model in order to"
                        " allow it",
                        self, key
                    )
```

The two declarations are:

```59:69:plasticos_logistics/models/freight_estimate.py
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("succeeded", "Succeeded"),
            ("insufficient_evidence", "Insufficient Evidence"),
            ("failed", "Failed"),
        ],
        required=True,
        default="pending",
        tracking=True,
    )
```

`PlasticosFreightEstimate` has only `_name`. Nothing else inherits `plasticos.freight.estimate`. `write()` also lists `status` in the immutable set, so a later change is rejected before any chatter could be written.

```541:541:plasticos_logistics/models/freight_quote.py
    selected = fields.Boolean(default=False, tracking=True)
```

`PlasticosFreightQuote` likewise has only `_name`, and nothing inherits `plasticos.freight.quote`. Selection goes through `action_select`, which writes `selected` and records a `freight_quote_selected` event on the load.

The other `tracking=True` in that file is legal. It is `state` on `plasticos.freight.quote.request`, and that class inherits `mail.thread`. `plasticos.load` does too. Every other `tracking=True` in the addons is on a model that inherits `mail.thread` directly or through a parent such as `res.partner`, `account.move`, or `plasticos.transaction`. These two fields are the only ones that produce the warning.
