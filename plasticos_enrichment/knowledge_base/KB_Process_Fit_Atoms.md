
---
title: Process Fit Atoms - Polymer Manufacturing Compatibility
version: 6.0.0
created: 2025-10-28T17:00:00Z
updated: 2025-10-28T17:00:00Z
owner: Igor Beylin
platform: Odoo 19
source: PlastOS v6.0 Knowledge Base System
tags: [knowledge-base, process-fit, atoms, polymer, manufacturing, compatibility, v6.0]
domain: plastos.knowledge_base
type: process-fit-atoms
production_ready: true
reasoning_enabled: true
---

# ----------------------------------------------------------------------
# 🧩 PROCESS-FIT ATOMS
# ----------------------------------------------------------------------

process_fit_atoms:

  - id: HDPE_BLOW_MOLD_2025
    meta_ref: "Blow Molding Process-Fit Framework"
    when:
      - process_eq: "blow_molding"
    infer:
      mi_range: "0.03–0.5 g/10 min"
      hlmi_mi_ratio_ge: 30
      density_range: "0.945–0.962 g/cm³"
      escr_condition_b_min_hours: 200
      escr_premium_hours: 600
      parison_swell_ratio: "1.3–1.7"
      blow_up_ratio_range: "1.5–3.0"
      recycle_content_le: 0.6
      reasoning: >
        Low-MFI (HMW) HDPE ensures parison stability and ESCR performance.
        MI > 0.7 g/10 min diverts to injection; density 0.949–0.955 g/cm³ optimizes
        stiffness vs. impact. Recycled content ≤60% acceptable for non-critical drums.
      process_fit: ["blow_molding"]  # type: list[str]
      buyer_target: ["container_molder","drum_molder"]  # type: list[str]
    confidence: 0.93
    performance:
      auto_update: true
      use_count: 0
      success_rate: 0.0
      last_updated: "2025-10-25"
    related_atoms: ["HDPE_FRAC_MELT_BLEND_2025"]

  - id: HDPE_PIPE_EXTRUSION_2025
    meta_ref: "Pipe Extrusion: PE4710, PE100, and Recycled Content Frameworks"
    when:
      - process_eq: "pipe_extrusion"
    infer:
      density_ge: 0.950
      escr_test: "PENT or FNCT"
      pent_hours_ge: 2000
      recycled_content_le: 0.3
      corrugated_recycle_content_range: "0.4–1.0"
      reasoning: >
        PE4710/PE100 classes (0.950–0.960 g/cm³) provide 50–100-year service life.
        Recycled content ≤30% viable for low-pressure; corrugated drainage pipe can use up to 100% PCR if NCLS ≥18 h and density ≥0.941 g/cm³.
      process_fit: ["pipe_extrusion"]  # type: list[str]
      buyer_target: ["pressure_pipe_extruder","corrugated_pipe_extruder"]  # type: list[str]
    confidence: 0.94
    performance:
      auto_update: true
      use_count: 0
      success_rate: 0.0
      last_updated: "2025-10-25"
    related_atoms: ["HDPE_SCG_2025"]

  - id: HDPE_FILM_EXTRUSION_2025
    meta_ref: "Film Extrusion: Melt Index, Dart Impact, and Processing Balance"
    when:
      - process_eq: "film_extrusion"
    infer:
      mi_range: "0.5–2.5 g/10 min"
      dart_impact_g: "100–600"
      density_range: "0.941–0.955 g/cm³"
      neck_in_percent: "10–20"
      die_swell_ratio: "1.2–1.5"
      antiblock_ppm: "2500–10000"
      slip_ppm: "600–2000"
      recycled_content_range: "0.2–0.5"
      reasoning: >
        Recycled HDPE films (MI 1.5–3.0) blend with virgin for 20–50% PCR use.
        Dart impact decreases with MI; antiblock and slip additives restore handling.
      process_fit: ["film_extrusion"]  # type: list[str]
      buyer_target: ["film_extruder","liner_producer"]  # type: list[str]
    confidence: 0.92
    performance:
      auto_update: true
      use_count: 0
      success_rate: 0.0
      last_updated: "2025-10-25"
    related_atoms: ["HDPE_BLOW_MOLD_2025"]

  - id: HDPE_INJECTION_MOLD_2025
    meta_ref: "Injection Molding: Flow Length, Shrinkage Control, and Cycle Optimization"
    when:
      - process_eq: "injection_molding"
    infer:
      mi_range: "1–40 g/10 min"
      density_range: "0.945–0.965 g/cm³"
      shrinkage_percent: "1.5–4.0"
      pack_pressure_percent_of_injection: "60–85"
      mold_temp_range_c: "40–80"
      reasoning: >
        HDPE injection grades span MI 1–40 for thick- to thin-wall parts.
        Shrinkage 1.5–4% managed by packing 60–85% of injection pressure
        and mold temps 40–80 °C; recycled HDPE may deviate ±25%.
      process_fit: ["injection_molding"]  # type: list[str]
      buyer_target: ["crate_molder","cap_closure_molder","pallet_molder"]  # type: list[str]
    confidence: 0.94
    performance:
      auto_update: true
      use_count: 0
      success_rate: 0.0
      last_updated: "2025-10-25"
    related_atoms: ["HDPE_TALC_FILL_2025"]

  - id: HDPE_SHEET_THERMOFORM_2025
    meta_ref: "Sheet Extrusion and Thermoforming: Material Architecture for Reheating"
    when:
      - process_eq: "thermoforming"
    infer:
      sheet_temp_range_c: "140–180"
      reheating_rate_c_per_s: "0.3–1.0"
      sag_resistance: "medium"
      talc_loading_percent: "10–30"
      density_range: "0.945–0.960 g/cm³"
      reasoning: >
        Talc-filled HDPE/PP sheets (10–30 %) provide stiffness 2–3 GPa.
        Forming at 140–180 °C with 0.3–1 °C/s reheating yields balanced
        sag and formability; PCR content 25–50% feasible for non-clear parts.
      process_fit: ["sheet_extrusion","thermoforming"]  # type: list[str]
      buyer_target: ["thermoformer","sheet_extruder"]  # type: list[str]
    confidence: 0.93
    performance:
      auto_update: true
      use_count: 0
      success_rate: 0.0
      last_updated: "2025-10-25"
    related_atoms: ["HDPE_FILM_EXTRUSION_2025","PP_RANDOM_COPOLYMER_2025"]

# ----------------------------------------------------------------------
# 📘 FOOTER / GOVERNANCE
# ----------------------------------------------------------------------

governance:
  validation_method: "ASTM & ISO cross-reference"
  last_audit: "2025-10-25"
  license: "CC BY-SA 4.0"
  notes: >
    Each process-fit atom maps property windows to process suitability.
    Values derived from academic + industrial references [2–85].
    Use as decision-support; validate locally before certification.
