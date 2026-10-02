(() => {
    for (const [doctype, config] of Object.entries(frappe.boot.k3ls_shop_ui || {})) {
        const original = frappe.listview_settings[doctype] || {};
        if (original.k3ls_simplified) continue;
        frappe.listview_settings[doctype] = {
            ...original,
            k3ls_simplified: true,
            hide_name_column: !config.keep_id,
            hide_name_filter: !config.keep_id,
        };
    }
})();
