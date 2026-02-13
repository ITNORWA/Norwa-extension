# Copyright (c) 2026, Norwa and contributors
# For license information, please see license.txt

"""
Norwa Departmental Budget control for:
- Purchase Order / Purchase Invoice (when applicable on PO/PI flags are set)
- Booking actual expenses (Expense Claim on_submit: when Applicable on booking actual expenses /
  Monthly Applicable on booking actual expenses are set).
Uses the Department accounting dimension throughout.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_last_day
from erpnext.accounts.utils import get_fiscal_year

# Month field names in Budget Details child table
MONTH_FIELDS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def validate_norwa_departmental_budget(doc, event=None):
	"""Validate document against Norwa Departmental Budget. Uses Department accounting dimension."""
	if doc.docstatus != 1:
		return
	company = doc.get("company")
	if not company:
		return
	# Posting date: PO uses transaction_date, PI uses posting_date
	posting_date = doc.get("posting_date") or doc.get("transaction_date")
	if not posting_date:
		return
	fiscal_year = get_fiscal_year(posting_date, company=company)
	if not fiscal_year:
		return
	fiscal_year = fiscal_year[0]

	doctype = doc.doctype
	is_po = doctype == "Purchase Order"
	is_pi = doctype == "Purchase Invoice"
	if not (is_po or is_pi):
		return

	# Build (department, account) -> amount using Department accounting dimension (header or item level)
	dept_account_amounts = _get_doc_amounts_by_department_and_account(doc, is_pi)

	if not dept_account_amounts:
		return

	# Validate each (department, account) pair that has budget and applicable flags
	departments = {d for d, a in dept_account_amounts}
	for department in departments:
		account_amounts = {acc: dept_account_amounts[(department, acc)] for (d, acc) in dept_account_amounts if d == department}
		budgets = frappe.db.sql(
			"""
			SELECT name, applicable_on_purchase_order, applicable_on_purchase_invoice,
			       applicable_on_booking_actual_expenses, monthly_applicable_on_booking_actual_expenses,
			       monthly_applicable_on_purchase_order, monthly_applicable_on_purchase_invoice
			FROM `tabNorwa Departmental Budget`
			WHERE company = %(company)s AND fiscal_year = %(fiscal_year)s AND department = %(department)s
			  AND docstatus = 1
			""",
			{"company": company, "fiscal_year": fiscal_year, "department": department},
			as_dict=True,
		)
		if not budgets:
			continue
		for budget in budgets:
			check_yearly = (is_po and budget.applicable_on_purchase_order) or (
				is_pi and budget.applicable_on_purchase_invoice
			)
			check_monthly = (is_po and budget.monthly_applicable_on_purchase_order) or (
				is_pi and budget.monthly_applicable_on_purchase_invoice
			)
			if not check_yearly and not check_monthly:
				continue
			_validate_budget_accounts(
				doc=doc,
				budget_name=budget.name,
				company=company,
				fiscal_year=fiscal_year,
				department=department,
				posting_date=posting_date,
				account_amounts=account_amounts,
				doctype=doctype,
				check_yearly=check_yearly,
				check_monthly=check_monthly,
			)


def _get_doc_amounts_by_department_and_account(doc, is_purchase_invoice):
	"""
	Sum amount by (department, expense_account) using Department accounting dimension.
	Department can be on header (doc.department) or on each item (item.department); item level overrides.
	Returns dict (department, account) -> total_amount.
	"""
	dept_account_amounts = {}
	for item in doc.get("items") or []:
		acc = item.get("expense_account")
		if not acc:
			continue
		# Department accounting dimension: item level or fallback to header
		department = item.get("department") or doc.get("department")
		if not department:
			continue
		if is_purchase_invoice:
			amt = flt(item.get("base_net_amount") or item.get("amount"), 2)
		else:
			amt = flt(item.get("amount"), 2)
		key = (department, acc)
		dept_account_amounts[key] = dept_account_amounts.get(key, 0) + amt
	return dept_account_amounts


def _validate_budget_accounts(
	doc,
	budget_name,
	company,
	fiscal_year,
	department,
	posting_date,
	account_amounts,
	doctype,
	check_yearly,
	check_monthly,
):
	"""Load budget details and validate each account that has budget and appears in doc."""
	budget_details = frappe.db.sql(
		"""
		SELECT accounts,
		       (jan + feb + mar + apr + may + jun + jul + aug + sep + oct + nov + `dec`) AS yearly_budget,
		       jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, `dec`
		FROM `tabBudget Details`
		WHERE parent = %s
		""",
		(budget_name,),
		as_dict=True,
	)
	for bd in budget_details:
		account = bd.accounts
		doc_amount = account_amounts.get(account, 0)
		if not doc_amount and not (check_yearly or check_monthly):
			continue
		if check_yearly and flt(bd.yearly_budget) > 0:
			existing_yearly = _get_existing_expense(
				company, fiscal_year, department, account, doctype, yearly=True
			)
			# Exclude current doc to avoid double-count (on_submit runs after doc is saved)
			if doc.name:
				existing_yearly = _subtract_doc_from_expense(
					doctype, doc.name, account, existing_yearly, department=department
				)
			total_yearly = existing_yearly + doc_amount
			if total_yearly > flt(bd.yearly_budget):
				_throw_budget_exceeded(
					_("Annual"),
					account,
					department,
					bd.yearly_budget,
					total_yearly,
					company,
				)
		if check_monthly and flt(bd.yearly_budget) > 0:
			month_idx = getdate(posting_date).month  # 1-12
			month_field = MONTH_FIELDS[month_idx - 1]
			monthly_budget = flt(bd.get(month_field))
			if monthly_budget <= 0:
				continue
			existing_monthly = _get_existing_expense(
				company,
				fiscal_year,
				department,
				account,
				doctype,
				yearly=False,
				posting_date=posting_date,
			)
			if doc.name:
				existing_monthly = _subtract_doc_from_expense(
					doctype, doc.name, account, existing_monthly, department=department, posting_date=posting_date
				)
			total_monthly = existing_monthly + doc_amount
			if total_monthly > monthly_budget:
				_throw_budget_exceeded(
					_("Monthly"),
					account,
					department,
					monthly_budget,
					total_monthly,
					company,
				)


def _get_existing_expense(
	company, fiscal_year, department, account, doctype, yearly=True, posting_date=None
):
	"""Get existing expense (ordered for PO, actual for PI) for this department+account."""
	if doctype == "Purchase Order":
		return _get_ordered_amount_po(company, fiscal_year, department, account, yearly, posting_date)
	else:
		return _get_actual_expense_pi(company, fiscal_year, department, account, yearly, posting_date)


def _get_ordered_amount_po(company, fiscal_year, department, account, yearly, posting_date=None):
	"""Sum of (amount - billed_amt) for submitted POs for this department and account (Department = accounting dimension)."""
	fy = frappe.get_cached_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"])
	if not fy:
		return 0
	start, end = fy[0], fy[1]
	# Department accounting dimension: on header (po) or item (poi); match item if set else parent
	cond = """
		AND po.company = %(company)s
		AND po.docstatus = 1 AND po.status != 'Closed'
		AND poi.expense_account = %(account)s
		AND (poi.amount - ifnull(poi.billed_amt, 0)) > 0
		AND po.transaction_date BETWEEN %(start_date)s AND %(end_date)s
		AND ((ifnull(poi.department, '') = '' AND po.department = %(department)s) OR poi.department = %(department)s)
	"""
	args = {
		"company": company,
		"department": department,
		"account": account,
		"start_date": start,
		"end_date": end,
	}
	if not yearly and posting_date:
		dt = getdate(posting_date)
		last = get_last_day(posting_date)
		cond += " AND po.transaction_date BETWEEN %(month_start)s AND %(month_end)s"
		args["month_start"] = dt.replace(day=1)
		args["month_end"] = last
	res = frappe.db.sql(
		f"""
		SELECT SUM(poi.amount - ifnull(poi.billed_amt, 0)) AS total
		FROM `tabPurchase Order Item` poi
		INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
		WHERE 1=1 {cond}
		""",
		args,
		as_dict=True,
	)
	return flt(res[0].total if res else 0, 2)


def _get_actual_expense_pi(company, fiscal_year, department, account, yearly, posting_date=None):
	"""Sum of base_net_amount from submitted PIs for this department and account (Department = accounting dimension)."""
	fy = frappe.get_cached_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"])
	if not fy:
		return 0
	start, end = fy[0], fy[1]
	# Department accounting dimension: on header (pi) or item (pii)
	cond = """
		AND pi.company = %(company)s
		AND pi.docstatus = 1 AND pii.expense_account = %(account)s
		AND pi.posting_date BETWEEN %(start_date)s AND %(end_date)s
		AND ((ifnull(pii.department, '') = '' AND pi.department = %(department)s) OR pii.department = %(department)s)
	"""
	args = {
		"company": company,
		"department": department,
		"account": account,
		"start_date": start,
		"end_date": end,
	}
	if not yearly and posting_date:
		dt = getdate(posting_date)
		last = get_last_day(posting_date)
		cond += " AND pi.posting_date BETWEEN %(month_start)s AND %(month_end)s"
		args["month_start"] = dt.replace(day=1)
		args["month_end"] = last
	res = frappe.db.sql(
		f"""
		SELECT SUM(ifnull(pii.base_net_amount, pii.amount)) AS total
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE 1=1 {cond}
		""",
		args,
		as_dict=True,
	)
	return flt(res[0].total if res else 0, 2)


def _subtract_doc_from_expense(doctype, docname, account, current_total, department=None, posting_date=None):
	"""Subtract this document's contribution (for this department and account) from current_total."""
	if doctype == "Purchase Order":
		# Department accounting dimension: match item.department or parent.department
		sub = frappe.db.sql(
			"""
			SELECT SUM(poi.amount - ifnull(poi.billed_amt, 0))
			FROM `tabPurchase Order Item` poi
			INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
			WHERE poi.parent = %s AND poi.expense_account = %s
			  AND (ifnull(poi.department, '') = '' AND po.department = %s OR poi.department = %s)
			""",
			(docname, account, department or "", department or ""),
			as_list=True,
		)
	elif doctype == "Purchase Invoice":
		sub = frappe.db.sql(
			"""
			SELECT SUM(ifnull(pii.base_net_amount, pii.amount))
			FROM `tabPurchase Invoice Item` pii
			INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
			WHERE pii.parent = %s AND pii.expense_account = %s
			  AND (ifnull(pii.department, '') = '' AND pi.department = %s OR pii.department = %s)
			""",
			(docname, account, department or "", department or ""),
			as_list=True,
		)
	else:
		return current_total
	subtract = flt(sub[0][0] if sub and sub[0][0] else 0, 2)
	return max(0, current_total - subtract)


def _throw_budget_exceeded(action_for, account, department, budget_amount, total_expense, company):
	currency = frappe.get_cached_value("Company", company, "default_currency") or "USD"
	from frappe.utils import fmt_money
	msg = _(
		"{0} Budget for Account {1} against Department {2} is {3}. Total expense would be {4}."
	).format(
		action_for,
		frappe.bold(account),
		frappe.bold(department),
		frappe.bold(fmt_money(budget_amount, currency=currency)),
		frappe.bold(fmt_money(total_expense, currency=currency)),
	)
	frappe.throw(msg, title=_("Budget Exceeded"))


# ---------------------------------------------------------------------------
# Booking actual expenses (Expense Claim)
# ---------------------------------------------------------------------------

def validate_norwa_budget_on_expense_claim(doc, event=None):
	"""
	Validate Expense Claim against Norwa Departmental Budget when applicable on booking actual expenses.
	Runs on Expense Claim on_submit. Uses Department (header) and expense account from claim details.
	"""
	if doc.docstatus != 1:
		return
	department = doc.get("department")
	company = doc.get("company")
	posting_date = doc.get("posting_date")
	if not department or not company or not posting_date:
		return

	fiscal_year = get_fiscal_year(posting_date, company=company)
	if not fiscal_year:
		return
	fiscal_year = fiscal_year[0]

	# Build (account -> amount) from expenses: use default_account and sanctioned_amount or amount
	account_amounts = {}
	for row in doc.get("expenses") or []:
		acc = row.get("default_account")
		if not acc:
			# Fallback: get default account from Expense Claim Type for this company
			et = row.get("expense_type")
			if et:
				acc = frappe.db.get_value(
					"Expense Claim Account",
					{"parent": et, "company": company},
					"default_account",
				)
		if not acc:
			continue
		amt = flt(row.get("sanctioned_amount") or row.get("amount"), 2)
		if amt <= 0:
			continue
		account_amounts[acc] = account_amounts.get(acc, 0) + amt

	if not account_amounts:
		return

	budgets = frappe.db.sql(
		"""
		SELECT name, applicable_on_booking_actual_expenses, monthly_applicable_on_booking_actual_expenses
		FROM `tabNorwa Departmental Budget`
		WHERE company = %(company)s AND fiscal_year = %(fiscal_year)s AND department = %(department)s
		  AND docstatus = 1
		  AND (applicable_on_booking_actual_expenses = 1 OR monthly_applicable_on_booking_actual_expenses = 1)
		""",
		{"company": company, "fiscal_year": fiscal_year, "department": department},
		as_dict=True,
	)
	if not budgets:
		return

	for budget in budgets:
		for account, doc_amount in account_amounts.items():
			bd_row = frappe.db.sql(
				"""
				SELECT accounts,
				       (jan + feb + mar + apr + may + jun + jul + aug + sep + oct + nov + `dec`) AS yearly_budget,
				       jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, `dec`
				FROM `tabBudget Details`
				WHERE parent = %s AND accounts = %s
				""",
				(budget.name, account),
				as_dict=True,
			)
			if not bd_row:
				continue
			bd = bd_row[0]

			if budget.applicable_on_booking_actual_expenses and flt(bd.yearly_budget) > 0:
				existing_yearly = _get_actual_expense_gl(company, fiscal_year, department, account, yearly=True)
				total_yearly = existing_yearly + doc_amount
				if total_yearly > flt(bd.yearly_budget):
					_throw_budget_exceeded(
						_("Annual"),
						account,
						department,
						bd.yearly_budget,
						total_yearly,
						company,
					)

			if budget.monthly_applicable_on_booking_actual_expenses:
				month_idx = getdate(posting_date).month
				month_field = MONTH_FIELDS[month_idx - 1]
				monthly_budget = flt(bd.get(month_field))
				if monthly_budget > 0:
					existing_monthly = _get_actual_expense_gl(
						company, fiscal_year, department, account, yearly=False, posting_date=posting_date
					)
					total_monthly = existing_monthly + doc_amount
					if total_monthly > monthly_budget:
						_throw_budget_exceeded(
							_("Monthly"),
							account,
							department,
							monthly_budget,
							total_monthly,
							company,
						)
		break


def _get_actual_expense_gl(company, fiscal_year, department, account, yearly=True, posting_date=None):
	"""Sum actual expense from GL Entry for account, company, department (Department = accounting dimension)."""
	cond = """
		AND gle.company = %(company)s AND gle.account = %(account)s AND gle.fiscal_year = %(fiscal_year)s
		AND gle.docstatus = 1 AND gle.is_cancelled = 0
		AND gle.department = %(department)s
	"""
	args = {"company": company, "account": account, "fiscal_year": fiscal_year, "department": department}
	if not yearly and posting_date:
		dt = getdate(posting_date)
		last = get_last_day(posting_date)
		cond += " AND gle.posting_date BETWEEN %(month_start)s AND %(month_end)s"
		args["month_start"] = dt.replace(day=1)
		args["month_end"] = last
	res = frappe.db.sql(
		f"""
		SELECT SUM(gle.debit) - SUM(gle.credit) FROM `tabGL Entry` gle
		WHERE 1=1 {cond}
		""",
		args,
		as_list=True,
	)
	return flt(res[0][0] if res and res[0][0] else 0, 2)
