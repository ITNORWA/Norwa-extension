# Copyright (c) 2026, Norwa and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	if not filters:
		filters = {}
	
	# Department is required for this report
	if not filters.get("department"):
		return [], []
	
	# Get company currency
	company = filters.get("company")
	currency_options = f"Company:{company}:default_currency" if company else ""
	
	columns = [
		{"fieldname": "account", "label": _("Account"), "fieldtype": "Link", "options": "Account", "width": 200},
		{"fieldname": "account_name", "label": _("Account Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "jan", "label": _("Jan"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "feb", "label": _("Feb"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "mar", "label": _("Mar"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "apr", "label": _("Apr"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "may", "label": _("May"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "jun", "label": _("Jun"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "jul", "label": _("Jul"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "aug", "label": _("Aug"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "sep", "label": _("Sep"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "oct", "label": _("Oct"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "nov", "label": _("Nov"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "dec", "label": _("Dec"), "fieldtype": "Currency", "width": 120, "options": currency_options},
		{"fieldname": "total", "label": _("Total"), "fieldtype": "Currency", "width": 120, "options": currency_options}
	]
	
	conditions = get_conditions(filters)
	
	query = """
		SELECT 
			bd.accounts as account,
			acc.account_name,
			bd.jan,
			bd.feb,
			bd.mar,
			bd.apr,
			bd.may,
			bd.jun,
			bd.jul,
			bd.aug,
			bd.sep,
			bd.oct,
			bd.nov,
			bd.`dec`,
			(bd.jan + bd.feb + bd.mar + bd.apr + bd.may + bd.jun + 
				bd.jul + bd.aug + bd.sep + bd.oct + bd.nov + bd.`dec`) as total
		FROM `tabBudget Details` bd
		INNER JOIN `tabNorwa Departmental Budget` ndb ON bd.parent = ndb.name
		LEFT JOIN `tabAccount` acc ON bd.accounts = acc.name
		WHERE ndb.docstatus = 1
		{conditions}
		ORDER BY bd.accounts
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
