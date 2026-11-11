/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { storedRelationIds } from "../lead_evidence/format";

export class LeadImageStrip extends Component {
    static template = "plasticos_web_leads.LeadImageStrip";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({ open: false, index: 0 });
    }

    get images() {
        const value = this.props.record.data[this.props.name];
        return storedRelationIds(value).map((id) => ({ id, url: `/web/image/${id}` }));
    }

    get current() {
        return this.images[this.state.index] || null;
    }

    openAt(index) {
        this.state.index = index;
        this.state.open = true;
    }

    close() {
        this.state.open = false;
    }

    previous(ev) {
        ev.stopPropagation();
        const count = this.images.length;
        if (!count) {
            return;
        }
        this.state.index = (this.state.index - 1 + count) % count;
    }

    next(ev) {
        ev.stopPropagation();
        const count = this.images.length;
        if (!count) {
            return;
        }
        this.state.index = (this.state.index + 1) % count;
    }
}

registry.category("fields").add("lead_image_strip", {
    component: LeadImageStrip,
    supportedTypes: ["many2many"],
    relatedFields: [
        { name: "name", type: "char" },
        { name: "mimetype", type: "char" },
    ],
});
