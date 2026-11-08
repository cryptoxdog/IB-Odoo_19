# PlasticOS Odoo 19 with custom Python dependencies
FROM odoo:19

USER root

# System libs for python-xmlsec (enterprise l10n_nl_reports and install-smoke parity).
# Without these, mounting odoo-enterprise fails module load on import xmlsec.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        pkg-config \
        libxml2-dev \
        libxmlsec1 \
        libxmlsec1-dev \
        libxmlsec1-openssl \
    && rm -rf /var/lib/apt/lists/*

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
