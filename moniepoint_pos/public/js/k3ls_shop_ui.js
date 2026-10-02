/* K3LS presentation only. Keep ERPNext validation, permissions and record storage. */
(() => {
    const config = frappe.boot.k3ls_shop_ui;
    if (!config) return;
    document.body.classList.add("k3ls-shop");
    // Translate the shop's terms, including quick-entry forms and checkout.
    Object.assign(frappe._messages, {
        "Item": "Product", "Item Name": "Product name", "Item Group": "Category",
        "K3LS Repair": "Repair", "POS Profile": "Till settings", "POS Invoice": "Sale",
        "Purchase Invoice": "Purchase", "Sales Invoice": "Invoice", "Payment Entry": "Payment",
        "Mode of Payment": "Payment method", "Posting Date": "Date", "Party": "Name",
        "Party Type": "Customer or supplier", "Primary Contact Details": "Contact details",
        "Receive": "Money in", "Pay": "Money out", "Internal Transfer": "Move between accounts",
        "Primary Address Details": "Address", "Email Id": "Email", "Mobile Number": "Phone",
        "State/Province": "State", "ZIP Code": "Postcode", "UOM": "Unit",
        "Qty": "Quantity", "Rate": "Price", "Grand Total": "Total",
        "Outstanding Amount": "Left to pay", "Net Total": "Subtotal",
        "Draft": "Not finished", "Submitted": "Confirmed", "Enabled": "Active",
        "Cancelled": "Cancelled", "New Invoice": "New sale", "Checkout": "Take payment",
        "Submit": "Confirm", "Save": "Save", "Close POS": "Close till",
        "Primary Address": "Main address", "Primary Contact": "Main contact",
        "Supplier Type": "Type", "Customer Type": "Type", "Company": "Business", "Individual": "Person",
        "My Device": "Choose files", "Library": "Saved files", "Attach": "Add file",
        "Reload File": "Retry upload", "Supplier Invoice No": "Supplier invoice number",
        "Please save before attaching.": "Save this record before adding files.",
        "Condition and faults by Item ID": "Condition and faults",
        "Testing at sale": "Was it tested?", "Customer acknowledged condition": "Customer accepts the condition",
        "Condition disclosure / receipt reference": "Condition record or receipt number",
        "Payment Type": "Direction", "Account Paid From": "From account", "Account Paid To": "To account",
        "In Place": "In place", "Debit To": "Customer account", "Credit To": "Supplier account",
        "Payment Terms": "Payment dates", "Due Date": "Pay by", "Remarks": "Notes",
        "Payment Entries": "Payments", "Stock Entry": "Stock change", "Stock Entries": "Stock changes",
        "Journal Entry": "Account adjustment", "Journal Entries": "Account adjustments",
        "POS Opening Entry": "Open till", "POS Closing Entry": "Close till",
        "Payment Entry Reference": "Invoice", "Payment Entry Deduction": "Deduction",
        "Point of Sale": "POS", "Attachments": "Files", "ToDo": "Tasks",
        "Payment Request": "Payment request", "Payment Order": "Payment order",
        "No Payment Entry found": "No payments yet", "No Payment Entries found": "No payments yet",
        "Create Payment Entry": "Add payment", "Make Payment Entry": "Add payment",
        "Fetch outstanding invoices": "Find unpaid invoices", "Get Outstanding Invoices": "Find unpaid invoices",
        "Allocate Payment Amount": "Match payment", "Unallocated Amount": "Unmatched amount",
        "Reference No": "Reference", "Reference Date": "Payment date",
        "Paid Amount": "Paid", "Received Amount": "Received", "Difference Amount": "Difference",
        "Taxes and Charges": "Tax", "Accounting Dimensions": "Account details",
        "Stock ownership": "Owner", "K3LS Owned": "K3LS", "Sister Owned": "Sister's stock",
        "Third-party Owner": "Someone else", "Supplier Purchase": "Bought from supplier",
        "Swap / Trade-in": "Trade-in", "Third-party Custody": "Held for someone else",
        "Configuration": "Specifications", "Diagnosis": "Problem found",
        "Received": "Received", "Diagnosing": "Checking", "Ready for collection": "Ready",
        "Customer approved quote": "Price approved", "Assigned repairer": "Repairer",
        "Intake photo / evidence": "Device photo", "Address / location": "Address",
        "See all Activity": "All notifications", "Notification": "Notifications",
        "You haven't created a {0} yet": "No {0} records yet",
        "No {0} found with matching filters. Clear filters to see all {0}.": "No matches. Clear the filters to see all records.",
        "Create your first {0}:Create a new document from list view": "Add {0}",
        "Create a new {0}:Create a new document from list view": "Add {0}",
        "Report: {0}": "{0} report", "Report:": "Report",
        "Desktop": "Home", "Workspaces": "Switch shop", "Logout": "Sign out",
    });

    // ERPNext uses breadcrumbs as its title. Keep one heading, without the trail.
    const page_titles = Object.fromEntries(Object.keys(config).map(name => [name, __(name)]));
    Object.assign(page_titles, { "Payment Entry": "Payments", "Payment": "Payments", "Supplier": "Suppliers", "Customer": "Customers", "Item": "Products", "Product": "Products", "K3LS Repair": "Repairs", "Repair": "Repairs", "Purchase Invoice": "Purchases", "Purchase": "Purchases", "POS Invoice": "Sales", "Sale": "Sales", "Sales Invoice": "Invoices", "Invoice": "Invoices", "Account": "Accounts" });
    const page = frappe.ui.Page.prototype;
    const set_title = page.set_title;
    page.set_title = function (title, ...args) {
        set_title.call(this, title, ...args);
        let heading = this.$title_area.children(".k3ls-page-title");
        if (!heading.length) heading = $("<h1 class='k3ls-page-title'></h1>").prependTo(this.$title_area);
        const label = page_titles[title] || __(title);
        heading.text(label).attr("title", label);
    };

    // The installed uploader supports both options. Subclass it rather than changing Frappe.
    const simplify_uploads = () => {
        const Uploader = frappe.ui.FileUploader;
        if (!Uploader || Uploader.k3ls_simplified) return;
        class ShopUploader extends Uploader {
            static k3ls_simplified = true;
            constructor(options = {}) {
                const doctype = options.doctype || options.frm?.doctype;
                if (config[doctype]) {
                    options = { ...options, allow_web_link: false, allow_toggle_private: false };
                }
                super(options);
            }
        }
        frappe.ui.FileUploader = ShopUploader;
    };
    frappe.require("file_uploader.bundle.js", simplify_uploads);

    for (const [doctype, settings] of Object.entries(config)) {
        const simplify_form = (frm) => {
                frm.$wrapper.addClass("k3ls-simple-form");
                frm.$wrapper.toggleClass("k3ls-master-form", ["Supplier", "Customer"].includes(doctype));
                if (doctype === "Supplier") frm.set_df_property("supplier_details", "description", "");
                if (doctype === "Customer") frm.set_df_property("customer_details", "description", "");
                if (!frm.k3ls_original_hidden) {
                    frm.k3ls_original_hidden = Object.fromEntries(frm.meta.fields.map(df => [df.fieldname, df.hidden || 0]));
                }
                const reveal = Boolean(frm.k3ls_more_fields && frappe.user.has_role("System Manager"));
                for (const name of settings.hide) {
                    const tab = frm.layout.tabs.find(tab => tab.df.fieldname === name);
                    const control = frm.fields_dict[name] || tab;
                    if (!control) continue;
                    // Never leave a new form with an empty, hidden required input.
                    const df = control.df;
                    const fields = frm.meta.fields;
                    const index = fields.findIndex(field => field.fieldname === name);
                    const children = [];
                    if (["Section Break", "Tab Break"].includes(df.fieldtype)) {
                        for (const child of fields.slice(index + 1)) {
                            if (child.fieldtype === "Tab Break" || (df.fieldtype === "Section Break" && child.fieldtype === "Section Break")) break;
                            children.push(child);
                        }
                    }
                    const needs_input = frm.is_new() && [df, ...children].some(field => field.reqd && !field.read_only && !frm.doc[field.fieldname] && !field.default);
                    const hidden = reveal ? frm.k3ls_original_hidden[name] : Number(!needs_input);
                    frm.set_df_property(name, "hidden", hidden);
                    if (tab) { tab.df.hidden = hidden; tab.refresh(); }
                }
                if (doctype === "Item" && !reveal) {
                    frm.set_df_property("stock_uom", "hidden", frm.doc.stock_uom === "Nos" ? 1 : 0);
                    frm.set_df_property("is_stock_item", "description", "Turn off for services such as repairs.");
                    frm.set_df_property("disabled", "label", "Stop selling this product");
                } else if (doctype === "Item") {
                    frm.set_df_property("stock_uom", "hidden", frm.k3ls_original_hidden.stock_uom);
                }
                frm.remove_custom_button(__("More fields"));
                frm.remove_custom_button(__("Fewer fields"));
                frm.k3ls_fields_menu?.closest("li").remove();
                if (frappe.user.has_role("System Manager")) {
                    frm.k3ls_fields_menu = frm.page.add_menu_item(__(reveal ? "Fewer fields" : "More fields"), () => {
                        frm.k3ls_more_fields = !reveal;
                        simplify_form(frm);
                    });
                    frm.page.show_menu();
                }
                if (frm.layout.tabs.find(tab => tab.is_active() && tab.df.hidden)) {
                    frm.layout.tabs.find(tab => !tab.df.hidden && !tab.hidden)?.set_active();
                }
                // Keep these calculated account details out of the normal payment form.
                if (doctype === "Payment Entry" && !reveal) {
                    for (const name of ["source_exchange_rate", "target_exchange_rate", "base_paid_amount", "base_received_amount", "paid_from_account_currency", "paid_to_account_currency"]) {
                        if (frm.fields_dict[name]) {
                            const value = frm.doc[name];
                            const calculated = name.startsWith("base_");
                            frm.set_df_property(name, "hidden", Number(calculated || ["NGN", 1].includes(value)));
                        }
                    }
                } else if (doctype === "Payment Entry") {
                    for (const name of ["source_exchange_rate", "target_exchange_rate", "base_paid_amount", "base_received_amount", "paid_from_account_currency", "paid_to_account_currency"]) {
                        if (frm.fields_dict[name]) frm.set_df_property(name, "hidden", frm.k3ls_original_hidden[name]);
                    }
                }
                const extra_actions = ["Remind Me", "Follow", "Unfollow", "Repeat", "Copy to Clipboard"];
                frm.page.menu.find("a").each(function () {
                    const label = $(this).find(".menu-item-label").text().trim();
                    if (extra_actions.map(label => __(label)).includes(label)) $(this).closest("li").hide();
                });
        };
        frappe.ui.form.on(doctype, { refresh: simplify_form });
    }

    const list = frappe.views.ListView.prototype;
    const load_last_view = frappe.views.ListView.load_last_view;
    frappe.views.ListView.load_last_view = function () {
        const route = frappe.get_route();
        if (config[route[1]] && !config[route[1]].presentation_only && route.length === 2) {
            frappe.set_route("list", frappe.router.doctype_layout || route[1], "list");
            return true;
        }
        return load_last_view.call(this);
    };
    const base_list = frappe.views.BaseList.prototype;
    const setup_view_menu = base_list.setup_view_menu;
    base_list.setup_view_menu = function () {
        if (!config[this.doctype]) return setup_view_menu.call(this);
        this.page.wrapper.addClass("k3ls-simple-list");
        if (frappe.user.has_role("System Manager") && this.view_name !== "Report") {
            this.page.add_menu_item("Report", () => frappe.set_route("list", this.doctype, "report"), true);
        }
    };
    const get_actions = list.get_actions_menu_items;
    list.get_actions_menu_items = function () {
        const actions = get_actions.call(this);
        if (!config[this.doctype]) return actions;
        const hidden = ["Assign To", "Clear Assignment", "Apply Assignment Rule", "Add Tags"].map(label => __(label, null, "Button in list view actions menu"));
        return actions.filter(action => !hidden.includes(action.label));
    };

    {
        const header = frappe.ui.SidebarHeader.prototype;
        const add_navbar_items = header.add_navbar_items;
        header.add_navbar_items = function () {
            add_navbar_items.call(this);
            if (!["K3LS Owner", "K3LS Shop"].includes(this.title)) return;
            const hidden = ["website", "edit sidebar", "display", "session defaults", "help"];
            this.dropdown_items = this.dropdown_items.filter(item => !hidden.includes((item.label || "").toLowerCase()) && !["website", "edit-sidebar", "display", "help"].includes(item.name));
            this.dropdown_items = this.dropdown_items.filter((item, index, items) => !item.is_divider || (index > 0 && index < items.length - 1 && !items[index - 1].is_divider));
        };
        const sidebar = frappe.ui.Sidebar.prototype;
        const resolve = sidebar.resolve_sidebar;
        const shop = ["Item", "Customer", "K3LS Repair", "POS Invoice", "Sales Invoice", "point-of-sale"];
        const owner = ["Supplier", "Purchase Invoice", "Payment Entry", "POS Profile", "Account", "Moniepoint Settings", "Moniepoint Terminal", "Moniepoint Transaction"];
        sidebar.resolve_sidebar = function (entity, module) {
            const title = shop.includes(entity) ? "K3LS Shop" : owner.includes(entity) ? "K3LS Owner" : null;
            if (title && this.all_sidebar_items[title.toLowerCase()]) return title;
            return resolve.call(this, entity, module);
        };
    }
})();
