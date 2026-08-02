# PlasticOS Odoo 19 with custom Python dependencies
FROM odoo:19

USER root

# Install Python dependencies from requirements.txt, pinned via constraints.txt
# (SonarCloud S8541/S8544: reproducible installs — every transitive resolution is
# locked in constraints.txt; regenerate with `make lock-deps`).
# --break-system-packages: required for Python 3.12+ (PEP 668)
# --ignore-installed: avoid conflicts with Debian-managed packages
COPY requirements.txt constraints.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    -r /tmp/requirements.txt -c /tmp/constraints.txt \
    && rm /tmp/requirements.txt /tmp/constraints.txt

USER odoo
