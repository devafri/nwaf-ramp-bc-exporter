# transform.py

import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
import json

# Define the standard BC General Journal column order
BC_COLUMN_ORDER = [
    'Journal Template Name', 'Journal Batch Name', 'Line No.', 'Posting Date', 
    'Document Type', 'Document No.', 'Account Type', 'Account No.', 
    'Description', 'Debit Amount', 'Credit Amount', 'Bal. Account Type', 
    'Bal. Account No.', 'Department Code', 'Activity Code'
]

def ramp_to_bc_rows(transactions: List[Dict[str, Any]], cfg: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts a list of Ramp transactions into a DataFrame suitable for BC import,
    using the G/L Account number already coded in the Ramp transaction data.
    """
    if not transactions:
        print("No transactions provided for transformation.")
        return pd.DataFrame()

    print(f"--- Transforming {len(transactions)} transactions using direct G/L mapping ---")
    
    journal_lines = []
    line_no_base = 1000
    
    # Configuration from config.toml
    bc_cfg = cfg['business_central']
    
    # --- !!! CRITICAL: VERIFY AND SET THE CORRECT KEY HERE !!! ---
    # This key must match the field in the Ramp API response that holds the BC G/L Account No.
    RAMP_GL_ACCOUNT_KEY = cfg['gl_mapping']['ramp_gl_account_key'] 
    
    for index, t in enumerate(transactions):
        # 1. Extract and standardize data
        amount_major_units = t.get('amount', 0)  # Already in major units (dollars)
        
        # Use transaction date for posting date
        trans_date_str = t.get('user_transaction_time', datetime.now().strftime('%Y-%m-%d'))
        posting_date = datetime.strptime(trans_date_str[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
        
        doc_no = f"RAMP-{t.get('id', index)}" 
        description = t.get('memo', t.get('merchant_name', 'Ramp Transaction'))
        
        # 2. EXTRACT ACCOUNTING DIMENSIONS FROM LINE ITEMS
        # Look in line_items[0].accounting_field_selections for all types
        trans_gl_account = None
        department_code = None
        activity_code = None
        
        line_items = t.get('line_items', [])
        if line_items and line_items[0].get('accounting_field_selections'):
            for selection in line_items[0]['accounting_field_selections']:
                if selection.get('type') == 'GL_ACCOUNT':
                    trans_gl_account = str(selection.get('external_code', '')).strip()
                elif selection.get('type') == 'OTHER':
                    external_id = selection.get('category_info', {}).get('external_id')
                    if external_id == 'Department':
                        department_code = str(selection.get('external_code', '')).strip()
                    elif external_id == 'Activity Code':
                        activity_code = str(selection.get('external_code', '')).strip()
        
        if not trans_gl_account or trans_gl_account in ('None', 'null', ''):
             print(f"⚠️ Warning: Transaction {doc_no} is missing a G/L Account code. Skipping.")
             continue # Skip transactions that are not fully coded

        # 3. CARD TRANSACTIONS: Use "Payment" document type (accounting best practice)
        # Credit card transactions are classified as payments since they represent
        # the disbursement/payment to merchants/vendors
        gl_debit = amount_major_units  # Debit the expense account
        gl_credit = 0.0
        bank_debit = 0.0
        bank_credit = amount_major_units  # Credit the bank account
        doc_type = 'Payment'  # Appropriate for disbursements/payments

        # 4. Create the journal line
        journal_lines.append({
            'Journal Template Name': bc_cfg.get('template_name', 'GENERAL'),
            'Journal Batch Name': bc_cfg.get('batch_name', 'RAMP_IMPORT'),
            'Line No.': line_no_base,
            'Posting Date': posting_date,
            'Document Type': doc_type,
            'Document No.': doc_no,
            'Account Type': 'G/L Account',
            'Account No.': trans_gl_account, # DIRECTLY USE THE RAMP-CODED ACCOUNT
            'Description': description,
            'Debit Amount': round(gl_debit, 2),
            'Credit Amount': round(gl_credit, 2),
            'Bal. Account Type': 'G/L Account',
            'Bal. Account No.': bc_cfg['ramp_card_account'],
            'Department Code': department_code or '',
            'Activity Code': activity_code or '',
        })
        line_no_base += 1000

    df_output = pd.DataFrame(journal_lines)
    if df_output.empty:
        print("No valid transactions found with G/L account codes. Returning empty DataFrame.")
        return pd.DataFrame(columns=BC_COLUMN_ORDER)
    return df_output[BC_COLUMN_ORDER]


def ramp_bills_to_bc_rows(bills: List[Dict[str, Any]], cfg: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts Ramp bills into Business Central journal entries.
    Bills are typically vendor invoices that need payment.
    """
    if not bills:
        print("No bills provided for transformation.")
        return pd.DataFrame()

    print(f"--- Transforming {len(bills)} bills ---")
    
    journal_lines = []
    line_no_base = 1000
    bc_cfg = cfg['business_central']
    
    for index, bill in enumerate(bills):
        # Extract bill data
        amount_obj = bill.get('amount', {})
        if isinstance(amount_obj, dict):
            minor_amount = amount_obj.get('amount', 0)
            conversion_rate = amount_obj.get('minor_unit_conversion_rate', 100)
            amount = minor_amount / conversion_rate
        else:
            # Fallback if amount is already a number
            amount = float(amount_obj) if amount_obj else 0.0
            
        bill_date = bill.get('bill_date', bill.get('created_at', ''))
        posting_date = bill_date[:10] if bill_date else datetime.now().strftime('%Y-%m-%d')
        
        doc_no = f"BILL-{bill.get('id', index)}"
        
        # Get description from bill memo, or line item memo, or fallback
        description = bill.get('memo')
        if not description:
            line_items = bill.get('line_items', [])
            if line_items and line_items[0].get('memo'):
                description = line_items[0]['memo']
        if not description:
            description = f"Bill from {bill.get('vendor', {}).get('name', 'Unknown Vendor')}"
        
        # Extract accounting dimensions from line items
        gl_account = None
        department_code = None
        activity_code = None
        
        line_items = bill.get('line_items', [])
        if line_items and line_items[0].get('accounting_field_selections'):
            for selection in line_items[0]['accounting_field_selections']:
                category_type = selection.get('category_info', {}).get('type')
                if category_type == 'GL_ACCOUNT':
                    gl_account = str(selection.get('external_code', '')).strip()
                elif category_type == 'OTHER':
                    external_id = selection.get('category_info', {}).get('external_id')
                    if external_id == 'Department':
                        department_code = str(selection.get('external_code', '')).strip()
                    elif external_id == 'Activity Code':
                        activity_code = str(selection.get('external_code', '')).strip()
        
        # Bills create payables: Debit Expense, Credit Vendor Payable
        # Use the coded expense account if available, otherwise suspense account
        expense_account = gl_account if gl_account and gl_account not in ('None', 'null', '') else bc_cfg.get('vendor_payable_account', '20000')
        
        journal_lines.append({
            'Journal Template Name': bc_cfg.get('template_name', 'GENERAL'),
            'Journal Batch Name': bc_cfg.get('batch_name', 'RAMP_BILLS'),
            'Line No.': line_no_base,
            'Posting Date': posting_date,
            'Document Type': 'Invoice',  # Bills are invoices from vendors
            'Document No.': doc_no,
            'Account Type': 'G/L Account',
            'Account No.': expense_account,  # Use coded expense account
            'Description': description,
            'Debit Amount': round(amount, 2),  # Debit the expense account
            'Credit Amount': 0.0,
            'Bal. Account Type': 'G/L Account',
            'Bal. Account No.': bc_cfg.get('vendor_payable_account', '20000'),  # Credit vendor payable
            'Department Code': department_code or '',
            'Activity Code': activity_code or '',
        })
        line_no_base += 1000

    df_output = pd.DataFrame(journal_lines)
    if df_output.empty:
        return pd.DataFrame(columns=BC_COLUMN_ORDER)
    return df_output[BC_COLUMN_ORDER]


def ramp_reimbursements_to_bc_rows(reimbursements: List[Dict[str, Any]], cfg: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts Ramp reimbursements into Business Central journal entries.
    Reimbursements are employee expense reimbursements that should use the employee's expense coding.
    """
    if not reimbursements:
        print("No reimbursements provided for transformation.")
        return pd.DataFrame()

    print(f"--- Transforming {len(reimbursements)} reimbursements using employee-coded G/L accounts ---")
    
    journal_lines = []
    line_no_base = 1000
    bc_cfg = cfg['business_central']
    
    for index, reimbursement in enumerate(reimbursements):
        # Extract reimbursement data
        created_date = reimbursement.get('created_at', '')
        posting_date = created_date[:10] if created_date else datetime.now().strftime('%Y-%m-%d')
        
        doc_no = f"REIMB-{reimbursement.get('id', index)}"
        employee_name = reimbursement.get('user', {}).get('name', 'Employee')
        
        # Process line items (similar to transactions)
        line_items = reimbursement.get('line_items', [])
        if not line_items:
            print(f"⚠️ Warning: Reimbursement {doc_no} has no line items. Skipping.")
            continue
            
        for line_index, line_item in enumerate(line_items):
            # Extract amount from the amount object
            amount_obj = line_item.get('amount', {})
            if isinstance(amount_obj, dict):
                minor_amount = amount_obj.get('amount', 0)
                conversion_rate = amount_obj.get('minor_unit_conversion_rate', 100)
                amount = minor_amount / conversion_rate
            else:
                # Fallback if amount is already a number
                amount = float(amount_obj) if amount_obj else 0.0
            
            description = reimbursement.get('memo') or f"Reimbursement for {employee_name}"
            
            # Extract accounting dimensions from line item
            gl_account = None
            department_code = None
            activity_code = None
            
            accounting_fields = line_item.get('accounting_field_selections', [])
            for selection in accounting_fields:
                if selection.get('type') == 'GL_ACCOUNT':
                    gl_account = str(selection.get('external_code', '')).strip()
                elif selection.get('type') == 'OTHER':
                    external_id = selection.get('category_info', {}).get('external_id')
                    if external_id == 'Department':
                        department_code = str(selection.get('external_code', '')).strip()
                    elif external_id == 'Activity Code':
                        activity_code = str(selection.get('external_code', '')).strip()
            
            if not gl_account or gl_account in ('None', 'null', ''):
                print(f"⚠️ Warning: Reimbursement line {line_index} in {doc_no} is missing a G/L Account code. Skipping.")
                continue
            
            # Reimbursements: Debit the employee's expense account, Credit bank account
            journal_lines.append({
                'Journal Template Name': bc_cfg.get('template_name', 'GENERAL'),
                'Journal Batch Name': bc_cfg.get('batch_name', 'RAMP_REIMB'),
                'Line No.': line_no_base,
                'Posting Date': posting_date,
                'Document Type': 'Payment',
                'Document No.': doc_no,
                'Account Type': 'G/L Account',
                'Account No.': gl_account,  # Employee-coded expense account
                'Description': description,
                'Debit Amount': round(amount, 2),
                'Credit Amount': 0.0,
                'Bal. Account Type': 'G/L Account',
                'Bal. Account No.': bc_cfg.get('bank_account', '11005'),  # Bank account (reimbursement payment)
                'Department Code': department_code or '',
                'Activity Code': activity_code or '',
            })
            line_no_base += 1000

    df_output = pd.DataFrame(journal_lines)
    if df_output.empty:
        print("No valid reimbursements found with G/L account codes. Returning empty DataFrame.")
        return pd.DataFrame(columns=BC_COLUMN_ORDER)
    return df_output[BC_COLUMN_ORDER]


def ramp_cashbacks_to_bc_rows(cashbacks: List[Dict[str, Any]], cfg: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts Ramp cashbacks into Business Central journal entries.
    Cashbacks are rewards/credits from credit card usage.
    """
    if not cashbacks:
        print("No cashbacks provided for transformation.")
        return pd.DataFrame()

    print(f"--- Transforming {len(cashbacks)} cashbacks ---")
    
    journal_lines = []
    line_no_base = 1000
    bc_cfg = cfg['business_central']
    
    for index, cashback in enumerate(cashbacks):
        amount_obj = cashback.get('amount', {})
        if isinstance(amount_obj, dict):
            minor_amount = amount_obj.get('amount', 0)
            conversion_rate = amount_obj.get('minor_unit_conversion_rate', 100)
            amount = minor_amount / conversion_rate
        else:
            # Fallback if amount is already a number
            amount = float(amount_obj) if amount_obj else 0.0
            
        earned_date = cashback.get('earned_at', '')
        posting_date = earned_date[:10] if earned_date else datetime.now().strftime('%Y-%m-%d')
        
        doc_no = f"CASHBACK-{cashback.get('id', index)}"
        description = f"Cashback reward - {cashback.get('description', 'Credit card cashback')}"
        
        # Cashbacks: Debit Cashback Income, Credit Bank/Card
        journal_lines.append({
            'Journal Template Name': bc_cfg.get('template_name', 'GENERAL'),
            'Journal Batch Name': bc_cfg.get('batch_name', 'RAMP_CASHBACK'),
            'Line No.': line_no_base,
            'Posting Date': posting_date,
            'Document Type': 'Payment',
            'Document No.': doc_no,
            'Account Type': 'G/L Account',
            'Account No.': bc_cfg.get('other_income_account', '40000'),  # Other income account
            'Description': description,
            'Debit Amount': round(amount, 2),
            'Credit Amount': 0.0,
            'Bal. Account Type': 'G/L Account',
            'Bal. Account No.': bc_cfg.get('bank_account', '11005'),
            'Department Code': '',
            'Activity Code': '',
        })
        line_no_base += 1000

    df_output = pd.DataFrame(journal_lines)
    if df_output.empty:
        return pd.DataFrame(columns=BC_COLUMN_ORDER)
    return df_output[BC_COLUMN_ORDER]


def ramp_statements_to_bc_rows(statements: List[Dict[str, Any]], cfg: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts Ramp statements into Business Central journal entries.
    Statements summarize credit card activity periods.
    """
    if not statements:
        print("No statements provided for transformation.")
        return pd.DataFrame()

    print(f"--- Transforming {len(statements)} statements ---")
    
    journal_lines = []
    line_no_base = 1000
    bc_cfg = cfg['business_central']
    
    for index, statement in enumerate(statements):
        # Statements might contain summary information
        # This is a placeholder - actual implementation depends on statement structure
        total_amount_obj = statement.get('total_amount', {})
        if isinstance(total_amount_obj, dict):
            minor_amount = total_amount_obj.get('amount', 0)
            conversion_rate = total_amount_obj.get('minor_unit_conversion_rate', 100)
            total_amount = minor_amount / conversion_rate
        else:
            # Fallback if amount is already a number
            total_amount = float(total_amount_obj) if total_amount_obj else 0.0
            
        statement_date = statement.get('statement_date', '')
        posting_date = statement_date[:10] if statement_date else datetime.now().strftime('%Y-%m-%d')
        
        doc_no = f"STMT-{statement.get('id', index)}"
        description = f"Credit card statement - {statement.get('card', {}).get('last_four', 'XXXX')}"
        
        # Statement summary (if needed for reconciliation)
        # This might be more of an informational entry
        journal_lines.append({
            'Journal Template Name': bc_cfg.get('template_name', 'GENERAL'),
            'Journal Batch Name': bc_cfg.get('batch_name', 'RAMP_STMTS'),
            'Line No.': line_no_base,
            'Posting Date': posting_date,
            'Document Type': '',
            'Document No.': doc_no,
            'Account Type': 'G/L Account',
            'Account No.': bc_cfg.get('ramp_card_account', '26100'),
            'Description': description,
            'Debit Amount': 0.0,
            'Credit Amount': round(total_amount, 2),
            'Bal. Account Type': '',
            'Bal. Account No.': '',
            'Department Code': '',
            'Activity Code': '',
        })
        line_no_base += 1000

    df_output = pd.DataFrame(journal_lines)
    if df_output.empty:
        return pd.DataFrame(columns=BC_COLUMN_ORDER)
    return df_output[BC_COLUMN_ORDER]