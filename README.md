# Ramp to Business Central Integration

This application integrates Ramp financial data with Microsoft Business Central by fetching various types of transactions and converting them into Business Central General Journal entries.

## Features

- **Card Transactions**: Credit card charges with G/L account coding
- **Bills**: Vendor bills/invoices
- **Reimbursements**: Employee expense reimbursements
- **Cashbacks**: Credit card reward programs
- **Statements**: Credit card statement summaries

## Prerequisites

- Python 3.8+
- Ramp API credentials (Client ID & Secret)
- Business Central configured with appropriate G/L accounts

## Installation

1. Clone or download the project files
2. Install dependencies:
   ```bash
   pip install requests python-dotenv tomllib openpyxl pandas
   ```

3. Create a `.env` file with your Ramp credentials:
   ```
   RAMP_CLIENT_ID=your_client_id_here
   RAMP_CLIENT_SECRET=your_client_secret_here
   ```

4. Update `config.toml` with your Business Central G/L account numbers

## Configuration

### config.toml

Update the following G/L account numbers to match your Business Central setup:

```toml
[business_central]
ramp_card_account = "26100"          # Credit card liability account
bank_account = "11005"               # Bank account for payments
vendor_payable_account = "20000"     # Vendor payable suspense
employee_receivable_account = "13000" # Employee receivables
other_income_account = "40000"       # Other income (cashbacks)
```

## Usage

### Command Line Options

```bash
# Single data type with manual dates
python main.py --type [TYPE] --start YYYY-MM-DD --end YYYY-MM-DD

# All data types with automatic reconciliation periods
python main.py --all --period [PERIOD]
```

### Data Types

- `transactions` (default): Credit card transactions
- `bills`: Vendor bills/invoices
- `reimbursements`: Employee reimbursements
- `cashbacks`: Credit card rewards
- `statements`: Statement summaries

### Reconciliation Periods

- `monthly` (default): All types use current month dates
- `bi-weekly`: Bills use last 2 weeks, others use current month
- `statement`: Transactions use statement period, others use current month

### Examples

#### Single Type Processing
```bash
# Export card transactions for current period
python main.py

# Export bills for specific date range
python main.py --type bills --start 2025-01-01 --end 2025-01-31

# Export reimbursements
python main.py --type reimbursements
```

#### Multi-Type Processing (Recommended Workflow)

```bash
# Monthly reconciliation (recommended for most organizations)
python main.py --all --period monthly

# Bi-weekly A/P processing (bills every 2 weeks, others monthly)
python main.py --all --period bi-weekly

# Statement reconciliation (transactions by statement period)
python main.py --all --period statement
```

#### Sync Status Management (Future Feature)

```bash
# Export and mark transactions as synced (requires accounting:write scope)
python main.py --all --period monthly --mark-synced

# Check sync status for specific transactions
# (This functionality will be available when accounting scopes are granted)
```

### Recommended Reconciliation Schedule

Based on your requirements:

1. **Monthly Reconciliation** (recommended):
   ```bash
   python main.py --all --period monthly
   ```
   - Transactions: Current month
   - Bills: Current month
   - Reimbursements: Current month
   - Cashbacks: Current month

2. **Bi-weekly A/P Processing**:
   ```bash
   python main.py --all --period bi-weekly
   ```
   - Bills: Last 2 weeks (for bi-weekly invoice processing)
   - Other types: Current month

3. **Statement-Based Reconciliation**:
   ```bash
   python main.py --all --period statement
   ```
   - Transactions: Statement period dates
   - Other types: Current month

## Workflow Benefits

### Single Export File
- All data types combined into one Business Central journal import file
- Eliminates manual consolidation of multiple exports
- Reduces import steps and potential errors

### Automated Date Ranges
- No need to manually calculate date ranges for different reconciliation frequencies
- Consistent processing based on your organization's schedule
- Reduces human error in date selection

### Smart Endpoint Detection
- Automatically detects which Ramp API endpoints are available based on your OAuth scopes
- Only processes data types you have access to
- Gracefully handles scope limitations without errors

### Error Resilience
- Continues processing other data types if one type fails
- Provides clear feedback on which types succeeded/failed
- Allows partial processing when some APIs are unavailable

### Audit Trail
- Timestamped export files show when data was processed
- Combined files include all transaction types for complete audit visibility
- Sync status tracking prevents duplicate processing (when accounting scopes are available)

## Output

Exports are saved to the `exports/` directory as:
- **CSV**: For Business Central import
- **Excel**: For review and validation

## Accounting Logic

### Card Transactions
- **Debit**: Expense G/L Account
- **Credit**: Credit Card Liability Account (26100)

### Bills
- **Debit**: (Expense account via balancing)
- **Credit**: Vendor Payable Account (20000)

### Reimbursements
- **Debit**: Bank Account (11005)
- **Credit**: Employee Receivable Account (13000)

### Cashbacks
- **Debit**: Other Income Account (40000)
- **Credit**: Bank Account (11005)

## Business Central Import

1. Open Business Central General Journal
2. Import the CSV file
3. Review and post the entries

## API Reference

- [Ramp Accounting API](https://docs.ramp.com/developer-api/v1/accounting)
- [Bills API](https://docs.ramp.com/developer-api/v1/api/bills)
- [Reimbursements API](https://docs.ramp.com/developer-api/v1/api/reimbursements)
- [Cashbacks API](https://docs.ramp.com/developer-api/v1/api/cashbacks)
- [Statements API](https://docs.ramp.com/developer-api/v1/api/statements)

## Sync Status Management

### Overview
The application includes future support for marking transactions as synced to Business Central to prevent duplicate processing.

### Requirements
- `accounting:write` OAuth scope (contact Ramp support to enable)
- `accounting:read` OAuth scope for status checking

### Usage
```bash
# Export data and mark transactions as synced
python main.py --all --period monthly --mark-synced
```

### Benefits
- Prevents duplicate journal entries in Business Central
- Tracks which transactions have been processed
- Enables incremental sync processes
- Provides audit trail of sync operations

### Current Status
- Code is implemented and ready
- Requires `accounting:read` and `accounting:write` scopes to be granted by Ramp
- Will automatically detect when scopes become available