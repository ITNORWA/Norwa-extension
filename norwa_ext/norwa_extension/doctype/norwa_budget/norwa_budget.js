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
