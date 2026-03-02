# VibeMall ITR Reports - Quick Start Guide

## 📍 Access the ITR Reports Generator

### Web URL
```
http://localhost:8000/admin-panel/backup/itr-reports/
```

### Requirements
- Admin login credentials
- Database with order data
- pandas 3.0.1 + openpyxl 3.1.5 installed

---

## 🎯 Generate Your First ITR Report

### Step 1: Navigate to ITR Reports Page
1. Login to admin panel
2. Go to Backup Management → ITR Reports
3. Or visit: `/admin-panel/backup/itr-reports/`

### Step 2: Select Report Type
- **Monthly**: Last 30 days
- **6-Month**: Last 180 days  
- **Yearly**: Last 365 days (FY: April 2024 - March 2025)
- **Custom**: Pick any date range

### Step 3: Generate Report
1. Click "Generate & Download Report"
2. Wait for report generation (30-60 seconds for large datasets)
3. File automatically downloads: `ITR_Report_{type}_{timestamp}.xlsx`

### Step 4: File Location
Report saved to: `D:\VibeMallBackUp\SpecialBackup\{YYYY-MM}\ITR_Report_{type}_{timestamp}.xlsx`

---

## 📊 Understanding the Report

### 9 Worksheets Included

| # | Sheet Name | Purpose |
|---|------------|---------|
| 1 | Cover Page | Filing info & disclaimer |
| 2 | Financial Summary | Revenue, GST, profit overview |
| 3 | Schedule - Business Income | Payment method breakdown |
| 4 | Monthly Breakdown | 12-month analysis |
| 5 | Detailed Orders | Individual transactions |
| 6 | Refunds & Adjustments | Return tracking |
| 7 | GST Calculation | Tax split (IGST/SGST/CGST) |
| 8 | Deductions | **User edits here** (15 categories) |
| 9 | Tax Computation | Final tax liability |

---

## ✏️ Customizing Your Report

### Edit Deductions (Sheet 8)
1. Open the "Deductions" worksheet
2. Enter actual values in the rightmost column:
   - Internet & Telecom
   - Office Rent
   - Salaries & Wages
   - Utilities
   - Office Supplies
   - Equipment Depreciation
   - Marketing & Advertising
   - Insurance
   - Professional Fees
   - Bank Charges
   - Travel Expenses
   - Warehouse Rent
   - Section 80C Investment (max ₹1,50,000)
   - Section 80D Insurance (max ₹25,000)
   - Section 80TTA Bank Interest (max ₹10,000)
3. Save file

### Adjust Cost of Goods Sold (COGS)
Default: 60% of net revenue

To change:
1. Edit `Hub/itr_utils.py` line 11
2. Change: `ASSUMED_COGS_PERCENTAGE = 60`
3. Regenerate report

### Update GST Rate
Default: 18%

To change:
1. Edit `Hub/itr_utils.py` line 10
2. Change: `GST_RATE = 18`
3. Regenerate report

---

## 💰 Key Figures in Your Report

### Financial Summary (Sheet 2)
```
Gross Revenue       : Sum of all orders
Less: Refunds       : Minus return amounts
Net Revenue         : Revised revenue
GST (18%)          : Tax liability
COGS (60%)         : Cost of goods
Profit             : Net - COGS
Profit Margin %    : Profit / Net Revenue
```

### Tax Computation (Sheet 9)
```
Taxable Income     = Profit - Deductions
Basic Exemption    = ₹3,00,000 (NO tax on this)
Taxable Amount     = Taxable Income - Exemption

Tax Rate Applied:
  0 to ₹5,00,000      → 5%
  ₹5,00,001-₹10,00,000 → 20%
  ₹10,00,001+         → 30%

Plus: Health & Education Cess = 4% on tax
Final Tax = Tax × 1.04
```

### GST Breakdown (Sheet 7)
```
Total GST Liability = Gross Revenue × 18%

For IGST (Interstate):
  IGST = 18%

For SGST + CGST (Intrastate):
  SGST = 9%
  CGST = 9%
```

---

## 🔍 Verification Checklist

Before submitting to CA:
- [ ] All order amounts appear in "Detailed Orders"
- [ ] Refund amounts deducted correctly
- [ ] Monthly totals match sales records
- [ ] GST calculation is 18% of gross revenue
- [ ] Deductions filled with actual expenses
- [ ] Tax computation uses correct slabs
- [ ] No negative values (alert CA if found)
- [ ] Report file opens in Excel without errors

---

## 🚨 Common Questions

### Q: Why is my profit different from QuickBooks?
**A:** This report calculates profit as Net Revenue minus COGS (60% default). Meet with CA to adjust COGS % or add manual deductions.

### Q: Can I change the tax slabs?
**A:** Tax slabs are fixed per Indian tax law for FY 2024-25. Don't modify unless law changes. Consult CA.

### Q: How often are backups created?
**A:** ITR reports are on-demand only. Regular backups (users, orders, etc.) run per configured schedule.

### Q: Where are files stored?
**A:** D:\VibeMallBackUp\SpecialBackup\{YYYY-MM}\ITR_Report_*.xlsx

### Q: Can I generate multiple reports?
**A:** Yes! Generate different date ranges, compare periods, analyze trends.

### Q: What if there's a calculation error?
**A:** Enable Django debug mode and check error message. Share error with CA.

### Q: Do I need internet for ITR reports?
**A:** No, all data is local. No cloud connection needed.

### Q: Can I automate ITR generation?
**A:** Currently manual. Future version will support scheduled generation + email delivery.

### Q: Is this file acceptable for tax filing?
**A:** Yes, but ALWAYS have CA review before official ITR-3 submission. This is a tool, not a substitute for professional advice.

---

## 🔐 Security Notes

- Only admin users can access ITR reports
- Reports contain sensitive financial data
- Store in secure location
- Don't share files via email
- Delete test files after verification
- Keep backups for 5+ years (Indian law)

---

## 📞 Support Resources

| Issue | Solution |
|-------|----------|
| Excel won't open | Reinstall openpyxl: `pip install openpyxl==3.1.5` |
| Report very large | Long date ranges = more data. Use shorter ranges. |
| Numbers look wrong | Check COGS %, Deduction amounts, date range |
| Report won't download | Check browser pop-up blocker, try different browser |
| Admin access denied | Ensure logged in with admin privileges |
| Django error page | Check server logs: `tail -f logs/debug.log` |

---

## 📋 Report Naming Convention

```
ITR_Report_{type}_{timestamp}.xlsx

Example:
ITR_Report_monthly_20260302_094713.xlsx
           └────┬────┘ └──┬─┘
              type    date+time

Types: monthly, six_month, yearly, custom
```

---

## 🎓 For Your Chartered Accountant

**Provide This Info With Report:**
- Report type (Monthly/6-Month/Yearly/Custom)
- Date range covered
- Business classification (Reselling/E-commerce)
- COGS percentage used (default: 60%)
- Any manual adjustments made

**Report Contents for CA Review:**
1. Gross revenue vs invoice records
2. Refund processing accuracy
3. GST calculation (18% on gross)
4. Deduction legitimacy & documentation
5. Advance tax payment schedule
6. ITR filing requirements
7. Estimated tax liability

---

## 🎯 Next Steps

1. ✅ Generate test report
2. ✅ Review all 9 worksheets
3. ✅ Verify calculations with records
4. ✅ Fill deduction amounts
5. ✅ Send to CA for review
6. ✅ Make CA-suggested corrections
7. ✅ File official ITR-3 before deadline
8. ✅ Archive report for 5+ years

---

**Report Generated:** 2026-03-02  
**System:** VibeMall v2.0  
**Status:** ✅ Ready for Use

### Questions? Contact CA or see ITR_IMPLEMENTATION_COMPLETE.md
