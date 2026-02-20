# -*- coding: utf-8 -*-
# ============================================
# Canonical Header (v4.0 Production Baseline)
# ============================================
# File Name: test_kb_integration.py
# Version: 4.6
# Created: 2025-10-17
# Author: Igor Beylin
# Domain: Plastic Recycling / AI-Augmented ERP
# Purpose: Automated testing for PostgreSQL JSONB KB config integration
# Related Files: ../models/kb_config.py, ../knowledge_base/, ../configs/
# ============================================

"""
KB Integration Test Script
Automated testing for PostgreSQL JSONB KB config integration

Usage:
    python3 test_kb_integration.py
    
Or run via Odoo shell:
    odoo shell -d your_db --addons-path=/path/to/Dev Kit
    >>> exec(open('test_kb_integration.py').read())
"""

def run_kb_integration_tests(env):
    """Run comprehensive KB integration tests"""
    
    print("\n" + "="*60)
    print("KB INTEGRATION TEST SUITE")
    print("="*60 + "\n")
    
    test_results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }
    
    # ============================================
    # TEST 1: KB Config Model Exists
    # ============================================
    print("TEST 1: KB Config Model Exists")
    try:
        KBConfig = env['plastic_ai.kb_config']
        print(" PASS: plastic_ai.kb_config model loaded")
        test_results['passed'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
        return test_results
    
    # ============================================
    # TEST 2: KB Configs Loaded
    # ============================================
    print("\nTEST 2: KB Configs Loaded from YAML")
    try:
        configs = KBConfig.search([('active', '=', True)])
        count = len(configs)
        
        if count == 3:
            print(f" PASS: {count} KB configs loaded (expected: 3)")
            for config in configs:
                print(f"  - {config.key} v{config.version} ({config.config_type})")
            test_results['passed'] += 1
        elif count > 0:
            print(f" WARNING: {count} configs loaded (expected: 3)")
            test_results['warnings'] += 1
        else:
            print(f" FAIL: No configs loaded")
            test_results['failed'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
    
    # ============================================
    # TEST 3: Escalation Matrix Accessible
    # ============================================
    print("\nTEST 3: Escalation Matrix Accessible")
    try:
        escalation_matrix = KBConfig.get_escalation_matrix()
        
        if escalation_matrix and 'escalation_matrix' in escalation_matrix:
            rules_count = len(escalation_matrix['escalation_matrix'])
            print(f" PASS: Escalation matrix loaded with {rules_count} rules")
            
            # Test specific rule
            price_rule = KBConfig.get_escalation_rule('esc_001')
            if price_rule:
                print(f"  - Rule esc_001: {price_rule.get('name')}")
                print(f"    Threshold: {price_rule.get('threshold')}")
                test_results['passed'] += 1
            else:
                print(f" WARNING: Rule esc_001 not found")
                test_results['warnings'] += 1
        else:
            print(f" FAIL: Escalation matrix not found or empty")
            test_results['failed'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
    
    # ============================================
    # TEST 4: QA Ruleset Accessible
    # ============================================
    print("\nTEST 4: QA Verification Ruleset Accessible")
    try:
        qa_ruleset = KBConfig.get_qa_verification_ruleset()
        
        if qa_ruleset and 'validation_rules' in qa_ruleset:
            rules_count = len(qa_ruleset['validation_rules'])
            print(f" PASS: QA ruleset loaded with {rules_count} rules")
            
            # Test specific rule
            schema_rule = KBConfig.get_qa_rule('qa_preprocess_001')
            if schema_rule:
                print(f"  - Rule qa_preprocess_001: {schema_rule.get('name')}")
                print(f"    Enforcement: {schema_rule.get('enforcement')}")
                test_results['passed'] += 1
            else:
                print(f" WARNING: Rule qa_preprocess_001 not found")
                test_results['warnings'] += 1
        else:
            print(f" FAIL: QA ruleset not found or empty")
            test_results['failed'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
    
    # ============================================
    # TEST 5: PostgreSQL Table Structure
    # ============================================
    print("\nTEST 5: PostgreSQL Table Structure")
    try:
        env.cr.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'plastic_ai_kb_config'
            ORDER BY ordinal_position
        """)
        columns = env.cr.fetchall()
        
        if columns:
            print(f" PASS: Table plastic_ai_kb_config exists with {len(columns)} columns")
            required_columns = ['key', 'version', 'config_type', 'config_data']
            found_columns = [col[0] for col in columns]
            
            all_required_present = all(col in found_columns for col in required_columns)
            if all_required_present:
                print(f"  - All required columns present")
                test_results['passed'] += 1
            else:
                print(f" WARNING: Some required columns missing")
                test_results['warnings'] += 1
        else:
            print(f" FAIL: Table not found")
            test_results['failed'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
    
    # ============================================
    # TEST 6: Offer Response Integration
    # ============================================
    print("\nTEST 6: Offer Response Escalation Integration")
    try:
        OfferResponse = env['plastic_ai.offer_response']
        
        # Check if _check_escalation_rules method exists
        if hasattr(OfferResponse, '_check_escalation_rules'):
            print(f" PASS: Offer Response has escalation integration")
            test_results['passed'] += 1
        else:
            print(f" FAIL: Escalation method not found in Offer Response")
            test_results['failed'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
    
    # ============================================
    # TEST 7: Supplier Intake Integration
    # ============================================
    print("\nTEST 7: Supplier Intake QA Integration")
    try:
        SupplierIntake = env['plastic_ai.supplier_intake']
        
        # Check if _run_qa_validation method exists
        if hasattr(SupplierIntake, '_run_qa_validation'):
            print(f" PASS: Supplier Intake has QA validation integration")
            test_results['passed'] += 1
        else:
            print(f" FAIL: QA validation method not found in Supplier Intake")
            test_results['failed'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
    
    # ============================================
    # TEST 8: Config Data Size Check
    # ============================================
    print("\nTEST 8: Config Data Storage")
    try:
        env.cr.execute("""
            SELECT key, 
                   pg_column_size(config_data) as size_bytes,
                   length(config_data) as length_chars
            FROM plastic_ai_kb_config
            WHERE active = true
        """)
        results = env.cr.fetchall()
        
        if results:
            print(f" PASS: Config data stored in PostgreSQL")
            for key, size, length in results:
                print(f"  - {key}: {size} bytes, {length} chars")
            test_results['passed'] += 1
        else:
            print(f" WARNING: No config data found")
            test_results['warnings'] += 1
    except Exception as e:
        print(f" FAIL: {e}")
        test_results['failed'] += 1
    
    # ============================================
    # SUMMARY
    # ============================================
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f" Passed:   {test_results['passed']}")
    print(f" Warnings: {test_results['warnings']}")
    print(f" Failed:   {test_results['failed']}")
    print(f"\nTotal Tests: {test_results['passed'] + test_results['failed'] + test_results['warnings']}")
    
    if test_results['failed'] == 0:
        print("\n ALL TESTS PASSED! KB Integration is working correctly.")
        print(" Ready for deployment to hosted instance.")
    elif test_results['failed'] < 3:
        print("\n  SOME TESTS FAILED. Review failures before deployment.")
    else:
        print("\n CRITICAL FAILURES. Fix issues before proceeding.")
    
    print("="*60 + "\n")
    
    return test_results


# ============================================
# Main Execution
# ============================================
if __name__ == '__main__':
    print("\n  This script should be run from Odoo shell")
    print("\nUsage:")
    print("  odoo shell -d your_database --addons-path=/path/to/Dev Kit")
    print("  >>> exec(open('test_kb_integration.py').read())")
    print("\nOr:")
    print("  >>> from test_kb_integration import run_kb_integration_tests")
    print("  >>> results = run_kb_integration_tests(env)")
else:
    # Running in Odoo shell context
    if 'env' in dir():
        results = run_kb_integration_tests(env)
    else:
        print("Error: 'env' not found. Are you running in Odoo shell?")

