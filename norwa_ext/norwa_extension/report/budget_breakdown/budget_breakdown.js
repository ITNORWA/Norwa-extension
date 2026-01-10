// Copyright (c) 2026, Norwa and contributors
// For license information, please see license.txt

frappe.query_reports["Budget Breakdown"] = {
	"filters": [
		{
			"fieldname": "view_type",
			"label": __("View Type"),
			"fieldtype": "Select",
			"options": "Department x Accounts\nDepartment x Months",
			"default": "Department x Accounts",
			"reqd": 1,
			"width": "200px"
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"width": "200px"
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
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		// Make department clickable to navigate to Departmental Budget Breakdown
		if (column.fieldname == "department" && data.department) {
			let company = frappe.query_report.get_filter_value("company");
			let fiscal_year = frappe.query_report.get_filter_value("fiscal_year");
			if (company && fiscal_year) {
				let url = `/app/query-report/Departmental Budget Breakdown?company=${encodeURIComponent(company)}&department=${encodeURIComponent(data.department)}&fiscal_year=${encodeURIComponent(fiscal_year)}`;
				value = `<a href="${url}" style="color: #5e64ff; text-decoration: underline; cursor: pointer;">${value || data.department_name || data.department}</a>`;
			}
		}
		
		return value;
	},
	
	"onload": function(report) {
		// Set default fiscal year to current fiscal year
		frappe.db.get_value("Fiscal Year", {"year_start_date": ["<=", frappe.datetime.get_today()], "year_end_date": [">=", frappe.datetime.get_today()]}, "name", (r) => {
			if (r && r.name) {
				report.set_filter_value("fiscal_year", r.name);
			}
		});
		
		// Add view type selector as buttons for better UX
		setTimeout(function() {
			add_view_type_buttons(report);
		}, 500);
	}
};

function add_view_type_buttons(report) {
	// Create button group for view types
	let filter_area = report.page.$filter_area;
	if (!filter_area || filter_area.length === 0) {
		return;
	}
	
	let view_buttons_html = `
		<div class="view-type-selector" style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px;">
			<label style="font-weight: 600; margin-right: 10px;">${__("View Type")}:</label>
			<button class="btn btn-sm view-btn active" data-view="Department x Accounts" style="margin-right: 5px;">
				${__("Department x Accounts")}
			</button>
			<button class="btn btn-sm view-btn" data-view="Department x Months">
				${__("Department x Months")}
			</button>
		</div>
	`;
	
	// Insert before filter form
	filter_area.prepend(view_buttons_html);
	
	// Handle button clicks using Frappe's jQuery
	let $ = frappe.$;
	report.page.$filter_area.find(".view-btn").on("click", function() {
		let view_type = $(this).data("view");
		
		// Update button states
		report.page.$filter_area.find(".view-btn").removeClass("active btn-primary").addClass("btn-default");
		$(this).addClass("active btn-primary").removeClass("btn-default");
		
		// Set filter value
		report.set_filter_value("view_type", view_type);
		
		// Trigger change event to update department field visibility
		if (report.page.fields_dict.view_type && report.page.fields_dict.view_type.$input) {
			report.page.fields_dict.view_type.$input.trigger("change");
		}
		
		// Refresh report
		report.refresh();
	});
	
	// Set initial active button
	let current_view = report.get_filter_value("view_type") || "Department x Accounts";
	report.page.$filter_area.find(`.view-btn[data-view="${current_view}"]`).addClass("active btn-primary").removeClass("btn-default");
};
