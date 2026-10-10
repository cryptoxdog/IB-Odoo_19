/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    Many2ManyTagsField,
    many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";

export class Many2ManyTagsOpenField extends Many2ManyTagsField {
    setup() {
        super.setup();
        this.action = useService("action");
    }

    getTagProps(record) {
        const props = super.getTagProps(record);
        props.canEdit = true;
        props.onClick = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            this.openTag(record);
        };
        return props;
    }

    async openTag(record) {
        if (!record.resId) {
            return;
        }
        const action = await this.orm.call(this.relation, "get_formview_action", [[record.resId]], {
            context: this.props.context,
        });
        await this.action.doAction(action);
    }
}

export const many2ManyTagsOpenField = {
    ...many2ManyTagsField,
    component: Many2ManyTagsOpenField,
    additionalClasses: ["o_field_many2many_tags"],
};

registry.category("fields").add("many2many_tags_open", many2ManyTagsOpenField);
