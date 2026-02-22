# PlasticOS Odoo 19 with custom Python dependencies
FROM odoo:19

USER root

# Install Python dependencies from requirements.txt
# --break-system-packages: required for Python 3.12+ (PEP 668)
# --ignore-installed: avoid conflicts with Debian-managed packages
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

USER odoo
