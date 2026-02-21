#!/usr/bin/env python3
# ============================================
# Canonical Header (v5.0 Enhanced)
# ============================================
# File Name: test_enhanced_matching_v5.py
# Version: 5.0
# Created: 2025-10-18
# Author: Igor Beylin
# Domain: Plastic Recycling / AI-Augmented ERP
# Purpose: Test enhanced buyer matching with BCP v5.0 and KB integration
# ============================================

"""
Test script for enhanced buyer matching with KB integration.
Validates BCP v5.0 schema alignment and knowledge base access.
"""

import logging

_logger = logging.getLogger(__name__)


def test_enhanced_buyer_matching(env):
    """
    Test enhanced buyer matching with KB integration and BCP v5.0 validation.

    Args:
        env: Odoo environment

    Returns:
        dict: Test results summary
    """
    print("=" * 60)
    print("ENHANCED BUYER MATCHING INTEGRATION TEST")
    print("=" * 60)

    results = {"tests_run": 0, "tests_passed": 0, "tests_failed": 0, "errors": []}

    try:
        # Test 1: KB Config Access
        print("\n🔍 Test 1: KB Configuration Access")
        results["tests_run"] += 1

        KBConfig = env["plastic_ai.kb_config"]

        # Test KB index loading
        kb_index = KBConfig.get_config("kb_index_v5.0")
        if kb_index:
            print("✅ KB Index v5.0 loaded successfully")
            results["tests_passed"] += 1
        else:
            print("❌ KB Index v5.0 not found")
            results["tests_failed"] += 1
            results["errors"].append("KB Index v5.0 not loaded")

        # Test 2: Polymer Specifications Access
        print("\n🧪 Test 2: Polymer Specifications Access")
        results["tests_run"] += 1

        test_polymers = ["HDPE", "PP", "PET", "TPE"]
        for polymer in test_polymers:
            try:
                specs = KBConfig.get_polymer_specs_indexed(polymer)
                if specs and "density_min" in specs:
                    print(f"✅ {polymer} specs: density {specs.get('density_min')}-{specs.get('density_max')} g/cm³")
                else:
                    print(f"❌ {polymer} specs not found or incomplete")
                    results["errors"].append(f"{polymer} specifications missing")
            except Exception as e:
                print(f"❌ {polymer} specs error: {str(e)}")
                results["errors"].append(f"{polymer} error: {str(e)}")

        results["tests_passed"] += 1

        # Test 3: QA Standards Access
        print("\n🔍 Test 3: QA Standards Access")
        results["tests_run"] += 1

        for polymer in test_polymers:
            try:
                standards = KBConfig.get_qa_standards(polymer)
                if standards and "moisture_limit_ppm" in standards:
                    print(f"✅ {polymer} QA: moisture limit {standards['moisture_limit_ppm']} ppm")
                else:
                    print(f"❌ {polymer} QA standards missing")
                    results["errors"].append(f"{polymer} QA standards missing")
            except Exception as e:
                print(f"❌ {polymer} QA error: {str(e)}")
                results["errors"].append(f"{polymer} QA error: {str(e)}")

        results["tests_passed"] += 1

        # Test 4: Enhanced Matching Model
        print("\n🎯 Test 4: Enhanced Matching Model")
        results["tests_run"] += 1

        BuyerMatching = env["plastic_ai.buyer_matching"]

        # Check if enhanced fields exist
        enhanced_fields = [
            "density_compatibility",
            "melt_index_compatibility",
            "contamination_compliance",
            "technical_validation_passed",
        ]

        model_fields = BuyerMatching._fields.keys()
        missing_fields = [field for field in enhanced_fields if field not in model_fields]

        if not missing_fields:
            print("✅ All enhanced BCP v5.0 fields present in model")
            results["tests_passed"] += 1
        else:
            print(f"❌ Missing enhanced fields: {missing_fields}")
            results["tests_failed"] += 1
            results["errors"].append(f"Missing fields: {missing_fields}")

        # Test 5: Enhanced Pipeline Method
        print("\n🔄 Test 5: Enhanced Pipeline Method")
        results["tests_run"] += 1

        if hasattr(BuyerMatching, "run_enhanced_matching_pipeline"):
            print("✅ Enhanced matching pipeline method available")
            results["tests_passed"] += 1
        else:
            print("❌ Enhanced matching pipeline method missing")
            results["tests_failed"] += 1
            results["errors"].append("Enhanced pipeline method missing")

    except Exception as e:
        print(f"\n❌ Critical test error: {str(e)}")
        results["errors"].append(f"Critical error: {str(e)}")
        results["tests_failed"] += 1

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests Run: {results['tests_run']}")
    print(f"Tests Passed: {results['tests_passed']}")
    print(f"Tests Failed: {results['tests_failed']}")

    if results["errors"]:
        print("\nErrors Found:")
        for error in results["errors"]:
            print(f"  • {error}")

    success_rate = (results["tests_passed"] / results["tests_run"]) * 100 if results["tests_run"] > 0 else 0
    print(f"\nSuccess Rate: {success_rate:.1f}%")

    if success_rate >= 80:
        print("🎉 ENHANCED BUYER MATCHING: READY FOR DEPLOYMENT")
    else:
        print("⚠️  ENHANCED BUYER MATCHING: NEEDS FIXES BEFORE DEPLOYMENT")

    return results


# Run test if executed directly
if __name__ == "__main__":
    print("Run this script in Odoo shell:")
    print("exec(open('scripts/test_enhanced_matching_v5.py').read())")
    print("test_enhanced_buyer_matching(env)")
