/* K3LS presentation only. Keep ERPNext validation, permissions and record storage. */
(() => {
    const config = frappe.boot.k3ls_shop_ui;
    if (!config) return;
    // Discard cached page scripts, never draft or business data, after app updates.
    const revision = "20261004-4";
    if (localStorage.getItem("k3ls-page-revision") !== revision) {
        for (const page_name of ["point-of-sale", "shop-repairs", "shop-accounts", "shop-profit", "shop-money-owed", "permission-manager"]) {
            localStorage.removeItem(`_page:${page_name}`);
        }
        localStorage.setItem("k3ls-page-revision", revision);
    }
    frappe.k3ls_role_labels = {"System Manager": "Owner / administrator", "Sales User": "Sales",
        "Sales Manager": "Manage sales", "Stock User": "Products", "Stock Manager": "Manage products",
        "Purchase User": "Restock", "Purchase Manager": "Manage restock",
        "Accounts User": "Money in/out", "Accounts Manager": "Manage accounts", "K3LS Repair Staff": "Repairs"};
    document.body.classList.add("k3ls-shop");
    frappe.k3ls_search_field = input => {
        if (input.parent().hasClass("k3ls-search-field")) return input.parent();
        const area = $("<div class='k3ls-search-field' role='search'></div>");
        if (input.parent().length) area.insertBefore(input);
        $("<span class='k3ls-search-symbol' aria-hidden='true'></span>").html(frappe.utils.icon("search", "md")).appendTo(area);
        input.appendTo(area);
        return area;
    };
    frappe.k3ls_empty_basket = () => `<div class='k3ls-empty-basket' role='status'>
        <img src='/assets/moniepoint_pos/images/undraw-empty-cart.svg' alt=''>
        <p>${frappe.utils.escape_html(__("Choose a product to start a sale."))}</p></div>`;
    const sale_choices = (parent, {product_sale, before_choose = () => {}} = {}) => {
        const choices = $("<div class='k3ls-sale-choices'></div>").appendTo(parent);
        const choose = async action => {before_choose(); await action();};
        if (frappe.model.can_create("POS Invoice")) {
            $("<button type='button' class='k3ls-sale-choice'></button>")
                .append($("<span aria-hidden='true'></span>").html(frappe.utils.icon("shopping-cart", "lg")))
                .append($("<strong></strong>").text(__("Product sale")))
                .on("click", () => choose(product_sale || (() => frappe.set_route("point-of-sale"))))
                .appendTo(choices);
        }
        if (frappe.model.can_create("K3LS Repair")) {
            $("<button type='button' class='k3ls-sale-choice'></button>")
                .append($("<span aria-hidden='true'></span>").html(frappe.utils.icon("wrench", "lg")))
                .append($("<strong></strong>").text(__("Repair")))
                .on("click", () => choose(() => {
                    frappe.k3ls_pending_repair = true;
                    return frappe.set_route("shop-repairs", {sidebar: frappe.app?.sidebar?.sidebar_title || "K3LS Shop"});
                }))
                .appendTo(choices);
        }
        if (!choices.children().length) choices.append($("<p></p>").text(__("You don't have access to create sales or repairs.")));
        return choices;
    };
    frappe.k3ls_new_sale = ({product_sale} = {}) => {
        if (frappe.boot.read_only) return Promise.resolve();
        return new Promise(resolve => {
            const dialog = new frappe.ui.Dialog({title: __("New sale"), fields: [{fieldname: "choices", fieldtype: "HTML"}]});
            sale_choices(dialog.fields_dict.choices.$wrapper, {product_sale, before_choose: () => dialog.hide()});
            dialog.$wrapper.on("hidden.bs.modal", resolve);
            dialog.show();
        });
    };
    const is_blank_sale = frm => ["POS Invoice", "Sales Invoice"].includes(frm.doctype) && frm.is_new()
        && !frm.doc.__k3ls_keep_invoice_form && !frm.doc.is_return && !frm.doc.return_against
        && (!frm.doc.company || frm.doc.company === "K3LS LIMITED")
        && (!frm.doc.customer || frm.doc.customer === "K3LS Walk-in Customer")
        && !(frm.doc.items || []).some(row => row.item_code || flt(row.qty) || flt(row.rate) || row.serial_no || row.batch_no)
        && !(frm.doc.payments || []).some(row => flt(row.amount))
        && !flt(frm.doc.paid_amount) && !frm.doc.remarks && !frm.doc.contact_mobile && !frm.doc.contact_email
        && !Object.keys(frm.doc).some(key => key.startsWith("custom_") && frm.doc[key]);
    const present_sale_entry = frm => {
        const show = is_blank_sale(frm) && !frm.k3ls_more_fields && !frappe.boot.read_only
            && frappe.get_route()?.[0] === "Form" && frappe.get_route()?.[1] === frm.doctype;
        frm.$wrapper.toggleClass("k3ls-sale-entry", show);
        frm.page.wrapper.toggleClass("k3ls-sale-entry-page", show);
        frm.k3ls_sale_entry?.toggle(show);
        if (!show) return;
        if (!frm.k3ls_sale_entry) {
            frm.k3ls_sale_entry = $("<section class='k3ls-sale-entry-content'></section>")
                .attr("aria-label", __("New sale")).insertBefore(frm.body);
            sale_choices(frm.k3ls_sale_entry);
        }
        frm.k3ls_sale_entry.show();
        frm.page.set_title(__("New sale"));
    };
    const new_doc = frappe.new_doc;
    frappe.new_doc = function (doctype, opts, init_callback) {
        if (doctype === "User" && frappe.k3ls_new_user) return frappe.k3ls_new_user();
        // Mapped, prefilled and callback-initialised documents keep their values and core path.
        if (["POS Invoice", "Sales Invoice"].includes(doctype) && !init_callback
            && !Object.keys(opts || {}).some(key => key !== "sidebar")) {
            return frappe.k3ls_new_sale();
        }
        if (doctype === "Purchase Invoice" && frappe.boot.k3ls_purchase_defaults && !init_callback && !opts?.is_return && !opts?.items
            && (!opts?.company || opts.company === frappe.boot.k3ls_purchase_defaults?.company)) {
            opts = {...frappe.boot.k3ls_purchase_defaults, update_stock: 1, ...opts};
        }
        if (["POS Invoice", "Sales Invoice"].includes(doctype)) {
            const callback = init_callback;
            init_callback = function (target) {
                (target.doc || target).__k3ls_keep_invoice_form = true;
                return callback?.call(this, target);
            };
        }
        return new_doc.call(this, doctype, opts, init_callback);
    };
    // Blank grid rows are not products. Stop before core generates setup-field errors.
    const check_mandatory = frappe.ui.form.check_mandatory;
    frappe.ui.form.check_mandatory = function (frm) {
        if (frm.doc?.pos_profile === "K3LS Shop" && frappe.get_route()?.[0] === "point-of-sale"
            && !(frm.doc.items || []).some(row => row.item_code && flt(row.qty))) {
            frappe.msgprint({title: __("Basket"), message: frappe.k3ls_empty_basket()});
            return false;
        }
        return check_mandatory.call(this, frm);
    };
    // Explicit loading state, separate from a successfully loaded empty result.
    frappe.k3ls_loading = (parent, label) => {
        const loading = $("<div class='k3ls-loading-state' role='status'></div>");
        $("<span></span>").text(__(label || "Loading")).appendTo(loading);
        const rows = $("<div class='k3ls-loading-rows' aria-hidden='true'></div>").appendTo(loading);
        for (let index = 0; index < 3; index++) $("<div></div>").appendTo(rows);
        parent.empty().append(loading).attr("aria-busy", "true");
        return loading;
    };
    const notifications = frappe.ui.Notifications.prototype;
    const make_notification_tab = notifications.make_tab_view;
    notifications.make_tab_view = function (item) {
        if (item.id === "notifications") return make_notification_tab.call(this, item);
    };
    const clean_notifications = instance => {
        instance.categories = (instance.categories || []).filter(category => {
            if (category.id === "notifications") return true;
            category.$tab?.remove(); instance.tabs[category.id]?.hide(); return false;
        });
        instance.panel_events?.remove(); instance.panel_changelog_feed?.remove();
        if (instance.categories[0]) instance.switch_tab(instance.categories[0]);
    };
    const setup_notification_headers = notifications.setup_headers;
    notifications.setup_headers = function () {
        setup_notification_headers.call(this);
        clean_notifications(this);
    };
    if (frappe.app?.sidebar?.notifications) clean_notifications(frappe.app.sidebar.notifications);
    // Omit the explanatory option from display, keyboard selection and result counts.
    // The original search query and its permission filters remain untouched.
    const link_control = frappe.ui.form.ControlLink.prototype;
    link_control.get_filter_description = async function () { return ""; };
    const setup_autocomplete = link_control.setup_awesomeplete;
    link_control.setup_awesomeplete = function () {
        setup_autocomplete.call(this);
        const original_filter = this.awesomplete.filter;
        this.awesomplete.filter = function (item, input) {
            return item.value !== "filter_description__link_option" && original_filter.call(this, item, input);
        };
    };
    // The phone dock uses the same routes and access checks as the shop sidebar.
    const dock = $("<nav class='k3ls-app-dock' aria-label='Shop'></nav>").appendTo(document.body);
    const shortcuts = [
        {label: "POS", icon: "shopping-cart", route: ["point-of-sale"], doctype: "POS Invoice", matches: ["point-of-sale", "POS Invoice"]},
        {label: "Repairs", icon: "wrench", route: ["shop-repairs"], doctype: "K3LS Repair", matches: ["shop-repairs", "K3LS Repair"]},
        {label: "Products", icon: "package", route: ["List", "Item"], doctype: "Item", matches: ["Item"]},
    ];
    for (const shortcut of shortcuts) {
        if (!frappe.model.can_read(shortcut.doctype)) continue;
        shortcut.link = $("<a></a>").attr("href",
            shortcut.route[0] === "List" ? "/desk/item" : `/desk/${shortcut.route[0]}`)
            .append($("<span aria-hidden='true'></span>").html(frappe.utils.icon(shortcut.icon, "md")))
            .append($("<span></span>").text(__(shortcut.label))).appendTo(dock);
        shortcut.link.on("click", event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            if (frappe.is_mobile() && frappe.app?.sidebar?.sidebar_expanded) frappe.app.sidebar.close();
            frappe.set_route(...shortcut.route);
        });
    }
    const more = $("<button type='button' aria-label='More sections'></button>")
        .append($("<span aria-hidden='true'></span>").html(frappe.utils.icon("menu", "md")))
        .append($("<span></span>").text(__("More"))).appendTo(dock);
    more.on("click", () => {
        if (!frappe.app?.sidebar?.wrapper) return;
        frappe.app.sidebar.set_workspace_sidebar();
        frappe.app.sidebar.wrapper.show();
        frappe.app.sidebar.set_height();
        frappe.app.sidebar.toggle_width();
        frappe.app.sidebar.prevent_scroll();
    });
    const update_dock = () => {
        const route = frappe.get_route() || [];
        const entity = ["Form", "List", "Tree"].includes(route[0]) ? route[1] : route[0];
        const shop_screen = Boolean(config[entity] || ["point-of-sale", "shop-repairs", "shop-accounts", "shop-profit", "shop-money-owed", "shop-staff", "permission-manager", "User", "Workspaces", "K3LS Shop", "K3LS Owner"].includes(entity));
        document.body.classList.toggle("k3ls-app-screen", shop_screen);
        const owner_screen = ["Supplier", "Purchase Invoice", "Payment Entry", "POS Profile", "Account", "shop-accounts", "shop-profit", "shop-money-owed", "shop-staff", "permission-manager", "User", "Moniepoint Settings", "Moniepoint Terminal", "Moniepoint Transaction", "K3LS Owner"]
            .includes(entity) || (entity === "Workspaces" && route[1] === "K3LS Owner")
            || (["POS Invoice", "Item", "shop-repairs", "K3LS Repair"].includes(entity) && frappe.app?.sidebar?.sidebar_title === "K3LS Owner");
        document.body.classList.toggle("k3ls-owner-screen", owner_screen);
        let shortcut_selected = false;
        for (const shortcut of shortcuts) {
            const selected = shortcut.matches.includes(entity);
            shortcut_selected ||= selected;
            shortcut.link?.toggleClass("selected", selected).attr("aria-current", selected ? "page" : null);
        }
        more.toggleClass("selected", !shortcut_selected);
        more.attr("aria-expanded", String(Boolean(frappe.app?.sidebar?.sidebar_expanded)));
        document.body.classList.toggle("k3ls-drawer-open", Boolean(frappe.is_mobile()
            && frappe.app?.sidebar?.sidebar_expanded && frappe.app.sidebar.wrapper?.is(":visible")));
    };
    frappe.router.on("change", update_dock);
    $(document).on("page-change.k3ls-app sidebar-expand.k3ls-app", update_dock);
    $(update_dock);
    // Translate the shop's terms, including quick-entry forms and checkout.
    Object.assign(frappe._messages, {
        "Item": "Product", "Item Name": "Product name", "Item Group": "Category",
        "K3LS Repair": "Repair", "POS Profile": "Checkout settings", "POS Invoice": "Sale",
        "Purchase Invoice": "Restock", "Purchase": "Restock", "Purchases": "Restock", "Sales Invoice": "Invoice", "Payment Entry": "Payment",
        "Mode of Payment": "Payment method", "Moniepoint MFB": "Moniepoint", "Posting Date": "Date", "Party": "Name",
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
        "Payment Entries": "Money in/out", "Stock Entry": "Stock change", "Stock Entries": "Stock changes",
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
        "All Items": "Products", "Item Cart": "Basket", "No items in cart": "Basket is empty",
        "Total Quantity": "Items", "Recent Orders": "Recent sales", "Complete Order": "Finish sale",
        "Edit Cart": "Back to basket", "Remaining Amount": "Left to pay", "Change Amount": "Change",
        "Update Additional Information": "Sale details", "Additional Information": "Sale details",
        "Click to add email / phone": "Customer details", "Quantity Available": "In stock",
    });

    // ERPNext uses breadcrumbs as its title. Keep one heading, without the trail.
    const page_titles = Object.fromEntries(Object.keys(config).map(name => [name, __(name)]));
    Object.assign(page_titles, { "Payment Entry": "Money in/out", "Payment": "Money in/out", "Supplier": "Suppliers", "Customer": "Customers", "Item": "Products", "Product": "Products", "K3LS Repair": "Repairs", "Repair": "Repairs", "Purchase Invoice": "Restock", "Purchase": "Restock", "Restock": "Restock", "POS Invoice": "Sales", "Sale": "Sales", "Sales Invoice": "Invoices", "Invoice": "Invoices", "Account": "Accounts", "Point of Sale": "POS", "POS": "POS", "Repairs": "Repairs", "New repair": "New repair", "User": "Users", "Money owed": "Money owed" });
    const page = frappe.ui.Page.prototype;
    const set_title = page.set_title;
    page.set_title = function (title, ...args) {
        set_title.call(this, title, ...args);
        let heading = this.$title_area.children(".k3ls-page-title");
        if (!heading.length) heading = $("<h1 class='k3ls-page-title'></h1>").prependTo(this.$title_area);
        const label = page_titles[title] || __(title);
        heading.text(label).attr("title", label);
    };

    // Frappe loads this bundle asynchronously. Wrap it when it arrives, without
    // starting a second download and freezing ordinary navigation.
    const wrap_uploader = Uploader => Uploader && new Proxy(Uploader, {
            construct(Target, args) {
                let options = args[0] || {};
                const doctype = options.doctype || options.frm?.doctype;
                if (config[doctype]) {
                    options = { ...options, allow_web_link: false, allow_toggle_private: false };
                }
                return Reflect.construct(Target, [options]);
            },
        });
    let shop_uploader = wrap_uploader(frappe.ui.FileUploader);
    Object.defineProperty(frappe.ui, "FileUploader", {
        configurable: true,
        get: () => shop_uploader,
        set: Uploader => { shop_uploader = wrap_uploader(Uploader); },
    });

    for (const [doctype, settings] of Object.entries(config)) {
        const simplify_form = (frm) => {
                const changed = new Set();
                const set_property = (name, property, value) => {
                    const control = frm.fields_dict[name] || frm.layout.tabs.find(tab => tab.df.fieldname === name);
                    const df = frm.get_docfield(name) || control?.df;
                    if (!df || df[property] == value) return;
                    df[property] = value;
                    if (control) { control.df[property] = value; changed.add(control); }
                };
                frm.$wrapper.addClass("k3ls-simple-form");
                frm.$wrapper.toggleClass("k3ls-no-files", ["Moniepoint Settings", "Moniepoint Terminal", "Moniepoint Transaction", "POS Profile", "Account", "User"].includes(doctype));
                frm.$wrapper.toggleClass("k3ls-user-form", doctype === "User");
                if (doctype === "Moniepoint Settings" && !frm.$wrapper.find(".k3ls-admin-warning").length) {
                    const warning = $("<section class='k3ls-admin-warning' role='note' aria-label='Admin only'></section>");
                    $("<strong></strong>").text(__("Admin only")).appendTo(warning);
                    $("<p></p>").text(__("Only administrators should change these payment connection settings.")).appendTo(warning);
                    warning.prependTo(frm.layout.wrapper);
                    $("<img class='k3ls-moniepoint-wordmark' alt='Moniepoint' src='/assets/moniepoint_pos/images/moniepoint-logo.svg'>").insertBefore(warning);
                }
                frm.$wrapper.toggleClass("k3ls-master-form", ["Supplier", "Customer"].includes(doctype));
                if (doctype === "Supplier") set_property("supplier_details", "description", "");
                if (doctype === "Customer") set_property("customer_details", "description", "");
                if (!frm.k3ls_original_hidden) {
                    frm.k3ls_original_hidden = Object.fromEntries(frm.meta.fields.map(df => [df.fieldname, df.hidden || 0]));
                    frm.k3ls_original_read_only = Object.fromEntries(frm.meta.fields.map(df => [df.fieldname, df.read_only || 0]));
                }
                const reveal = Boolean(frm.k3ls_more_fields && frappe.user.has_role("System Manager"));
                for (const [name, label] of Object.entries(settings.labels || {})) set_property(name, "label", label);
                if (doctype === "User") {
                    frm.$wrapper.toggleClass("k3ls-user-advanced", reveal);
                    for (const [name, label] of Object.entries(settings.labels)) {
                        const tab = frm.layout.tabs.find(tab => tab.df.fieldname === name);
                        if (tab) tab.tab_link.find(".nav-link").text(__(label));
                        const section = frm.layout.sections_dict[name];
                        if (section?.head) section.head.toggle(Boolean(label)).contents().filter(function () {return this.nodeType === 3;}).remove();
                        if (section?.head && label) section.head.prepend(document.createTextNode(__(label)));
                    }
                    if (!reveal) {
                        const password = frm.layout.sections_dict.change_password;
                        password?.body.removeClass("hide");
                        password?.head.removeClass("collapsed").hide();
                    }
                    for (const name of ["phone", "mobile_no"]) {
                        const control = frm.fields_dict[name];
                        if (control && !control.k3ls_original_parent) control.k3ls_original_parent = control.$wrapper.parent();
                        if (control) control.$wrapper.appendTo(reveal ? control.k3ls_original_parent : frm.fields_dict.last_name.$wrapper.parent());
                    }
                    // Reuse core role controls. Hide unrelated choices without removing their checked values.
                    const role_labels = frappe.k3ls_role_labels;
                    const editor = frm.roles_editor;
                    if (editor) {
                        const tidy = () => {
                            const advanced = Boolean(frm.k3ls_more_fields);
                            editor.multicheck.$select_buttons.toggle(advanced);
                            for (const option of editor.multicheck.options || []) {
                                option.$checkbox?.toggle(advanced || option.value in role_labels);
                                option.$checkbox?.find(".label-area").text(advanced ? __(option.value) : __(role_labels[option.value] || option.value));
                            }
                        };
                        if (!editor.k3ls_choices) {
                            editor.k3ls_choices = true;
                            const make = editor.multicheck.make_checkboxes;
                            editor.multicheck.make_checkboxes = function () {make.call(this); tidy();};
                        }
                        tidy();
                    }
                }
                if (doctype === "POS Profile" && frm.doc.name === "K3LS Shop" && !frm.is_new()) {
                    frm.page.set_title(__("Checkout settings"));
                    const grid = frm.fields_dict.payments.$wrapper;
                    if (!frm.k3ls_payment_summary) frm.k3ls_payment_summary = $("<section class='k3ls-checkout-methods' aria-label='Payment methods'></section>").insertBefore(grid);
                    const summary = frm.k3ls_payment_summary.empty().toggle(!reveal);
                    for (const payment of frm.doc.payments || []) {
                        const card = $("<div class='k3ls-checkout-method'></div>").appendTo(summary);
                        const icon = frappe.boot.k3ls_bank_icons?.[payment.mode_of_payment];
                        if (icon) {
                            $("<img alt=''>").attr("src", `/assets/moniepoint_pos/images/${icon}`).appendTo(card);
                        } else $("<span aria-hidden='true'></span>").html(frappe.utils.icon("wallet", "lg")).appendTo(card);
                        const text = $("<div></div>").appendTo(card);
                        $("<strong></strong>").text(__(payment.mode_of_payment)).appendTo(text);
                        $("<small></small>").text(__(payment.default ? "Default" : payment.mode_of_payment === "Moniepoint MFB" ? "Card or transfer" : "Bank transfer")).appendTo(text);
                    }
                    grid.toggle(reveal);
                    $("<p class='text-muted'></p>").text(__("Part payments are available at checkout.")).appendTo(summary);
                    frm.page.btn_primary.toggleClass("hide", !reveal);
                }
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
                    const account_secret_field = doctype === "User" && ["email", "new_password", "logout_all_sessions", "send_welcome_email"].includes(name);
                    const hidden = account_secret_field ? 1 : reveal ? frm.k3ls_original_hidden[name] : Number(!needs_input);
                    set_property(name, "hidden", hidden);
                }
                if (doctype === "Purchase Invoice") {
                    frm.$wrapper.toggleClass("k3ls-purchase-form", !reveal);
                    const has_supplier = Boolean(frm.doc.supplier);
                    const has_products = (frm.doc.items || []).some(row => row.item_code && flt(row.qty));
                    const progressive = !reveal && frm.is_new() && !frm.doc.is_return;
                    frm.$wrapper.toggleClass("k3ls-restock-await-supplier", progressive && !has_supplier && !has_products);
                    frm.$wrapper.toggleClass("k3ls-restock-await-products", progressive && !has_products);
                    const details = frm.layout.tabs[0];
                    if (!frm.k3ls_purchase_payments) {
                        frm.k3ls_purchase_payments = $("<section class='form-section k3ls-purchase-payments'><h2></h2><div class='section-body'></div></section>").appendTo(details.wrapper);
                        frm.k3ls_purchase_payments.find("h2").text(__("Payment"));
                    }
                    frm.k3ls_purchase_payments.toggle(!reveal && (!progressive || has_products));
                    for (const name of ["is_paid", "mode_of_payment", "paid_amount", "due_date", "remarks"]) {
                        const control = frm.fields_dict[name];
                        if (!control) continue;
                        control.k3ls_purchase_parent ||= control.$wrapper.parent();
                        control.$wrapper.appendTo(reveal ? control.k3ls_purchase_parent : frm.k3ls_purchase_payments.find(".section-body"));
                    }
                    for (const name of ["outstanding_amount"]) {
                        const control = frm.fields_dict[name];
                        if (!control) continue;
                        control.k3ls_purchase_parent ||= control.$wrapper.parent();
                        control.$wrapper.appendTo(reveal ? control.k3ls_purchase_parent : frm.k3ls_purchase_payments.find(".section-body"));
                    }
                    if (!reveal) {
                        set_property("is_return", "hidden", Number(!frm.doc.is_return));
                        set_property("update_stock", "hidden", Number(Boolean(frm.doc.update_stock)));
                        for (const name of ["mode_of_payment", "paid_amount"]) set_property(name, "hidden", Number(!frm.doc.is_paid));
                        const fully_paid = frm.doc.is_paid && flt(frm.doc.grand_total) > 0 && flt(frm.doc.paid_amount) >= flt(frm.doc.grand_total);
                        set_property("due_date", "hidden", Number(Boolean(fully_paid)));
                        set_property("update_stock", "read_only", frm.is_new() ? frm.k3ls_original_read_only.update_stock : 1);
                        for (const name of ["total_taxes_and_charges", "discount_amount", "rounding_adjustment", "rounded_total"]) {
                            set_property(name, "hidden", Number(!flt(frm.doc[name]) || name === "rounded_total" && (frm.doc.disable_rounded_total || frm.doc.rounded_total === frm.doc.grand_total)));
                        }
                        if (details.df.hidden) {details.df.hidden = 0; details.refresh();}
                    }
                    const grid = frm.fields_dict.items.grid;
                    grid.wrapper.find(".grid-add-row").text(__("Add product"));
                    for (const name of ["supplier_invoice_details", "sec_warehouse"]) {
                        const section = frm.layout.sections_dict[name];
                        if (!section?.head) continue;
                        section.head.contents().filter(function () {return this.nodeType === 3;}).remove();
                        section.head.prepend(document.createTextNode(__(settings.labels[name])));
                    }
                    const visible = new Set(["item_code", "item_name", "qty", "rate", "amount", "serial_no", "batch_no", "serial_and_batch_bundle", "add_serial_batch_bundle"]);
                    frm.k3ls_purchase_grid ||= Object.fromEntries(grid.docfields.map(df => [df.fieldname, {hidden: df.hidden || 0, label: df.label, in_list_view: df.in_list_view || 0}]));
                    let grid_changed = false;
                    for (const df of grid.docfields) {
                        if (["Section Break", "Column Break", "Tab Break"].includes(df.fieldtype)) continue;
                        const original = frm.k3ls_purchase_grid[df.fieldname];
                        const hidden = reveal ? original.hidden : Number(!visible.has(df.fieldname));
                        const label = reveal ? original.label : {item_code: "Product", item_name: "Product name", qty: "Quantity", rate: "Cost each", amount: "Total", serial_no: "Serial numbers"}[df.fieldname] || df.label;
                        const in_list_view = reveal ? original.in_list_view : Number(["item_code", "qty", "rate", "amount"].includes(df.fieldname));
                        for (const [property, value] of Object.entries({hidden, label, in_list_view})) {
                            if (df[property] !== value) {grid.update_docfield_property(df.fieldname, property, value); grid_changed = true;}
                        }
                    }
                    if (grid_changed) {grid.visible_columns = null; grid.refresh();}
                    if (!reveal && details.is_active() === false) details.set_active();
                    if (reveal) {
                        set_property("update_stock", "read_only", frm.k3ls_original_read_only.update_stock);
                        for (const name of ["is_return", "update_stock"]) set_property(name, "hidden", frm.k3ls_original_hidden[name]);
                    }
                    const payment = frm.fields_dict.mode_of_payment;
                    if (!payment.k3ls_purchase_query_wrapped) {
                        payment.k3ls_purchase_query_wrapped = true;
                        payment.k3ls_purchase_query = payment.get_query;
                        payment.get_query = (...args) => {
                            const query = payment.k3ls_purchase_query?.(...args) || {};
                            if (frm.k3ls_more_fields) return query;
                            const filters = Array.isArray(query.filters)
                                ? [...query.filters, ["Mode of Payment", "name", "in", frappe.boot.k3ls_payment_methods]]
                                : {...query.filters, name: ["in", frappe.boot.k3ls_payment_methods]};
                            return {...query, filters};
                        };
                    }
                }
                if (doctype === "Item" && !reveal) {
                    set_property("stock_uom", "hidden", frm.doc.stock_uom === "Nos" ? 1 : 0);
                    set_property("disabled", "label", "Stop selling this product");
                } else if (doctype === "Item") {
                    set_property("stock_uom", "hidden", frm.k3ls_original_hidden.stock_uom);
                }
                if (doctype === "Item") {
                    if (frappe.k3ls_product_prices) frappe.k3ls_product_prices(frm);
                    for (const name of ["item_code", "stock_uom", "is_stock_item", "has_serial_no", "opening_stock", "valuation_rate", "standard_rate",
                        "custom_k3ls_purchase_cost", "custom_k3ls_landing_cost"]) {
                        set_property(name, "read_only", !reveal && !frm.is_new() ? 1 : frm.k3ls_original_read_only[name] || 0);
                    }
                }
                // Child-row tax template selectors are separate from the parent form fields.
                for (const control of Object.values(frm.fields_dict)) {
                    if (!control.grid) continue;
                    for (const df of control.grid.docfields) {
                        if (!df.fieldname.includes("tax") || df.read_only) continue;
                        frm.k3ls_child_tax_hidden ||= {};
                        const key = `${control.df.fieldname}:${df.fieldname}`;
                        if (!(key in frm.k3ls_child_tax_hidden)) frm.k3ls_child_tax_hidden[key] = df.hidden || 0;
                        const hidden = reveal ? frm.k3ls_child_tax_hidden[key] : 1;
                        if (df.hidden !== hidden) control.grid.update_docfield_property(df.fieldname, "hidden", hidden);
                    }
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
                // Keep these calculated account details out of the normal payment form.
                if (doctype === "Payment Entry" && !reveal) {
                    for (const name of ["source_exchange_rate", "target_exchange_rate", "base_paid_amount", "base_received_amount", "paid_from_account_currency", "paid_to_account_currency"]) {
                        if (frm.fields_dict[name]) {
                            const value = frm.doc[name];
                            const calculated = name.startsWith("base_");
                            set_property(name, "hidden", Number(calculated || ["NGN", 1].includes(value)));
                        }
                    }
                } else if (doctype === "Payment Entry") {
                    for (const name of ["source_exchange_rate", "target_exchange_rate", "base_paid_amount", "base_received_amount", "paid_from_account_currency", "paid_to_account_currency"]) {
                        if (frm.fields_dict[name]) set_property(name, "hidden", frm.k3ls_original_hidden[name]);
                    }
                }
                if (changed.size) {
                    for (const control of changed) control.refresh();
                    frm.layout.refresh_dependency();
                    frm.layout.refresh_sections();
                }
                if (frm.layout.tabs.find(tab => tab.is_active() && tab.df.hidden)) {
                    frm.layout.tabs.find(tab => !tab.df.hidden && !tab.hidden)?.set_active();
                }
                frm.k3ls_header_actions?.forEach(({label, group, button}) => {
                    button.toggle(reveal);
                    if (group) {
                        const parent = button.closest(".inner-group-button");
                        parent.toggle(parent.find(".dropdown-menu a").toArray().some(item => item.style.display !== "none"));
                    }
                    const menu_label = group ? `${group} > ${label}` : label;
                    frm.page.menu.find(".menu-item-label").filter(function () {return $(this).text().trim() === menu_label;}).closest("li").toggle(reveal);
                });
                frm.page.wrapper.find(".prev-doc, .next-doc").toggle(reveal);
                const extra_actions = ["Remind Me", "Follow", "Unfollow", "Repeat", "Copy to Clipboard",
                    "Jump to field", "Show Links", "Edit DocType", "Customize", "Customize Form"];
                if (doctype === "User") extra_actions.push("Email", "Rename", "Duplicate");
                frm.page.menu.find("a").each(function () {
                    const label = $(this).find(".menu-item-label").text().trim();
                    if (extra_actions.map(label => __(label)).includes(label)) $(this).closest("li").toggle(reveal);
                });
                present_sale_entry(frm);
        };
        frappe.ui.form.on(doctype, {setup(frm) {
            frm.$wrapper.addClass("k3ls-simple-form");
            if (doctype === "User") frm.$wrapper.addClass("k3ls-user-form k3ls-no-files");
        }, refresh: simplify_form, onload_post_render: simplify_form});
        if (doctype === "Purchase Invoice") {
            frappe.ui.form.on(doctype, {onload: async frm => {
                if (!frm.is_new() || !frm.doc.__run_link_triggers || frm.doc.is_return
                    || (frm.doc.items || []).some(row => row.item_code || row.purchase_receipt || row.purchase_order)) return;
                const defaults = frappe.boot.k3ls_purchase_defaults || {};
                if (!frm.doc.company && defaults.company) await frm.set_value("company", defaults.company);
                if (frm.doc.company === defaults.company && !frm.doc.set_warehouse && defaults.set_warehouse) {
                    await frm.set_value("set_warehouse", defaults.set_warehouse);
                }
            }});
            // Run after core's asynchronous defaults and calculations, not before them.
            const trigger = frappe.ui.form.ScriptManager.prototype.trigger;
            const events = new Set(["refresh", "supplier", "company", "credit_to", "item_code", "qty", "rate", "amount",
                "items_add", "items_remove", "is_paid", "paid_amount", "mode_of_payment", "due_date", "grand_total",
                "rounded_total", "total_taxes_and_charges", "discount_amount"]);
            frappe.ui.form.ScriptManager.prototype.trigger = function (event, ...args) {
                const result = trigger.call(this, event, ...args);
                if (this.frm.doctype !== "Purchase Invoice" || !events.has(event)) return result;
                return Promise.resolve(result).then(value => {simplify_form(this.frm); return value;});
            };
        }
    }

    const suggested_actions = {
        User: ["Set User Permissions", "View Permitted Documents", "View Doctype Permissions", "Create User Email", "Impersonate", "Reset LDAP Password", "Reset Password"],
        Supplier: ["Accounting Ledger", "Accounts Payable", "Get Supplier Group Details", "Link with Customer", "Request for Quotation", "Supplier Quotation", "Purchase Order", "Purchase Receipt"],
        Customer: ["Accounting Ledger", "Accounts Receivable", "Get Customer Group Details", "Link with Supplier", "Quotation", "Sales Order", "Delivery Note"],
        Item: ["Stock Ledger", "Stock Projected Qty", "Show Variants", "Item Variant Settings", "Variant Details Report", "Single Variant", "Multiple Variants", "Variant", "Duplicate"],
        "Purchase Invoice": ["Purchase Order", "Purchase Receipt", "Material Request", "Supplier Quotation", "Product Bundle"],
    };
    const add_button = frappe.ui.form.Form.prototype.add_custom_button;
    frappe.ui.form.Form.prototype.add_custom_button = function (label, fn, group) {
        if (this.doctype === "User" && label === __("Reset Password")) return;
        if (!config[this.doctype] || !suggested_actions[this.doctype]?.some(value => __(value) === label)) return add_button.call(this, label, fn, group);
        // Keep original callbacks available in More fields, without suggesting unrelated work.
        const button = add_button.call(this, label, fn, group);
        if (button) {
            this.k3ls_header_actions ||= [];
            this.k3ls_header_actions = this.k3ls_header_actions.filter(action => action.label !== label);
            this.k3ls_header_actions.push({label, group, button});
            button.toggle(Boolean(this.k3ls_more_fields));
            if (group) {
                const parent = button.closest(".inner-group-button");
                parent.toggle(parent.find(".dropdown-menu a").toArray().some(item => item.style.display !== "none"));
            }
        }
        return button;
    };
    const navigation = frappe.ui.form.Toolbar.prototype.make_navigation;
    frappe.ui.form.Toolbar.prototype.make_navigation = function () {
        if (!config[this.frm.doctype] || this.frm.k3ls_more_fields) return navigation.call(this);
    };

    const list = frappe.views.ListView.prototype;
    const make_new_doc = list.make_new_doc;
    list.make_new_doc = function () {
        if (this.doctype === "User" && frappe.k3ls_new_user) return frappe.k3ls_new_user();
        if (["POS Invoice", "Sales Invoice"].includes(this.doctype)) return frappe.k3ls_new_sale();
        return make_new_doc.call(this);
    };
    const load_last_view = frappe.views.ListView.load_last_view;
    frappe.views.ListView.load_last_view = function () {
        const route = frappe.get_route() || [];
        if (config[route[1]] && (!config[route[1]].presentation_only || route[1] === "User") && route.length === 2) {
            const options = {...Object.fromEntries(new URLSearchParams(location.search)), ...frappe.route_options};
            frappe.set_route("list", frappe.router.doctype_layout || route[1], "list", options);
            return true;
        }
        return load_last_view.call(this);
    };
    const base_list = frappe.views.BaseList.prototype;
    const setup_filters = base_list.setup_filter_area;
    base_list.setup_filter_area = function () {
        if (!config[this.doctype]?.search_title) return setup_filters.call(this);
        // Keep normal filters in the Filter dialog rather than several competing header inputs.
        const original_meta = this.meta;
        const hide_name = this.settings.hide_name_filter;
        this.settings.hide_name_filter = true;
        this.meta = {...original_meta, title_field: null,
            fields: original_meta.fields.map(df => ({...df, in_standard_filter: 0}))};
        try {return setup_filters.call(this);}
        finally {this.meta = original_meta; this.settings.hide_name_filter = hide_name;}
    };
    // Core removes its skeleton after metadata, before fetching the first records.
    const hide_skeleton = list.hide_skeleton;
    list.hide_skeleton = function () {
        if (!config[this.doctype]) return hide_skeleton.call(this);
        this.$list_skeleton?.hide();
        this.parent.page.container.find(".layout-main").show();
        const parent = this.page?.main || this.parent.page.container.find(".page-content");
        this.k3ls_list_loading ||= $("<div class='k3ls-list-loading'></div>").appendTo(parent);
        frappe.k3ls_loading(this.k3ls_list_loading, "Loading records");
        this.page?.wrapper.addClass("k3ls-list-pending");
    };
    const refresh_list = list.refresh;
    list.refresh = function (...args) {
        if (!config[this.doctype]) return refresh_list.apply(this, args);
        if (this.k3ls_list_request) {
            this.k3ls_list_queued = args;
            return this.k3ls_list_request;
        }
        this.k3ls_list_loading ||= $("<div class='k3ls-list-loading'></div>").appendTo(this.page.main);
        frappe.k3ls_loading(this.k3ls_list_loading, "Loading records");
        this.k3ls_list_loading.show();
        this.page.wrapper.addClass("k3ls-list-pending").attr("aria-busy", "true");
        this.k3ls_list_failed = false;
        this.k3ls_list_request = (async () => {
            try {
                let next = args;
                do {
                    this.k3ls_list_queued = null;
                    await Promise.resolve(refresh_list.apply(this, next));
                    next = this.k3ls_list_queued;
                } while (next);
            } catch (error) {
                this.k3ls_list_loading.empty().append($("<p role='alert'></p>").text(__("Records could not load.")));
                $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
                    .on("click", () => {this.last_args = null; this.refresh();}).appendTo(this.k3ls_list_loading);
                this.k3ls_list_failed = true;
            } finally {
                this.k3ls_list_request = null;
                this.freeze(false);
                this.page.wrapper.attr("aria-busy", "false");
                this.k3ls_list_loading.attr("aria-busy", "false");
                if (!this.k3ls_list_failed) {this.k3ls_list_loading.hide(); this.page.wrapper.removeClass("k3ls-list-pending");}
            }
        })();
        return this.k3ls_list_request;
    };
    const after_load = frappe.ui.form.Form.prototype.run_after_load_hook;
    frappe.ui.form.Form.prototype.run_after_load_hook = function (...args) {
        const result = after_load.apply(this, args);
        present_sale_entry(this);
        if (config[this.doctype]) this.$wrapper.removeClass("k3ls-form-pending").attr("aria-busy", "false");
        return result;
    };
    $(document).on("form-refresh.k3ls-loading", (event, frm) => {
        if (config[frm.doctype]) frm.$wrapper.addClass("k3ls-form-pending").attr("aria-busy", "true");
    });
    const quick_fields = frappe.ui.form.QuickEntryForm.prototype.set_meta_and_mandatory_fields;
    frappe.ui.form.QuickEntryForm.prototype.set_meta_and_mandatory_fields = function () {
        quick_fields.call(this);
        if (this.doctype === "User") this.docfields = this.docfields.filter(df => df.fieldname !== "email" && (df.reqd || ["first_name", "last_name", "username"].includes(df.fieldname)));
    };
    const setup_view_menu = base_list.setup_view_menu;
    base_list.setup_view_menu = function () {
        if (!config[this.doctype]) return setup_view_menu.call(this);
        this.page.wrapper.addClass("k3ls-simple-list");
        if (frappe.user.has_role("System Manager") && this.view_name !== "Report") {
            this.page.add_menu_item("Report", () => frappe.set_route("list", this.doctype, "report"), true);
        }
        if (this.doctype === "User" && frappe.user.has_role("System Manager")) {
            this.page.add_menu_item(__("Shop access"), () => frappe.set_route("permission-manager"));
        }
    };
    const set_menu_items = base_list.set_menu_items;
    base_list.set_menu_items = function () {
        if (!config[this.doctype]) return set_menu_items.call(this);
        // Keep refresh and report/export access; configuration belongs outside everyday lists.
        const hidden = ["Import", "User Permissions", "Role Permissions Manager", "Customize", "Edit DocType",
            "Customize Quick Filters", "List Settings"].map(label => __(label, null, "Button in list view menu"));
        const items = this.menu_items;
        this.menu_items = items?.filter(item => !hidden.includes(item.label));
        try {return set_menu_items.call(this);}
        finally {this.menu_items = items;}
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
        const place_brand = instance => {
            instance.sidebar_wrapper.find(".k3ls-sidebar-brand").remove();
            if (!["K3LS Shop", "K3LS Owner"].includes(instance.title)) return;
            $("<div class='k3ls-sidebar-brand'><img src='/assets/moniepoint_pos/images/k3ls-loading-logo.png' alt='K3LS'></div>")
                .insertBefore(instance.wrapper);
        };
        const make_header = header.make;
        header.make = function () {make_header.call(this); place_brand(this);};
        if (frappe.app?.sidebar?.sidebar_header) place_brand(frappe.app.sidebar.sidebar_header);
        const add_navbar_items = header.add_navbar_items;
        header.add_navbar_items = function () {
            add_navbar_items.call(this);
            if (!["K3LS Owner", "K3LS Shop"].includes(this.title)) return;
            const hidden = ["website", "edit sidebar", "display", "session defaults", "help"];
            this.dropdown_items = this.dropdown_items.filter(item => !hidden.includes((item.label || "").toLowerCase()) && !["website", "edit-sidebar", "display", "help"].includes(item.name));
            this.dropdown_items = this.dropdown_items.filter((item, index, items) => !item.is_divider || (index > 0 && index < items.length - 1 && !items[index - 1].is_divider));
            this.dropdown_items.push({name: "password-recovery", label: __("Password and recovery"), icon: "lock",
                onClick: () => frappe.k3ls_account_security?.()});
        };
        const sidebar = frappe.ui.Sidebar.prototype;
        const link_item = frappe.ui.sidebar_item.TypeLink.prototype;
        const get_sidebar_path = link_item.get_path;
        link_item.get_path = function () {
            if (this.item.link_type === "DocType" && this.item.link_to === "POS Profile"
                && this.workspace_title?.toLowerCase() === "k3ls owner" && frappe.boot.k3ls_till_profile) {
                return `/desk/pos-profile/${encodeURIComponent(frappe.boot.k3ls_till_profile)}#accounting_tab`;
            }
            return get_sidebar_path.call(this);
        };
        const setup_sidebar = sidebar.setup;
        sidebar.setup = function (...args) {
            const result = setup_sidebar.apply(this, args);
            update_dock();
            return result;
        };
        const place_account_notifications = instance => {
            const root = instance.wrapper;
            if (!root?.length) return;
            let account_tools = root.find(".k3ls-account-tools");
            if (!account_tools.length) account_tools = $("<div class='k3ls-account-tools standard-items-sections'></div>")
                .appendTo(root.find(".body-sidebar-bottom"));
            root.find(".sidebar-notification").appendTo(account_tools);
            root.find(".dropdown-notifications").appendTo(account_tools);
            root.find(".sidebar-user-button").closest(".dropdown-navbar-user").appendTo(account_tools);
            account_tools.find(".avatar-name-email .text-secondary").text(frappe.boot.k3ls_username || "");
            const trigger = account_tools.find(".sidebar-notification .item-anchor");
            trigger.attr({role: "button", tabindex: "0", "aria-label": __("Notifications"), "aria-expanded": "false"});
            trigger.off("keydown.k3ls-notifications").on("keydown.k3ls-notifications", event => {
                if (["Enter", " "].includes(event.key)) {event.preventDefault(); trigger.trigger("click");}
            });
            const dropdown = account_tools.find(".dropdown-notifications");
            if (!dropdown.length) return;
            dropdown.find(".notifications-list").attr({role: "dialog", "aria-label": __("Notifications")});
            dropdown.find(".header-actions > span").each(function () {
                const action = $(this);
                action.attr({role: "button", tabindex: "0", "aria-label": action.attr("data-original-title") || action.attr("title") || __("Close notifications")});
                action.off("keydown.k3ls-notifications").on("keydown.k3ls-notifications", event => {
                    if (["Enter", " "].includes(event.key)) {event.preventDefault(); action.trigger("click");}
                });
            });
            instance.k3ls_notification_observer?.disconnect();
            instance.k3ls_notification_observer = new MutationObserver(() => {
                const open = !dropdown.hasClass("hidden");
                trigger.attr("aria-expanded", String(open));
                document.body.classList.toggle("k3ls-notifications-open", open);
            });
            instance.k3ls_notification_observer.observe(dropdown[0], {attributes: true, attributeFilter: ["class"]});
            dropdown.off("keydown.k3ls-notifications").on("keydown.k3ls-notifications", event => {
                if (event.key === "Escape") {dropdown.addClass("hidden"); trigger.trigger("focus");}
            });
        };
        const setup_sidebar_notifications = sidebar.setup_notifications;
        sidebar.setup_notifications = function () {
            setup_sidebar_notifications.call(this);
            place_account_notifications(this);
        };
        if (frappe.app?.sidebar?.notifications) place_account_notifications(frappe.app.sidebar);
        const load_sidebar_state = sidebar.load_sidebar_state;
        sidebar.load_sidebar_state = function () {
            load_sidebar_state.call(this);
            if (frappe.is_mobile()) return;
            const saved = localStorage.getItem("k3ls-sidebar-expanded");
            this.sidebar_expanded = saved === null || saved === "true";
        };
        const expand_sidebar = sidebar.expand_sidebar;
        sidebar.expand_sidebar = function () {
            expand_sidebar.call(this);
            // Opening the phone drawer must not overwrite the desktop preference.
            if (!frappe.is_mobile()) localStorage.setItem("k3ls-sidebar-expanded", String(this.sidebar_expanded));
        };
        const add_sidebar_item = sidebar.add_item;
        sidebar.add_item = function (container, item, ...args) {
            if (item.class?.includes("sidebar-notification")) item.onClick = () => {
                const dropdown = this.wrapper.find(".dropdown-notifications");
                dropdown.toggleClass("hidden");
                if (!dropdown.hasClass("hidden")) dropdown.trigger("show.bs.dropdown");
            };
            const result = add_sidebar_item.call(this, container, item, ...args);
            if (item.link_to === "Moniepoint Settings") {
                container.find("a[href^='/desk/moniepoint-settings'] .sidebar-item-icon").empty()
                    .append($("<img class='k3ls-moniepoint-mark' alt='' src='/assets/moniepoint_pos/images/moniepoint-mark.svg'>"));
            }
            return result;
        };
        const resolve = sidebar.resolve_sidebar;
        const shop = ["Item", "Customer", "K3LS Repair", "shop-repairs", "POS Invoice", "Sales Invoice", "point-of-sale"];
        const owner = ["Supplier", "Purchase Invoice", "Payment Entry", "POS Profile", "Account", "shop-accounts", "shop-profit", "shop-money-owed", "shop-staff", "permission-manager", "User", "Moniepoint Settings", "Moniepoint Terminal", "Moniepoint Transaction"];
        sidebar.resolve_sidebar = function (entity, module) {
            const url_sidebar = new URLSearchParams(location.search).get("sidebar")?.replace(/^"|"$/g, "");
            if (frappe.get_route()?.[0] === "permission-manager" && this.all_sidebar_items["k3ls owner"]) return "K3LS Owner";
            if (["POS Invoice", "Sales Invoice"].includes(entity) && frappe.get_route()?.[0] === "Form"
                && frappe.get_route()?.[2]?.startsWith("new-") && !url_sidebar && !frappe.route_options?.sidebar
                && frappe.user.has_role("System Manager") && this.all_sidebar_items["k3ls owner"]) return "K3LS Owner";
            if (["POS Invoice", "Item", "shop-repairs", "K3LS Repair"].includes(entity)
                && (frappe.route_options?.sidebar || url_sidebar || this.sidebar_title) === "K3LS Owner"
                && this.all_sidebar_items["k3ls owner"]) return "K3LS Owner";
            const title = shop.includes(entity) ? "K3LS Shop" : owner.includes(entity) ? "K3LS Owner" : null;
            if (title && this.all_sidebar_items[title.toLowerCase()]) return title;
            return resolve.call(this, entity, module);
        };
    }
})();
