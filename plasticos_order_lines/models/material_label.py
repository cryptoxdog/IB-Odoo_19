import re

_TRAILING_DETAIL = re.compile(r"\s*\([^)]*\)\s*$")


def projected_material(line):
    """Product name, then the line specs, joined with dashes.

    A trailing parenthetical on the product name is dropped so a color stored
    in the grade, such as ``(CLEAR)``, is not repeated before the color spec.
    A line with no specs has nothing to project.
    """
    specs = []
    for record in (
        line.color_id,
        line.filler_type_id,
        line.form_id,
        line.packaging_type_id,
        line.source_type_id,
    ):
        name = (record.name or "").strip() if record else ""
        if name and name not in specs:
            specs.append(name)
    if line.material_attribute_ids:
        attributes = ", ".join(name for name in line.material_attribute_ids.mapped("name") if name)
        if attributes and attributes not in specs:
            specs.append(attributes)
    if not specs:
        return ""
    product = ""
    if line.product_id:
        product = _TRAILING_DETAIL.sub("", (line.product_id.name or "").strip()).strip()
    if not product and line.product_id and line.product_id.polymer_id:
        product = (line.product_id.polymer_id.name or "").strip()
    if product and product not in specs:
        return " - ".join([product, *specs])
    return " - ".join(specs)
