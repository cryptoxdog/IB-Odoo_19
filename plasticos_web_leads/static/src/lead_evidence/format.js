/** @odoo-module **/

export const NOT_STATED = "Not stated.";

const SECRET_KEYS = new Set([
    "file",
    "source_url",
    "url",
    "adminlink",
    "document1",
    "useragent",
    "ipaddress",
    "token",
    "api_key",
]);

const ANALYSIS_PRIMARY = [
    ["polymer", "Polymer"],
    ["estimated_lbs", "Estimated weight"],
    ["is_plastic", "Plastic"],
    ["confidence", "Confidence"],
    ["source_type", "Source"],
    ["notes", "Notes"],
];

const ANALYSIS_EXTRA = {
    form: "Form",
    color: "Color",
    loads_per_month: "Loads per month",
    frequency: "Frequency",
    lbs_source: "Weight source",
    material_summary: "Material summary",
    contaminants_noted: "Contaminants",
    is_commercial_source: "Commercial source",
    source_description: "Source description",
    estimated_lbs_high: "Estimated weight high",
    vision_summary: "Vision summary",
    material_description: "Material description",
};

const TRIAGE_FIELDS = [
    ["polymer", "Polymer"],
    ["material_description", "Material description"],
    ["source_type", "Source"],
    ["source_description", "Source description"],
    ["estimated_lbs_per_load", "Weight"],
    ["loads_per_month", "Loads per month"],
    ["is_plastic", "Plastic"],
    ["is_commercial_source", "Commercial source"],
    ["confidence", "Confidence"],
    ["notes", "Notes"],
    ["weight_source", "Weight source"],
    ["_inferred_fields", "Inferred fields"],
];

const VISION_FIELDS = [
    ["observed_form", "Form"],
    ["observed_color", "Color"],
    ["commercial_color", "Commercial color"],
    ["cleanliness", "Cleanliness"],
    ["quantity_visible", "Quantity visible"],
    ["quantity_notes", "Quantity note"],
    ["contamination_visible", "Contamination"],
    ["contamination_notes", "Contamination notes"],
    ["observed_polymer_hint", "Polymer hint"],
    ["confidence", "Confidence"],
    ["material_form_observed", "Material form"],
    ["containment", "Containment"],
    ["support_unit", "Support unit"],
];

const GATE_LABELS = {
    "is_plastic:false": "Not plastic",
    "is_commercial_source:false": "Not a commercial source",
    "is_commercial_source:true": "Commercial source",
    reject_material: "Rejected material",
    reject_source: "Rejected source",
    "weight:unknown": "Weight unknown",
    "weight:below_cold_floor": "Weight below the cold floor",
    "weight:below_hot_threshold": "Weight below the hot threshold",
    insufficient_qualifiers: "Not enough hot qualifiers",
    "economic_policy:eligible": "Meets the economic policy",
    commercial_keyword_detected: "Commercial keyword detected",
    "source_type:post_industrial": "Post-industrial source",
};

const PHOTO_FIELDS = [
    "UploadPhotosOfYourScrapUpTo10",
    "UploadPhotos",
    "Photos",
    "Attachments",
    "Files",
];

const PAYLOAD_TRANSPORT = new Set([
    "Form",
    "Entry",
    "Id",
    "InternalName",
    "User",
    "Action",
    "Number",
    "Origin",
    "IpAddress",
    "UserAgent",
    "AdminLink",
    "Document1",
    "IsImported",
    "Status",
    "Version",
    "DateCreated",
    "DateUpdated",
    "DateSubmitted",
    "Role",
    "Order",
]);

const WEIGHT_KEYS = new Set(["estimated_lbs", "estimated_lbs_per_load", "estimated_lbs_high"]);
const CONFIDENCE_KEYS = new Set(["confidence"]);
const BOOL_KEYS = new Set([
    "is_plastic",
    "is_commercial_source",
    "quantity_visible",
    "contamination_visible",
]);
const SOURCE_KEYS = new Set(["source_type", "polymer", "form", "observed_form", "cleanliness"]);

export function parseJson(value) {
    if (typeof value === "string") {
        const text = value.trim();
        if (!text) {
            return null;
        }
        try {
            return JSON.parse(text);
        } catch {
            return null;
        }
    }
    return value ?? null;
}

export function isSecretKey(key) {
    return SECRET_KEYS.has(String(key).toLowerCase());
}

export function filenameFromUrl(value) {
    if (typeof value !== "string" || !value.trim()) {
        return "";
    }
    const path = value.split("?")[0].split("#")[0];
    const segment = path.split("/").filter(Boolean).pop() || "";
    try {
        return decodeURIComponent(segment);
    } catch {
        return segment;
    }
}

export function redact(value) {
    if (Array.isArray(value)) {
        return value.map((item) => redact(item));
    }
    if (value && typeof value === "object") {
        const redacted = {};
        for (const [key, child] of Object.entries(value)) {
            redacted[key] = isSecretKey(key) ? "[redacted]" : redact(child);
        }
        return redacted;
    }
    if (typeof value === "string" && /^https?:\/\//i.test(value) && value.includes("?")) {
        return `${value.split("?")[0]}?[redacted]`;
    }
    return value;
}

export function technicalText(value) {
    return JSON.stringify(redact(parseJson(value) ?? value ?? {}), null, 2);
}

function stated(value) {
    if (value === null || value === undefined || value === "") {
        return NOT_STATED;
    }
    if (typeof value === "string" && /^https?:\/\//i.test(value.trim())) {
        return filenameFromUrl(value) || NOT_STATED;
    }
    return String(value);
}

function formatBool(value) {
    if (value === true) {
        return "Yes";
    }
    if (value === false) {
        return "No";
    }
    return NOT_STATED;
}

function formatConfidence(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return NOT_STATED;
    }
    const percent = number <= 1 ? number * 100 : number;
    return `${Math.round(percent)}%`;
}

function formatWeight(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return NOT_STATED;
    }
    return `${number.toLocaleString("en-US")} lb`;
}

function formatSource(value) {
    if (value === null || value === undefined || value === "") {
        return NOT_STATED;
    }
    const text = String(value).replaceAll("_", " ").trim();
    if (!text) {
        return NOT_STATED;
    }
    if (text.length <= 5 && text === text.toUpperCase()) {
        return text;
    }
    return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

function formatInferred(value) {
    if (!Array.isArray(value) || !value.length) {
        return NOT_STATED;
    }
    return value
        .map((item) => String(item).replace(/^_/, "").replaceAll("_", " "))
        .join(", ");
}

function formatField(key, value) {
    if (key === "_inferred_fields") {
        return formatInferred(value);
    }
    if (BOOL_KEYS.has(key)) {
        return formatBool(value);
    }
    if (CONFIDENCE_KEYS.has(key)) {
        return formatConfidence(value);
    }
    if (WEIGHT_KEYS.has(key)) {
        return formatWeight(value);
    }
    if (SOURCE_KEYS.has(key) || key === "weight_source" || key === "lbs_source" || key === "frequency") {
        return formatSource(value);
    }
    if (Array.isArray(value)) {
        return value.length ? value.map((item) => stated(item)).join(", ") : NOT_STATED;
    }
    if (value && typeof value === "object") {
        return stated(JSON.stringify(redact(value)));
    }
    return stated(value);
}

function row(label, value) {
    return { label, value };
}

function section(id, title, rows = [], bullets = []) {
    return { id, title, rows, bullets };
}

function labelKey(key) {
    return String(key)
        .replace(/^_/, "")
        .replaceAll("_", " ")
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .trim();
}

function labelGate(identifier) {
    const text = String(identifier);
    if (GATE_LABELS[text]) {
        return GATE_LABELS[text];
    }
    if (text.startsWith("polymer_confirmed:")) {
        return `Polymer confirmed: ${text.slice("polymer_confirmed:".length).toUpperCase()}`;
    }
    if (text.startsWith("weight:")) {
        return formatSource(text.replaceAll(":", " "));
    }
    return text;
}

function otherRows(source, knownKeys) {
    if (!source || typeof source !== "object" || Array.isArray(source)) {
        return [];
    }
    const rows = [];
    for (const [key, value] of Object.entries(source)) {
        if (knownKeys.has(key) || isSecretKey(key) || key === "raw_form_data" || PAYLOAD_TRANSPORT.has(key)) {
            continue;
        }
        rows.push(row(labelKey(key), formatField(key, value)));
    }
    return rows;
}

export function formatAnalysis(analysisValue, reasonsValue) {
    const analysis = parseJson(analysisValue);
    const source = analysis && typeof analysis === "object" && !Array.isArray(analysis) ? analysis : {};
    const reasons = parseJson(reasonsValue);
    const reasonSource = reasons && typeof reasons === "object" && !Array.isArray(reasons) ? reasons : {};
    const known = new Set([...ANALYSIS_PRIMARY.map(([key]) => key), ...Object.keys(ANALYSIS_EXTRA)]);
    const rows = ANALYSIS_PRIMARY.map(([key, label]) => row(label, formatField(key, source[key])));
    for (const [key, label] of Object.entries(ANALYSIS_EXTRA)) {
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            rows.push(row(label, formatField(key, source[key])));
        }
    }
    const why = Array.isArray(reasonSource.reasons) ? reasonSource.reasons.map((item) => stated(item)) : [];
    const review = Array.isArray(reasonSource.review_reasons)
        ? reasonSource.review_reasons.map((item) => stated(item))
        : [];
    const gates = []
        .concat(reasonSource.cold_gates || [], reasonSource.hot_qualifiers || [])
        .filter((item) => item !== null && item !== undefined && item !== "")
        .map((item) => labelGate(item));
    return {
        sections: [
            section("decision", "", rows),
            section("why", "Why", [], why.length ? why : [NOT_STATED]),
            section("review", "What still needs a broker", [], review.length ? review : [NOT_STATED]),
            section("gates", "Qualifiers", [], gates),
            section("other", "Other", otherRows(source, known)),
        ].filter((item) => item.rows.length || item.bullets.length),
        cards: [],
        technical: technicalText(analysisValue),
    };
}

const VISION_ALWAYS = new Set([
    "observed_form",
    "observed_color",
    "cleanliness",
    "quantity_visible",
    "quantity_notes",
    "contamination_visible",
    "observed_polymer_hint",
    "confidence",
]);

function visionCards(visionValue, imageUrls, attachments) {
    const vision = parseJson(visionValue);
    const results = Array.isArray(vision) ? vision : vision && typeof vision === "object" ? [vision] : [];
    const urls = Array.isArray(parseJson(imageUrls)) ? parseJson(imageUrls) : [];
    const files = Array.isArray(attachments) ? attachments : [];
    const cards = [];
    const count = Math.max(results.length, urls.length);
    for (let index = 0; index < count; index += 1) {
        const result = results[index] && typeof results[index] === "object" ? results[index] : {};
        const fromList = filenameFromUrl(urls[index]);
        const fromVision = filenameFromUrl(result.source_url);
        const named = [fromList, fromVision].find((name) => /\.[A-Za-z0-9]{2,5}$/.test(name));
        const filename = named || fromList || fromVision || (result.Name || result.name ? String(result.Name || result.name) : "");
        const match = files.find(
            (file) => file.name && filename && file.name.toLowerCase() === filename.toLowerCase()
        );
        const imageId = Number(match && match.id);
        const known = new Set(VISION_FIELDS.map(([key]) => key).concat(["source_url", "Name", "name"]));
        const rows = [];
        for (const [key, label] of VISION_FIELDS) {
            if (key === "commercial_color") {
                continue;
            }
            if (!VISION_ALWAYS.has(key) && !Object.prototype.hasOwnProperty.call(result, key)) {
                continue;
            }
            if (key === "observed_color" && !result.observed_color && result.commercial_color) {
                rows.push(row("Color", formatField("commercial_color", result.commercial_color)));
                continue;
            }
            rows.push(row(label, formatField(key, result[key])));
        }
        cards.push({
            id: `photo-${index}`,
            filename: filename || NOT_STATED,
            imageUrl: Number.isInteger(imageId) && imageId > 0 ? `/web/image/${imageId}` : "",
            rows: rows.concat(otherRows(result, known)),
        });
    }
    return cards;
}

export function formatTriage(normalizedValue, visionValue, imageUrls, attachments) {
    const normalized = parseJson(normalizedValue);
    const source = normalized && typeof normalized === "object" && !Array.isArray(normalized) ? normalized : {};
    const known = new Set(TRIAGE_FIELDS.map(([key]) => key).concat(["raw_form_data"]));
    return {
        sections: [
            section(
                "extraction",
                "Extraction",
                TRIAGE_FIELDS.map(([key, label]) => row(label, formatField(key, source[key])))
            ),
            section("other", "Other", otherRows(source, known)),
        ].filter((item) => item.rows.length),
        cards: visionCards(visionValue, imageUrls, attachments),
        technical: technicalText(normalizedValue),
    };
}

function firstText(source, keys) {
    for (const key of keys) {
        const value = source[key];
        if (typeof value === "string" && value.trim()) {
            return value.trim();
        }
        if (typeof value === "number") {
            return String(value);
        }
    }
    return "";
}

function contactName(source) {
    const name = source.Name ?? source.YourName;
    if (typeof name === "string") {
        return name.trim();
    }
    if (name && typeof name === "object") {
        if (typeof name.FirstAndLast === "string" && name.FirstAndLast.trim()) {
            return name.FirstAndLast.trim();
        }
        return [name.First, name.Last].filter((part) => typeof part === "string" && part.trim()).join(" ");
    }
    return "";
}

function photoNames(source) {
    const names = [];
    for (const key of PHOTO_FIELDS) {
        const items = source[key];
        if (!Array.isArray(items)) {
            continue;
        }
        for (const item of items) {
            if (item && typeof item === "object") {
                const name = item.Name || item.name;
                if (name) {
                    names.push(String(name));
                }
            }
        }
    }
    return names;
}

export function formatPayload(payloadValue) {
    const payload = parseJson(payloadValue);
    const source = payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
    const consumed = new Set([
        "YourBusinessCompanyName",
        "company_name",
        "Name",
        "YourName",
        "Email",
        "Phone",
        "PhoneNumber",
        "WhatMaterialIsItMadeFrom",
        "WhatIsIt",
        "DescribeYourMaterial",
        "material_description",
        "WeightPerLoad",
        "weight_per_load_text",
        "WhatIsTheQuantity",
        "quantity_text",
        "LocationOfPickUpCityState",
        "WhereIsItLocated",
        "pickup_location_text",
        "LocationOfPickUpZip",
        ...PHOTO_FIELDS,
    ]);
    const rows = [
        row("Company", stated(firstText(source, ["YourBusinessCompanyName", "company_name"]))),
        row("Contact", stated(contactName(source))),
        row("Email", stated(firstText(source, ["Email"]))),
        row("Phone", stated(firstText(source, ["Phone", "PhoneNumber"]))),
        row(
            "Material",
            stated(firstText(source, ["WhatMaterialIsItMadeFrom", "WhatIsIt", "DescribeYourMaterial", "material_description"]))
        ),
        row("Weight", stated(firstText(source, ["WeightPerLoad", "weight_per_load_text"]))),
        row("Quantity", stated(firstText(source, ["WhatIsTheQuantity", "quantity_text"]))),
        row("Pickup", stated(firstText(source, ["LocationOfPickUpCityState", "WhereIsItLocated", "pickup_location_text"]))),
        row("Zip", stated(firstText(source, ["LocationOfPickUpZip"]))),
        row("Photos", photoNames(source).join(", ") || NOT_STATED),
    ];
    return {
        sections: [
            section("answers", "", rows),
            section("other", "Other", otherRows(source, consumed)),
        ].filter((item) => item.rows.length),
        cards: [],
        technical: technicalText(payloadValue),
    };
}

export function attachmentEntries(value) {
    const records = value && value.records;
    if (!Array.isArray(records)) {
        return [];
    }
    return records
        .map((record) => ({
            id: record.resId,
            name: (record.data && (record.data.display_name || record.data.name)) || "",
        }))
        .filter((file) => file.id);
}
