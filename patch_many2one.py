#!/usr/bin/env python3
"""
Smart patcher: adds ondelete= to Many2one fields missing it.
Handles both single-line and multi-line declarations.

Strategy:
- child/subordinate models (lines, penalties, logs, etc.): cascade
- res.users, res.partner, res.company, res.currency: restrict
- all others: restrict (safe default)
"""

import re
import sys
import os
from pathlib import Path

# Models/contexts where cascade makes sense (child/subordinate)
CASCADE_FIELD_PATTERNS = [
    r'transaction_id',
    r'intake_id',
    r'claim_id',
    r'load_id',
    r'payout_id',
    r'rule_id',
    r'penalty_id',
    r'header_id',
    r'order_id',
    r'picking_id',
    r'move_id',
    r'line_id',
]

# Known "restrict" comodel patterns
RESTRICT_COMODEL_PATTERNS = [
    r'res\.users',
    r'res\.partner',
    r'res\.company',
    r'res\.currency',
    r'uom\.uom',
    r'product\.product',
    r'product\.template',
    r'account\.account',
    r'account\.journal',
    r'account\.tax',
    r'stock\.warehouse',
    r'stock\.location',
    r'res\.country',
    r'res\.lang',
]


def decide_ondelete(field_name: str, comodel: str, file_path: str) -> str:
    """Decide ondelete value based on field name and comodel."""
    # Always restrict for system models
    for pat in RESTRICT_COMODEL_PATTERNS:
        if re.search(pat, comodel):
            return 'restrict'
    
    # Check if field name suggests child/subordinate relationship
    for pat in CASCADE_FIELD_PATTERNS:
        if re.match(pat, field_name):
            return 'cascade'
    
    # File-level heuristics: if file is in a "_line" or "penalty" or "log" model
    fname = os.path.basename(file_path)
    if any(x in fname for x in ['_line', 'penalty', '_log', '_detail', '_item']):
        # Only cascade the parent reference fields
        if field_name.endswith('_id') and any(
            field_name.startswith(x) for x in [
                'transaction', 'intake', 'claim', 'load', 'order', 'move',
                'payout', 'rule', 'header', 'picking', 'penalty'
            ]
        ):
            return 'cascade'
    
    return 'restrict'


def patch_file(filepath: str) -> int:
    """Patch a single Python file. Returns count of fields patched."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    patch_count = 0
    
    # We need to find Many2one declarations that span possibly multiple lines
    # and add ondelete= if not present.
    # 
    # Strategy: find "fields.Many2one(" then collect the full argument block
    # (respecting nested parens), check for ondelete, add if missing.
    
    result = []
    i = 0
    
    while i < len(content):
        # Look for fields.Many2one( 
        match = re.search(r'fields\.Many2one\s*\(', content[i:])
        if not match:
            result.append(content[i:])
            break
        
        start = i + match.start()
        paren_start = i + match.end() - 1  # position of '('
        
        # Append everything up to the start of this match
        result.append(content[i:start])
        
        # Now find the matching closing paren for this Many2one(
        depth = 0
        j = paren_start
        while j < len(content):
            c = content[j]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        
        # The full declaration is content[start:j+1]
        declaration = content[start:j+1]
        inner = content[paren_start+1:j]  # content between the outer parens
        
        # Check if ondelete is already present
        if 'ondelete' in declaration:
            result.append(declaration)
            i = j + 1
            continue
        
        # Skip if it's commented out
        # Check if the line containing this declaration is commented
        line_start = content.rfind('\n', 0, start) + 1
        line_prefix = content[line_start:start]
        if '#' in line_prefix:
            result.append(declaration)
            i = j + 1
            continue
        
        # Extract field name from context (look backwards for "fieldname = ")
        context_before = content[max(0, start-200):start]
        field_name_match = re.search(r'(\w+)\s*=\s*$', context_before.rstrip())
        field_name = field_name_match.group(1) if field_name_match else ''
        
        # Extract comodel (first string argument)
        comodel_match = re.search(r'''["']([^"']+)["']''', inner)
        comodel = comodel_match.group(1) if comodel_match else ''
        
        ondelete = decide_ondelete(field_name, comodel, filepath)
        
        # Now patch: add ondelete="..." before the closing paren
        # Find last non-whitespace before closing paren
        stripped_inner = inner.rstrip()
        trailing_ws = inner[len(stripped_inner):]
        
        # Handle trailing comma and whitespace
        if stripped_inner.endswith(','):
            new_inner = stripped_inner + f'\n        ondelete="{ondelete}",' + trailing_ws
        else:
            new_inner = stripped_inner + f', ondelete="{ondelete}"' + trailing_ws
        
        new_declaration = f'fields.Many2one({new_inner})'
        result.append(new_declaration)
        patch_count += 1
        i = j + 1
    
    new_content = ''.join(result)
    
    if patch_count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  Patched {patch_count} field(s) in {filepath}")
    
    return patch_count


def main():
    # Find all .py files in plasticos_*/models/ and plasticos_*/wizard/
    base = Path('.')
    py_files = []
    for pattern in ['plasticos_*/models/*.py', 'plasticos_*/wizard/*.py']:
        py_files.extend(base.glob(pattern))
    
    total = 0
    for fp in sorted(py_files):
        count = patch_file(str(fp))
        total += count
    
    print(f"\nTotal Many2one fields patched: {total}")
    return total


if __name__ == '__main__':
    main()
