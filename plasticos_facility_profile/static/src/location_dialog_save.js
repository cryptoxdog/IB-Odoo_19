/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

function hasParent(parent) {
    if (!parent) {
        return false;
    }
    if (Array.isArray(parent)) {
        return Boolean(parent[0]);
    }
    return Boolean(parent.id ?? parent);
}

patch(FormController.prototype, {
    saveButtonClicked(params = {}) {
        const record = this.model.root;
        const locationDialog =
            this.env.inDialog &&
            record.resModel === "res.partner" &&
            record.data.is_company &&
            hasParent(record.data.parent_id);
        if (locationDialog) {
            return super.saveButtonClicked({});
        }
        return super.saveButtonClicked(params);
    },
});
