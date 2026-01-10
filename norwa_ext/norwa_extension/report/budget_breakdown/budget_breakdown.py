# Copyright (c) 2026, Norwa and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	if not filters:
		filters = {}
	
	view_type = filters.get("view_type", "Department x Accounts")
	
	if view_type == "Department x Accounts":
		return get_department_accounts_view(filters)
	elif view_type == "Department x Months":
		return get_department_months_view(filters)
	else:
		return [], []


def get_department_accounts_view(filters):
	"""Department x Accounts view: Departments on rows, Accounts on columns"""
	conditions = get_conditions(filters)
	
	# Get company currency
	company = filters.get("company")
	currency_options = f"Company:{company}:default_currency" if company else ""
	
	# First, get all unique accounts
	accounts_query = """
		SELECT DISTINCT bd.accounts as account, acc.account_name
		FROM `tabBudget Details` bd
		INNER JOIN `tabNorwa Departmental Budget` ndb ON bd.parent = ndb.name
		LEFT JOIN `tabAccount` acc ON bd.accounts = acc.name
		WHERE ndb.docstatus = 1
		{conditions}
		ORDER BY bd.accounts
	""".format(conditions=conditions)
	
	accounts = frappe.db.sql(accounts_query, filters, as_dict=True)
	
	# Build dynamic columns
	columns = [
		{"fieldname": "department", "label": _("Department"), "fieldtype": "Link", "options": "Department"},
		{"fieldname": "department_name", "label": _("Department Name"), "fieldtype": "Data"}
	]
	
	# Add account columns
	account_map = {}
	for idx, acc in enumerate(accounts):
		# Create safe fieldname from account name
		import re
		fieldname = f"account_{idx}"
		columns.append({
			"fieldname": fieldname,
			"label": acc.account_name or acc.account,
			"fieldtype": "Currency",
			"options": currency_options
		})
		account_map[acc.account] = fieldname
	
	columns.append({"fieldname": "total", "label": _("Total"), "fieldtype": "Currency", "options": currency_options})
	
	# Get department data with account totals
	query = """
		SELECT 
			ndb.department,
			dept.department_name,
			bd.accounts as account,
			SUM(bd.jan + bd.feb + bd.mar + bd.apr + bd.may + bd.jun + 
				bd.jul + bd.aug + bd.sep + bd.oct + bd.nov + bd.`dec`) as account_total
		FROM `tabNorwa Departmental Budget` ndb
		INNER JOIN `tabBudget Details` bd ON bd.parent = ndb.name
		LEFT JOIN `tabDepartment` dept ON ndb.department = dept.name
		WHERE ndb.docstatus = 1
		{conditions}
		GROUP BY ndb.department, bd.accounts
		ORDER BY ndb.department, bd.accounts
	""".format(conditions=conditions)
	
	raw_data = frappe.db.sql(query, filters, as_dict=True)
	
	# Pivot data: group by department
	department_data = {}
	for row in raw_data:
		dept = row.department
		if dept not in department_data:
			department_data[dept] = {
				"department": dept,
				"department_name": row.department_name,
				"total": 0
			}
			# Initialize all account columns to 0
			for acc in accounts:
				fieldname = account_map[acc.account]
				department_data[dept][fieldname] = 0
		
		# Set account total
		if row.account in account_map:
			fieldname = account_map[row.account]
			department_data[dept][fieldname] = row.account_total
			department_data[dept]["total"] += row.account_total
	
	data = list(department_data.values())
	
	return columns, data


def get_department_months_view(filters):
	"""Department x Months view: Departments on rows, Months on columns"""
	# Get company currency
	company = filters.get("company")
	currency_options = f"Company:{company}:default_currency" if company else ""
	
	columns = [
		{"fieldname": "department", "label": _("Department"), "fieldtype": "Link", "options": "Department"},
		{"fieldname": "department_name", "label": _("Department Name"), "fieldtype": "Data"},
		{"fieldname": "jan", "label": _("Jan"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "feb", "label": _("Feb"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "mar", "label": _("Mar"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "apr", "label": _("Apr"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "may", "label": _("May"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "jun", "label": _("Jun"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "jul", "label": _("Jul"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "aug", "label": _("Aug"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "sep", "label": _("Sep"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "oct", "label": _("Oct"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "nov", "label": _("Nov"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "dec", "label": _("Dec"), "fieldtype": "Currency", "options": currency_options},
		{"fieldname": "total", "label": _("Total"), "fieldtype": "Currency", "options": currency_options}
	]
	
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			ndb.department,
			dept.department_name,
			SUM(bd.jan) as jan,
			SUM(bd.feb) as feb,
			SUM(bd.mar) as mar,
			SUM(bd.apr) as apr,
			SUM(bd.may) as may,
			SUM(bd.jun) as jun,
			SUM(bd.jul) as jul,
			SUM(bd.aug) as aug,
			SUM(bd.sep) as sep,
			SUM(bd.oct) as oct,
			SUM(bd.nov) as nov,
			SUM(bd.`dec`) as `dec`,
			SUM(bd.jan + bd.feb + bd.mar + bd.apr + bd.may + bd.jun + 
				bd.jul + bd.aug + bd.sep + bd.oct + bd.nov + bd.`dec`) as total
		FROM `tabNorwa Departmental Budget` ndb
		INNER JOIN `tabBudget Details` bd ON bd.parent = ndb.name
		LEFT JOIN `tabDepartment` dept ON ndb.department = dept.name
		WHERE ndb.docstatus = 1
		{conditions}
		GROUP BY ndb.department, dept.department_name
		ORDER BY ndb.department
	""".format(conditions=conditions)
	
	data = frappe.db.sql(query, filters, as_dict=True)
	
	return columns, data


def get_conditions(filters):
	"""Build WHERE conditions based on filters"""
	conditions = []
	
	if filters.get("company"):
		conditions.append("ndb.company = %(company)s")
	
	if filters.get("fiscal_year"):
		conditions.append("ndb.fiscal_year = %(fiscal_year)s")
	
	if filters.get("department"):
		conditions.append("ndb.department = %(department)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""
