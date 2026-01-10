// Copyright (c) 2025, Norwa and contributors
// For license information, please see license.txt


frappe.ui.form.on("Budget Details", {
    // Trigger on change of any month field
    jan: update_total,
    feb: update_total,
    mar: update_total,
    apr: update_total,
    may: update_total,
    jun: update_total,
    jul: update_total,
    aug: update_total,
    sep: update_total,
    oct: update_total,
    nov: update_total,
    dec: update_total
});

function update_total(frm, cdt, cdn) {
    let child = locals[cdt][cdn];
    let total = 0;
    (frm.doc.budget_details || []).forEach(row => {
        total += flt(row.jan) + flt(row.feb) + flt(row.mar) + flt(row.apr) +
                 flt(row.may) + flt(row.jun) + flt(row.jul) + flt(row.aug) +
                 flt(row.sep) + flt(row.oct) + flt(row.nov) + flt(row.dec);
    });

    frm.set_value("total", total);
}

frappe.ui.form.on("Norwa Departmental Budget", {
    company: function(frm) {
        // Filter department based on selected company
        set_department_filter(frm);
        // Filter accounts in child table based on selected company
        set_accounts_filter(frm);
        // Clear department if company changes
        if (frm.doc.department) {
            frm.set_value("department", "");
        }
    },
    refresh: function(frm) {
        // Set filter when form loads if company is already selected
        set_department_filter(frm);
        set_accounts_filter(frm);
    }
});

function set_department_filter(frm) {
    if (frm.doc.company) {
        frm.set_query("department", function() {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
    } else {
        // Clear filter if no company is selected
        frm.set_query("department", function() {
            return {};
        });
    }
}

function set_accounts_filter(frm) {
    if (frm.doc.company) {
        frm.set_query("accounts", "budget_details", function() {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
    } else {
        // Clear filter if no company is selected
        frm.set_query("accounts", "budget_details", function() {
            return {};
        });
    }
}
