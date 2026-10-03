/* K3LS presentation only. Keep ERPNext validation, permissions and record storage. */
(() => {
    const config = frappe.boot.k3ls_shop_ui;
    if (!config) return;
    document.body.classList.add("k3ls-shop");
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
        {label: "Stock", icon: "package", route: ["List", "Item"], doctype: "Item", matches: ["Item"]},
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
        const route = frappe.get_route();
        const entity = ["Form", "List", "Tree"].includes(route[0]) ? route[1] : route[0];
        const shop_screen = Boolean(config[entity] || ["point-of-sale", "shop-repairs", "shop-accounts", "shop-money-owed", "shop-staff", "User", "Workspaces", "K3LS Shop", "K3LS Owner"].includes(entity));
        document.body.classList.toggle("k3ls-app-screen", shop_screen);
        const owner_screen = ["Supplier", "Purchase Invoice", "Payment Entry", "POS Profile", "Account", "shop-accounts", "shop-money-owed", "shop-staff", "User", "Moniepoint Settings", "Moniepoint Terminal", "Moniepoint Transaction", "K3LS Owner"]
            .includes(entity) || (entity === "Workspaces" && route[1] === "K3LS Owner")
            || (entity === "POS Invoice" && frappe.app?.sidebar?.sidebar_title === "K3LS Owner");
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
        "Purchase Invoice": "Purchase", "Sales Invoice": "Invoice", "Payment Entry": "Payment",
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
    Object.assign(page_titles, { "Payment Entry": "Money in/out", "Payment": "Money in/out", "Supplier": "Suppliers", "Customer": "Customers", "Item": "Products", "Product": "Products", "K3LS Repair": "Repairs", "Repair": "Repairs", "Purchase Invoice": "Purchases", "Purchase": "Purchases", "POS Invoice": "Sales", "Sale": "Sales", "Sales Invoice": "Invoices", "Invoice": "Invoices", "Account": "Accounts", "Point of Sale": "POS", "POS": "POS", "Repairs": "Repairs", "New repair": "New repair", "User": "Users", "Money owed": "Money owed" });
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
                frm.$wrapper.toggleClass("k3ls-no-files", ["Moniepoint Settings", "Moniepoint Terminal", "Moniepoint Transaction", "POS Profile", "Account"].includes(doctype));
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
                if (doctype === "POS Profile" && frm.doc.name === "K3LS Shop" && !frm.is_new()) {
                    frm.page.set_title(__("Checkout settings"));
                    const grid = frm.fields_dict.payments.$wrapper;
                    if (!frm.k3ls_payment_summary) frm.k3ls_payment_summary = $("<section class='k3ls-checkout-methods' aria-label='Payment methods'></section>").insertBefore(grid);
                    const summary = frm.k3ls_payment_summary.empty().toggle(!reveal);
                    for (const payment of frm.doc.payments || []) {
                        const card = $("<div class='k3ls-checkout-method'></div>").appendTo(summary);
                        if (payment.mode_of_payment === "Moniepoint MFB") {
                            $("<img alt='' src='/assets/moniepoint_pos/images/moniepoint-mark.svg'>").appendTo(card);
                        } else $("<span aria-hidden='true'></span>").html(frappe.utils.icon("wallet", "lg")).appendTo(card);
                        const text = $("<div></div>").appendTo(card);
                        $("<strong></strong>").text(__(payment.mode_of_payment)).appendTo(text);
                        $("<small></small>").text(__(payment.default ? "Default" : payment.mode_of_payment === "Moniepoint MFB" ? "Card or transfer" : "")).appendTo(text);
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
                    const hidden = reveal ? frm.k3ls_original_hidden[name] : Number(!needs_input);
                    set_property(name, "hidden", hidden);
                }
                if (doctype === "Item" && !reveal) {
                    set_property("stock_uom", "hidden", frm.doc.stock_uom === "Nos" ? 1 : 0);
                    set_property("disabled", "label", "Stop selling this product");
                } else if (doctype === "Item") {
                    set_property("stock_uom", "hidden", frm.k3ls_original_hidden.stock_uom);
                }
                if (doctype === "Item") {
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
        const owner = ["Supplier", "Purchase Invoice", "Payment Entry", "POS Profile", "Account", "shop-accounts", "shop-money-owed", "shop-staff", "User", "Moniepoint Settings", "Moniepoint Terminal", "Moniepoint Transaction"];
        sidebar.resolve_sidebar = function (entity, module) {
            if (entity === "POS Invoice" && this.sidebar_title === "K3LS Owner"
                && this.all_sidebar_items["k3ls owner"]) return "K3LS Owner";
            const title = shop.includes(entity) ? "K3LS Shop" : owner.includes(entity) ? "K3LS Owner" : null;
            if (title && this.all_sidebar_items[title.toLowerCase()]) return title;
            return resolve.call(this, entity, module);
        };
    }
})();
