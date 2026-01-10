// Copyright (c) 2026, Norwa and contributors
// For license information, please see license.txt

frappe.query_reports["Departmental Budget Breakdown"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"width": "200px"
		},
		{
			"fieldname": "department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"reqd": 1,
			"width": "200px",
			"get_query": function() {
				let company = frappe.query_report.get_filter_value("company");
				if (company) {
					return {
						filters: {
							company: company
						}
					};
				}
			}
		},
		{
			"fieldname": "fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"reqd": 1,
			"width": "200px"
		}
	],
	
	"onload": function(report) {
		// Set default fiscal year to current fiscal year
		frappe.db.get_value("Fiscal Year", {"year_start_date": ["<=", frappe.datetime.get_today()], "year_end_date": [">=", frappe.datetime.get_today()]}, "name", (r) => {
			if (r && r.name) {
				report.set_filter_value("fiscal_year", r.name);
			}
		});
		
		// Filter department based on company when company changes
		report.page.fields_dict.company.$input.on("change", function() {
			let company = report.get_filter_value("company");
			if (company) {
				report.set_query("department", function() {
					return {
						filters: {
							company: company
						}
					};
				});
			}
		});
	}
};
