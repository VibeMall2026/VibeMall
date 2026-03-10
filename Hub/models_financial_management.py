"""
Financial Management Models - Phase 6
Features: P&L Statements, GST Reports, Payment Reconciliation, Expense Tracking, Vendor Payments, Tax Automation
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class ProfitLossStatement(models.Model):
    """Profit & Loss statement generation"""
    PERIOD_TYPE_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
        ('CUSTOM', 'Custom Period'),
    ]
    
    statement_id = models.CharField(max_length=50, unique=True)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES)
    
    # Period details
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Revenue
    gross_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    returns_refunds = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discounts_given = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Cost of Goods Sold (COGS)
    opening_inventory = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    purchases = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_inventory = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cogs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Gross Profit
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Operating Expenses
    marketing_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_gateway_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    staff_salaries = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    office_rent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    utilities = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_operating_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Net Profit
    operating_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_income = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    interest_expense = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_expense = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Additional metrics
    total_orders = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    customer_acquisition_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Status
    is_finalized = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_date']
        unique_together = ['period_type', 'start_date', 'end_date']
    
    def __str__(self):
        return f"P&L {self.statement_id} - {self.start_date} to {self.end_date}"


class GSTReport(models.Model):
    """GST reports (GSTR-1, GSTR-3B ready)"""
    REPORT_TYPE_CHOICES = [
        ('GSTR1', 'GSTR-1 (Outward Supplies)'),
        ('GSTR3B', 'GSTR-3B (Summary Return)'),
        ('GSTR2A', 'GSTR-2A (Auto-populated)'),
        ('GSTR9', 'GSTR-9 (Annual Return)'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('GENERATED', 'Generated'),
        ('FILED', 'Filed'),
        ('REVISED', 'Revised'),
    ]
    
    report_type = models.CharField(max_length=10, choices=REPORT_TYPE_CHOICES)
    financial_year = models.CharField(max_length=10, help_text="e.g., 2023-24")
    month = models.PositiveIntegerField(help_text="Month (1-12)")
    
    # Report identification
    gstin = models.CharField(max_length=15, help_text="GSTIN of the business")
    report_id = models.CharField(max_length=50, unique=True)
    
    # Tax summary
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cess_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Input tax credit (for GSTR-3B)
    itc_claimed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    itc_reversed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_itc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Tax liability
    tax_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_penalty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Report data
    report_data = models.JSONField(default=dict, help_text="Detailed GST report data")
    
    # Status and filing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    filing_date = models.DateField(null=True, blank=True)
    acknowledgment_number = models.CharField(max_length=50, blank=True)
    
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-financial_year', '-month']
        unique_together = ['report_type', 'financial_year', 'month']
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.financial_year} Month {self.month}"


class PaymentGatewayReconciliation(models.Model):
    """Payment gateway reconciliation"""
    GATEWAY_CHOICES = [
        ('RAZORPAY', 'Razorpay'),
        ('PAYU', 'PayU'),
        ('CASHFREE', 'Cashfree'),
        ('INSTAMOJO', 'Instamojo'),
        ('PHONEPE', 'PhonePe'),
        ('PAYTM', 'Paytm'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('MATCHED', 'Matched'),
        ('MISMATCHED', 'Mismatched'),
        ('DISPUTED', 'Disputed'),
        ('RESOLVED', 'Resolved'),
    ]
    
    reconciliation_id = models.CharField(max_length=50, unique=True)
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    
    # Reconciliation period
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Summary
    total_transactions = models.PositiveIntegerField(default=0)
    matched_transactions = models.PositiveIntegerField(default=0)
    mismatched_transactions = models.PositiveIntegerField(default=0)
    
    # Financial summary
    gateway_total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    system_total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    difference_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Gateway fees
    gateway_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_on_fees = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    net_settlement = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Files
    gateway_report_file = models.FileField(upload_to='reconciliation_reports/', null=True, blank=True)
    reconciliation_report = models.FileField(upload_to='reconciliation_reports/', null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def match_percentage(self):
        if self.total_transactions > 0:
            return (self.matched_transactions / self.total_transactions) * 100
        return 0
    
    def __str__(self):
        return f"{self.gateway} Reconciliation - {self.start_date} to {self.end_date}"


class ReconciliationTransaction(models.Model):
    """Individual transaction in reconciliation"""
    reconciliation = models.ForeignKey(PaymentGatewayReconciliation, on_delete=models.CASCADE, related_name='transactions')
    
    # Transaction details
    gateway_transaction_id = models.CharField(max_length=100)
    system_order_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Amounts
    gateway_amount = models.DecimalField(max_digits=10, decimal_places=2)
    system_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Dates
    gateway_date = models.DateTimeField()
    system_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_matched = models.BooleanField(default=False)
    mismatch_reason = models.CharField(max_length=200, blank=True)
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-gateway_date']
    
    def __str__(self):
        return f"Transaction {self.gateway_transaction_id} - {'Matched' if self.is_matched else 'Mismatched'}"


class ExpenseCategory(models.Model):
    """Expense categories for tracking"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Category settings
    is_active = models.BooleanField(default=True)
    is_tax_deductible = models.BooleanField(default=True)
    gst_applicable = models.BooleanField(default=True)
    
    # Budgeting
    monthly_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    yearly_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Expense Categories"
    
    def __str__(self):
        return self.name


class ExpenseRecord(models.Model):
    """Individual expense records"""
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CREDIT_CARD', 'Credit Card'),
        ('DEBIT_CARD', 'Debit Card'),
        ('UPI', 'UPI'),
        ('CHEQUE', 'Cheque'),
        ('OTHER', 'Other'),
    ]
    
    expense_id = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='expenses')
    
    # Expense details
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField()
    
    # Vendor/Supplier
    vendor_name = models.CharField(max_length=100, blank=True)
    vendor_gstin = models.CharField(max_length=15, blank=True)
    
    # Payment details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference_number = models.CharField(max_length=100, blank=True, help_text="Transaction/Cheque/Reference number")
    
    # Tax details
    is_gst_applicable = models.BooleanField(default=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    gst_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Documents
    invoice_number = models.CharField(max_length=50, blank=True)
    invoice_file = models.FileField(upload_to='expense_invoices/', null=True, blank=True)
    receipt_file = models.FileField(upload_to='expense_receipts/', null=True, blank=True)
    
    # Approval workflow
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-expense_date']
        indexes = [
            models.Index(fields=['expense_date']),
            models.Index(fields=['category', '-expense_date']),
        ]
    
    def save(self, *args, **kwargs):
        if self.is_gst_applicable:
            self.gst_amount = (self.amount * self.gst_rate) / 100
            self.total_amount = self.amount + self.gst_amount
        else:
            self.gst_amount = 0
            self.total_amount = self.amount
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.expense_id} - {self.description} (₹{self.total_amount})"


class VendorPayment(models.Model):
    """Vendor payment management"""
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('PURCHASE_ORDER', 'Purchase Order Payment'),
        ('SERVICE_PAYMENT', 'Service Payment'),
        ('ADVANCE_PAYMENT', 'Advance Payment'),
        ('EXPENSE_REIMBURSEMENT', 'Expense Reimbursement'),
        ('OTHER', 'Other'),
    ]
    
    payment_id = models.CharField(max_length=50, unique=True)
    vendor_name = models.CharField(max_length=100)
    vendor_gstin = models.CharField(max_length=15, blank=True)
    
    # Payment details
    payment_type = models.CharField(max_length=30, choices=PAYMENT_TYPE_CHOICES)
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Tax calculations
    tds_applicable = models.BooleanField(default=False)
    tds_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tds_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_payable = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Bank details
    vendor_bank_account = models.CharField(max_length=50, blank=True)
    vendor_ifsc = models.CharField(max_length=11, blank=True)
    vendor_bank_name = models.CharField(max_length=100, blank=True)
    
    # Payment execution
    payment_method = models.CharField(max_length=20, choices=ExpenseRecord.PAYMENT_METHOD_CHOICES)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    
    # Status and approval
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_payments')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Related documents
    invoice_file = models.FileField(upload_to='vendor_invoices/', null=True, blank=True)
    payment_receipt = models.FileField(upload_to='payment_receipts/', null=True, blank=True)
    
    # Due date tracking
    due_date = models.DateField()
    is_overdue = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['vendor_name', '-created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if self.tds_applicable:
            self.tds_amount = (self.amount * self.tds_rate) / 100
            self.net_payable = self.amount - self.tds_amount
        else:
            self.tds_amount = 0
            self.net_payable = self.amount
        
        # Check if overdue
        if self.due_date < timezone.now().date() and self.status != 'PAID':
            self.is_overdue = True
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Payment {self.payment_id} - {self.vendor_name} (₹{self.net_payable})"


class TaxCalculation(models.Model):
    """Automated tax calculations"""
    TAX_TYPE_CHOICES = [
        ('GST', 'Goods and Services Tax'),
        ('TDS', 'Tax Deducted at Source'),
        ('INCOME_TAX', 'Income Tax'),
        ('PROFESSIONAL_TAX', 'Professional Tax'),
    ]
    
    calculation_id = models.CharField(max_length=50, unique=True)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES)
    
    # Calculation period
    financial_year = models.CharField(max_length=10)
    quarter = models.PositiveIntegerField(null=True, blank=True, help_text="Quarter (1-4)")
    month = models.PositiveIntegerField(null=True, blank=True, help_text="Month (1-12)")
    
    # Tax calculation
    taxable_amount = models.DecimalField(max_digits=15, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    calculated_tax = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Additional details
    exemptions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment tracking
    tax_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Calculation details
    calculation_data = models.JSONField(default=dict, help_text="Detailed calculation breakdown")
    
    calculated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-financial_year', '-quarter', '-month']
    
    def __str__(self):
        return f"{self.get_tax_type_display()} - {self.financial_year} (₹{self.final_tax_amount})"


class CommissionCalculation(models.Model):
    """Commission calculation for resellers/affiliates"""
    COMMISSION_TYPE_CHOICES = [
        ('RESELLER', 'Reseller Commission'),
        ('AFFILIATE', 'Affiliate Commission'),
        ('REFERRAL', 'Referral Commission'),
        ('SALES_TEAM', 'Sales Team Commission'),
    ]
    
    calculation_id = models.CharField(max_length=50, unique=True)
    commission_type = models.CharField(max_length=20, choices=COMMISSION_TYPE_CHOICES)
    
    # Beneficiary
    beneficiary = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commissions')
    
    # Calculation period
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Sales data
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    qualifying_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    
    # Commission calculation
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    base_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus_commission = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Deductions
    tds_deducted = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    net_payable = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Payment status
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    calculated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='calculated_commissions')
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def save(self, *args, **kwargs):
        self.base_commission = (self.qualifying_sales * self.commission_rate) / 100
        self.total_commission = self.base_commission + self.bonus_commission
        self.net_payable = self.total_commission - self.tds_deducted - self.other_deductions
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.beneficiary.username} - {self.get_commission_type_display()} (₹{self.net_payable})"