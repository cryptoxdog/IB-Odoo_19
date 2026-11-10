/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { attachmentEntries, formatAnalysis, formatPayload, formatTriage } from "./format";

export class LeadEvidence extends Component {
    static template = "plasticos_web_leads.LeadEvidence";
    static props = {
        ...standardFieldProps,
        mode: { type: String },
    };

    setup() {
        this.state = useState({ technical: false });
    }

    get presentation() {
        const data = this.props.record.data;
        const value = data[this.props.name];
        if (this.props.mode === "analysis") {
            return formatAnalysis(value, data.decision_reasons);
        }
        if (this.props.mode === "triage") {
            return formatTriage(value, data.ai_vision_results, data.image_urls, attachmentEntries(data.lead_image_ids));
        }
        return formatPayload(value);
    }

    get technicalLabel() {
        return this.state.technical ? "Hide technical data" : "Show technical data";
    }

    toggleTechnical() {
        this.state.technical = !this.state.technical;
    }
}

registry.category("fields").add("lead_evidence", {
    component: LeadEvidence,
    supportedTypes: ["json"],
    extractProps: ({ options }) => ({
        mode: options.mode || "",
    }),
});
