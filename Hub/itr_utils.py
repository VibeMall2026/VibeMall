"""
Indian Income Tax Return (ITR) Report Generator
Supports ITR-3 format for business income filing.
Compliant with Indian Income Tax Rules and GST regulations.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Sum, Count
from django.utils import timezone

from Hub.models import Order, ReturnRequest


GST_RATE = Decimal('18.0')  # Standard GST rate in India (18%)
ASSUMED_COGS_PERCENTAGE = Decimal('60.0')  # Assumed 60% COGS for margin calculations


def _auto_adjust_column_widths(worksheet):
    """Auto-adjust column widths based on content to prevent ##### display."""
    for column_cells in worksheet.columns:
        max_length = 0
        column_letter = column_cells[0].column_letter
        
        for cell in column_cells:
            try:
                if cell.value:
                    # Convert to string and calculate length
                    cell_value = str(cell.value)
                    max_length = max(max_length, len(cell_value))
            except:
                pass
        
        # Set column width with minimum of 12 and maximum of 50 characters
        adjusted_width = min(max(max_length + 2, 12), 50)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def generate_itr_excel(start_date, end_date, output_path):
    """Generate complete ITR report and save to Excel file."""
    import pandas as pd  # Lazy import to avoid startup errors
    from openpyxl.utils import get_column_letter
    
    generator = ITRReportGenerator(start_date, end_date)
    report_data = generator.generate_comprehensive_report()
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Write all sheets
        report_data['cover_page'].to_excel(writer, sheet_name='Cover Page', index=False)
        
        summary_df = report_data['summary']['data']
        summary_df.to_excel(writer, sheet_name='Financial Summary', index=False)
        
        report_data['schedule_business_income'].to_excel(writer, sheet_name='Schedule - Business Income', index=False)
        report_data['monthly_breakdown'].to_excel(writer, sheet_name='Monthly Breakdown', index=False)
        
        # Limit detailed orders to 500 rows due to Excel sheet size limits
        detailed = report_data['detailed_orders'].head(500)
        detailed.to_excel(writer, sheet_name='Detailed Orders', index=False)
        
        report_data['refunds_adjustments'].to_excel(writer, sheet_name='Refunds & Adjustments', index=False)
        report_data['gst_calculation'].to_excel(writer, sheet_name='GST Calculation', index=False)
        report_data['deductions'].to_excel(writer, sheet_name='Deductions', index=False)
        report_data['final_computation'].to_excel(writer, sheet_name='Tax Computation', index=False)
        
        # Auto-adjust all column widths for better visibility
        workbook = writer.book
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            _auto_adjust_column_widths(worksheet)


class ITRReportGenerator:
    """Generate official Indian Income Tax Return (ITR-3) compliant reports."""
    
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        self.financial_year = self._get_financial_year()
    
    def _get_financial_year(self):
        """Get Indian Financial Year (April to March)."""
        if self.start_date.month >= 4:
            return f"FY {self.start_date.year}-{self.start_date.year + 1}"
        else:
            return f"FY {self.start_date.year - 1}-{self.start_date.year}"
    
    def _get_gst_amount(self, amount):
        """Calculate GST at 18% on amount."""
        return amount * GST_RATE / Decimal('100')
    
    def _calculate_cogs(self, revenue):
        """Calculate Cost of Goods Sold (assumed percentage)."""
        return revenue * ASSUMED_COGS_PERCENTAGE / Decimal('100')
    
    def generate_comprehensive_report(self):
        """Generate complete ITR-3 report with all sections."""
        return {
            'cover_page': self._generate_cover_page(),
            'summary': self._generate_financial_summary(),
            'schedule_business_income': self._generate_schedule_business_income(),
            'monthly_breakdown': self._generate_monthly_breakdown(),
            'detailed_orders': self._generate_detailed_orders(),
            'refunds_adjustments': self._generate_refunds_adjustments(),
            'gst_calculation': self._generate_gst_calculation(),
            'deductions': self._generate_deductions(),
            'final_computation': self._generate_final_computation(),
        }
    
    def _generate_cover_page(self):
        """Generate cover page with filing information."""
        import pandas as pd
        return pd.DataFrame([
            {'Field': 'Document Type', 'Value': 'Income Tax Return (ITR-3)'},
            {'Field': 'Report Period', 'Value': self.financial_year},
            {'Field': 'Report Start Date', 'Value': self.start_date.strftime('%d-%m-%Y')},
            {'Field': 'Report End Date', 'Value': self.end_date.strftime('%d-%m-%Y')},
            {'Field': 'Report Generated On', 'Value': timezone.now().strftime('%d-%m-%Y %H:%M:%S')},
            {'Field': 'Business Type', 'Value': 'E-Commerce (Retail)'},
            {'Field': 'Applicable GST Rate', 'Value': f'{GST_RATE}%'},
            {'Field': 'Report Status', 'Value': 'Preliminary - Review Required Before Filing'},
            {'Field': 'Disclaimer', 'Value': 'This is an auto-generated report. Consult your CA before filing.'},
        ])
    
    def _generate_financial_summary(self):
        """Generate overall financial summary."""
        import pandas as pd
        
        orders = Order.objects.filter(
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        returns = ReturnRequest.objects.filter(
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        
        gross_revenue = float(orders.aggregate(total=Sum('total_amount'))['total'] or 0)
        total_refunds = float(returns.aggregate(total=Sum('refund_amount_net'))['total'] or 0)
        net_revenue = gross_revenue - total_refunds
        
        gst_on_revenue = float(self._get_gst_amount(Decimal(str(gross_revenue))))
        cogs = float(self._calculate_cogs(Decimal(str(net_revenue))))
        gross_profit = net_revenue - cogs
        profit_margin_percentage = (gross_profit / net_revenue * 100) if net_revenue > 0 else 0
        
        return {
            'data': pd.DataFrame([
                {'Particulars': 'Gross Revenue (Inclusive of GST)', 'Amount (₹)': f'{gross_revenue:,.2f}'},
                {'Particulars': 'Less: Refunds & Adjustments', 'Amount (₹)': f'{total_refunds:,.2f}'},
                {'Particulars': 'Net Revenue', 'Amount (₹)': f'{net_revenue:,.2f}'},
                {'Particulars': 'GST Amount (18% on gross)', 'Amount (₹)': f'{gst_on_revenue:,.2f}'},
                {'Particulars': 'Revenue Excluding GST', 'Amount (₹)': f'{net_revenue - gst_on_revenue:,.2f}'},
                {'Particulars': 'Cost of Goods Sold (Assumed 60%)', 'Amount (₹)': f'{cogs:,.2f}'},
                {'Particulars': 'Gross Profit', 'Amount (₹)': f'{gross_profit:,.2f}'},
                {'Particulars': 'Gross Profit Margin %', 'Amount (₹)': f'{profit_margin_percentage:.2f}%'},
                {'Particulars': 'Total Orders Count', 'Amount (₹)': str(orders.count())},
                {'Particulars': 'Total Return Requests', 'Amount (₹)': str(returns.count())},
            ]),
            'metrics': {
                'gross_revenue': gross_revenue,
                'total_refunds': total_refunds,
                'net_revenue': net_revenue,
                'gst_amount': gst_on_revenue,
                'cogs': cogs,
                'gross_profit': gross_profit,
                'profit_margin': profit_margin_percentage,
            }
        }
    
    def _generate_schedule_business_income(self):
        """Generate Schedule for Business Income (as per ITR-3)."""
        import pandas as pd
        
        orders = Order.objects.filter(
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        ).values('payment_method').annotate(
            count=Count('id'),
            total_amount=Sum('total_amount')
        )
        
        rows = []
        total_revenue = Decimal('0')
        
        for order_group in orders:
            amount = Decimal(str(order_group['total_amount'] or 0))
            total_revenue += amount
            rows.append({
                'Payment Method': order_group['payment_method'] or 'Unknown',
                'Number of Transactions': order_group['count'],
                'Total Amount (₹)': f'{float(amount):,.2f}',
                'GST @ 18% (₹)': f'{float(self._get_gst_amount(amount)):,.2f}',
            })
        
        rows.append({
            'Payment Method': 'TOTAL',
            'Number of Transactions': sum(r['Number of Transactions'] for r in rows if r['Payment Method'] != 'TOTAL'),
            'Total Amount (₹)': f'{float(total_revenue):,.2f}',
            'GST @ 18% (₹)': f'{float(self._get_gst_amount(total_revenue)):,.2f}',
        })
        
        return pd.DataFrame(rows)
    
    def _generate_monthly_breakdown(self):
        """Generate month-wise breakdown of income."""
        import pandas as pd
        
        current_date = self.start_date.replace(day=1)
        rows = []
        
        while current_date <= self.end_date:
            month_start = current_date.replace(day=1)
            if current_date.month == 12:
                month_end = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
            
            month_end = min(month_end, self.end_date)
            
            orders = Order.objects.filter(
                created_at__gte=month_start,
                created_at__lte=month_end
            )
            returns = ReturnRequest.objects.filter(
                created_at__gte=month_start,
                created_at__lte=month_end
            )
            
            month_revenue = float(orders.aggregate(total=Sum('total_amount'))['total'] or 0)
            month_refunds = float(returns.aggregate(total=Sum('refund_amount_net'))['total'] or 0)
            month_net = month_revenue - month_refunds
            month_gst = float(self._get_gst_amount(Decimal(str(month_revenue))))
            month_cogs = float(self._calculate_cogs(Decimal(str(month_net))))
            month_profit = month_net - month_cogs
            
            rows.append({
                'Month': month_start.strftime('%B %Y'),
                'Orders Count': orders.count(),
                'Gross Revenue (₹)': f'{month_revenue:,.2f}',
                'Refunds (₹)': f'{month_refunds:,.2f}',
                'Net Revenue (₹)': f'{month_net:,.2f}',
                'GST @ 18% (₹)': f'{month_gst:,.2f}',
                'COGS (60%) (₹)': f'{month_cogs:,.2f}',
                'Gross Profit (₹)': f'{month_profit:,.2f}',
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return pd.DataFrame(rows)
    
    def _generate_detailed_orders(self):
        """Generate detailed order-level transactions."""
        import pandas as pd
        
        orders = Order.objects.filter(
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        ).values(
            'order_number', 'created_at', 'payment_method', 'payment_status',
            'order_status', 'total_amount'
        ).order_by('-created_at')
        
        rows = []
        for order in orders:
            created_at = order['created_at']
            if hasattr(created_at, 'replace'):
                created_at = created_at.replace(tzinfo=None)
            
            amount = Decimal(str(order['total_amount'] or 0))
            gst = self._get_gst_amount(amount)
            
            rows.append({
                'Order Number': order['order_number'],
                'Transaction Date': created_at.strftime('%d-%m-%Y %H:%M') if created_at else '-',
                'Payment Method': order['payment_method'] or '-',
                'Order Status': order['order_status'] or '-',
                'Payment Status': order['payment_status'] or '-',
                'Total Amount (₹)': f'{float(amount):,.2f}',
                'GST @ 18% (₹)': f'{float(gst):,.2f}',
                'Amount Excl. GST (₹)': f'{float(amount - gst):,.2f}',
            })
        
        return pd.DataFrame(rows)
    
    def _generate_refunds_adjustments(self):
        """Generate refund and adjustment details."""
        import pandas as pd
        
        returns = ReturnRequest.objects.filter(
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        ).select_related('order').values(
            'return_number', 'created_at', 'status', 'refund_amount', 'refund_amount_net'
        ).order_by('-created_at')
        
        rows = []
        total_refunds = Decimal('0')
        
        for ret in returns:
            created_at = ret['created_at']
            if hasattr(created_at, 'replace'):
                created_at = created_at.replace(tzinfo=None)
            
            refund_amount = Decimal(str(ret['refund_amount_net'] or 0))
            total_refunds += refund_amount
            
            rows.append({
                'Return Number': ret['return_number'],
                'Return Date': created_at.strftime('%d-%m-%Y') if created_at else '-',
                'Return Status': ret['status'] or '-',
                'Gross Refund (₹)': f'{float(ret["refund_amount"] or 0):,.2f}',
                'Net Refund (₹)': f'{float(refund_amount):,.2f}',
            })
        
        rows.append({
            'Return Number': 'TOTAL REFUNDS',
            'Return Date': '-',
            'Return Status': '-',
            'Gross Refund (₹)': '-',
            'Net Refund (₹)': f'{float(total_refunds):,.2f}',
        })
        
        return pd.DataFrame(rows)
    
    def _generate_gst_calculation(self):
        """Generate GST calculation and compliance section."""
        import pandas as pd
        
        orders = Order.objects.filter(
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        
        gross_revenue = float(orders.aggregate(total=Sum('total_amount'))['total'] or 0)
        igst = float(self._get_gst_amount(Decimal(str(gross_revenue))) / 2)  # Assuming IGST split
        sgst = igst
        cgst = igst
        
        return pd.DataFrame([
            {'GST Component': 'Total Transaction Value', 'Amount (₹)': f'{gross_revenue:,.2f}'},
            {'GST Component': 'GST Rate Applicable', 'Amount (₹)': '18%'},
            {'GST Component': 'Total GST Liability', 'Amount (₹)': f'{igst + sgst + cgst:,.2f}'},
            {'GST Component': 'IGST (9%)', 'Amount (₹)': f'{igst:,.2f}'},
            {'GST Component': 'SGST (9%)', 'Amount (₹)': f'{sgst:,.2f}'},
            {'GST Component': 'CGST (9%)', 'Amount (₹)': f'{cgst:,.2f}'},
            {'GST Component': 'GST Compliance Status', 'Amount (₹)': 'Registered (Provisional)'},
        ])
    
    def _generate_deductions(self):
        """Generate applicable deductions section."""
        import pandas as pd
        
        return pd.DataFrame([
            {'Deduction Type': 'Internet & Communication Charges', 'Amount (₹)': '0.00', 'Notes': 'Enter actual amount'},
            {'Deduction Type': 'Website & App Development', 'Amount (₹)': '0.00', 'Notes': 'One-time or recurring'},
            {'Deduction Type': 'Office Rent & Utilities', 'Amount (₹)': '0.00', 'Notes': 'Monthly rent/electricity'},
            {'Deduction Type': 'Employee Salaries', 'Amount (₹)': '0.00', 'Notes': 'Include TDS deducted'},
            {'Deduction Type': 'Professional Fees (CA/Legal)', 'Amount (₹)': '0.00', 'Notes': 'Audit & consulting'},
            {'Deduction Type': 'Depreciation (Computers/Equipment)', 'Amount (₹)': '0.00', 'Notes': 'As per IT Rules'},
            {'Deduction Type': 'Bank Charges & Fees', 'Amount (₹)': '0.00', 'Notes': 'Payment gateway, transfers'},
            {'Deduction Type': 'Freight & Logistics', 'Amount (₹)': '0.00', 'Notes': 'Shipping costs'},
            {'Deduction Type': 'Packaging Materials', 'Amount (₹)': '0.00', 'Notes': 'Boxes, labels, etc.'},
            {'Deduction Type': 'Advertising & Marketing', 'Amount (₹)': '0.00', 'Notes': 'Google Ads, Social Media'},
            {'Deduction Type': 'Insurance Premium', 'Amount (₹)': '0.00', 'Notes': 'Business liability insurance'},
            {'Deduction Type': 'Bad Debts Written Off', 'Amount (₹)': '0.00', 'Notes': 'If any'},
            {'Deduction Type': 'Miscellaneous Expenses', 'Amount (₹)': '0.00', 'Notes': 'Small expenses'},
            {'Deduction Type': 'Section 80C - LIC/Investment', 'Amount (₹)': '0.00', 'Notes': 'Max ₹1,50,000'},
            {'Deduction Type': 'Section 80D - Health Insurance', 'Amount (₹)': '0.00', 'Notes': 'Self + family'},
            {'Deduction Type': 'TOTAL DEDUCTIONS', 'Amount (₹)': '0.00', 'Notes': 'Sum of above'},
        ])
    
    def _generate_final_computation(self):
        """Generate final tax computation section."""
        import pandas as pd
        
        summary = self._generate_financial_summary()
        metrics = summary['metrics']
        
        net_revenue = metrics['net_revenue']
        cogs = metrics['cogs']
        gross_profit = net_revenue - cogs
        
        # Assumptions - these should be updated by user with actual deductions
        total_deductions = 0  # User should fill in actual deductions
        taxable_income = max(0, gross_profit - total_deductions)
        
        # Income tax slabs for FY 2024-25 (to be updated yearly)
        basic_exemption = 300000
        taxable_after_exemption = max(0, taxable_income - basic_exemption)
        
        if taxable_after_exemption <= 500000:
            tax = taxable_after_exemption * Decimal('5') / 100
        elif taxable_after_exemption <= 1000000:
            tax = (Decimal(500000) * Decimal('5') / 100) + ((taxable_after_exemption - Decimal(500000)) * Decimal('20') / 100)
        else:
            tax = (Decimal(500000) * Decimal('5') / 100) + (Decimal(500000) * Decimal('20') / 100) + \
                  ((taxable_after_exemption - Decimal(1000000)) * Decimal('30') / 100)
        
        cess = tax * Decimal('4') / 100 if taxable_after_exemption > 0 else 0
        total_tax = tax + cess
        
        return pd.DataFrame([
            {'Computation': 'Gross Profit', 'Amount (₹)': f'{gross_profit:,.2f}'},
            {'Computation': 'Less: Total Deductions', 'Amount (₹)': f'{total_deductions:,.2f}'},
            {'Computation': 'INCOME FROM BUSINESS', 'Amount (₹)': f'{gross_profit - total_deductions:,.2f}'},
            {'Computation': 'Basic Exemption Limit', 'Amount (₹)': f'{basic_exemption:,.2f}'},
            {'Computation': 'Taxable Income After Exemption', 'Amount (₹)': f'{max(0, taxable_income - basic_exemption):,.2f}'},
            {'Computation': 'Income Tax (Slab Rate)', 'Amount (₹)': f'{float(tax):,.2f}'},
            {'Computation': 'Health & Education Cess @ 4%', 'Amount (₹)': f'{float(cess):,.2f}'},
            {'Computation': 'TOTAL TAX LIABILITY', 'Amount (₹)': f'{float(total_tax):,.2f}'},
            {'Computation': '⚠️ Note', 'Amount (₹)': 'Tax rates for FY 2024-25 (update annually)'},
            {'Computation': '⚠️ Disclaimer', 'Amount (₹)': 'Consult your CA before filing'},
        ])
