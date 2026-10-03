// Keep ERPNext's till, open-session lookup and checkout.
frappe.pages["point-of-sale"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper, title: __("Point of Sale"), single_column: true, hide_sidebar: true,
    });
    frappe.require("point-of-sale.bundle.js", function () {
        const escape = frappe.utils.escape_html;
        class ProductSelector extends erpnext.PointOfSale.ItemSelector {
            async get_parent_item_group() {
                this.item_group = this.parent_item_group = null;
            }

            async load_items_data() {
                await this.item_ready_group;
                return this.filter_items({search_term: this.search_field.get_value() || ""});
            }

            prepare_dom() {
                super.prepare_dom();
                this.$component.find(".filter-section .label").text(__("Products"));
                const categories = $("<div class='k3ls-pos-categories' role='group' aria-label='Product category'></div>")
                    .insertAfter(this.$component.find(".filter-section"));
                for (const [value, label] of [[null, "All products"], ["Laptop", "Laptops"], ["Accessories", "Accessories"]]) {
                    $("<button type='button'></button>").text(__(label)).attr("aria-pressed", String(!value))
                        .toggleClass("selected", !value).on("click", () => {
                            this.item_group = value;
                            categories.find("button").attr("aria-pressed", "false").removeClass("selected");
                            categories.find("button").filter(function () {return $(this).text() === __(label);})
                                .attr("aria-pressed", "true").addClass("selected");
                            this.filter_items({search_term: this.search_field.get_value() || ""});
                        }).appendTo(categories);
                }
            }

            make_search_bar() {
                super.make_search_bar();
                this.search_field.$input.attr({placeholder: __("Find a product or scan a barcode"), "aria-label": __("Find products")});
                this.search_field.$wrapper.find(".tooltip-content").remove();
                this.$component.find(".item-group-field").hide();
                // A name search must not add a product before it is chosen.
                this.auto_add_item = false;
            }

            get_items({start=0, page_length=40, search_term=""}) {
                return frappe.call({method: "moniepoint_pos.pos.products", type: "GET",
                    args: {start, page_length, search_term, item_group: this.item_group, pos_profile: this.pos_profile}});
            }

            async filter_items({search_term=""}={}) {
                const request = this.shop_search_request = (this.shop_search_request || 0) + 1;
                this.start_item_loading_animation();
                try {
                    const {message} = await this.get_items({search_term});
                    if (request !== this.shop_search_request) return;
                    this.render_item_list(message?.items || []);
                } catch (error) {
                    if (request !== this.shop_search_request) return;
                    this.$items_container.empty().append($("<p></p>").text(__("Products could not load.")));
                    $("<button type='button' class='btn btn-default'></button>").text(__("Retry"))
                        .on("click", () => this.filter_items({search_term})).appendTo(this.$items_container);
                } finally {if (request === this.shop_search_request) this.stop_item_loading_animation();}
            }

            render_item_list(items) {
                this.items = items || [];
                this.$items_container.empty().removeClass("hide-item-image show-item-image items-not-found").addClass("k3ls-product-grid");
                if (!this.items.length) {
                    this.$items_container.append($("<div class='k3ls-shop-empty'></div>")
                        .html(`<span aria-hidden="true">${frappe.utils.icon("package", "lg")}</span><h2>${escape(__("No products found"))}</h2>`));
                    return;
                }
                for (const item of this.items) this.$items_container.append(this.get_item_html(item));
            }

            get_item_html(item) {
                const available = flt(item.actual_qty) > 0;
                const priced = item.price_list_rate !== null && item.price_list_rate !== undefined;
                const button = $("<button type='button' class='item-wrapper k3ls-product-card'></button>")
                    .prop("disabled", !available || !priced);
                for (const [key, value] of Object.entries({"item-code": item.item_code, "serial-no": item.serial_no,
                    "batch-no": item.batch_no, uom: item.uom, rate: item.price_list_rate, "stock-uom": item.stock_uom})) {
                    if (value != null) button.attr(`data-${key}`, value);
                }
                button.html(`<span class="k3ls-product-symbol" aria-hidden="true">${frappe.utils.icon(item.item_code === "K3LS-ITM-0001" ? "laptop" : "package", "lg")}</span>
                    <strong>${escape(item.item_name)}</strong><small>${escape(item.item_code)}</small>
                    <span class="k3ls-product-price">${escape(priced ? format_currency(item.price_list_rate, item.currency) : __("Price not set"))}</span>
                    <span class="k3ls-product-stock">${escape(available ? __("{0} in stock", [item.actual_qty]) : __("Out of stock"))}</span>`);
                if (item.item_image) {
                    let image_url;
                    try {image_url = new URL(item.item_image, window.location.origin);} catch (error) {}
                    if (image_url && ["http:", "https:"].includes(image_url.protocol)) {
                        const symbol = button.find(".k3ls-product-symbol");
                        const photo = $("<img class='k3ls-product-photo' alt='' loading='lazy'>")
                            .attr("src", image_url.href).prependTo(button);
                        symbol.hide();
                        photo.on("error", () => {photo.remove(); symbol.show();});
                    }
                }
                return button;
            }
        }

        class K3LSController extends erpnext.PointOfSale.Controller {
            init_item_selector() {
                if (this.pos_profile !== "K3LS Shop") return super.init_item_selector();
                this.item_selector = new ProductSelector({wrapper: this.$components_wrapper, pos_profile: this.pos_profile,
                    settings: this.settings, events: {item_selected: args => this.on_cart_update(args), get_frm: () => this.frm || {}}});
            }

            prepare_dom() {
                super.prepare_dom();
                if (this.pos_profile === "K3LS Shop") this.$components_wrapper.addClass("k3ls-pos-app");
            }

            prepare_btns() {
                super.prepare_btns();
                if (this.pos_profile !== "K3LS Shop") return;
                this.page.add_inner_button(__("Repairs"), () => frappe.set_route("shop-repairs"));
            }

            prepare_menu() {
                super.prepare_menu();
                if (this.pos_profile === "K3LS Shop") this.page.add_menu_item(__("Recent sales"), () => this.toggle_recent_order());
            }

            init_item_cart() {
                super.init_item_cart();
                if (this.pos_profile !== "K3LS Shop") return;
                // Native buttons retain the core delegated click handlers.
                this.cart.$component.find(".checkout-btn, .edit-cart-btn").each(function () {
                    const old = $(this);
                    $("<button type='button'></button>").attr({class: old.attr("class"), style: old.attr("style") || ""})
                        .html(old.html()).replaceAll(old);
                });
                const highlight = this.cart.highlight_checkout_btn.bind(this.cart);
                this.cart.highlight_checkout_btn = enabled => {
                    highlight(enabled);
                    this.cart.$component.find(".checkout-btn").prop("disabled", !enabled);
                };
                this.cart.highlight_checkout_btn(false);
            }

            init_payments() {
                super.init_payments();
                if (this.pos_profile !== "K3LS Shop") return;
                const payment = this.payment;
                const render_modes = payment.render_payment_mode_dom.bind(payment);
                payment.render_payment_mode_dom = () => {
                    render_modes();
                    if (!payment.$payment_modes.is(":visible")) return;
                    for (const row of this.frm.doc.payments || []) {
                        const mode = payment.sanitize_mode_of_payment(row.mode_of_payment);
                        const card = payment.$payment_modes.find(`.mode-of-payment[data-mode='${mode}']`);
                        // Old drafts can contain other methods. Never hide money already entered.
                        if (!["Cash", "Moniepoint MFB"].includes(row.mode_of_payment) && !flt(row.amount)) {
                            card.parent().remove(); continue;
                        }
                        card.attr({role: "button", tabindex: "0", "aria-label": __(row.mode_of_payment)});
                        card.contents().filter(function () {return this.nodeType === 3;}).first().replaceWith(
                            $("<span class='k3ls-payment-name'></span>").text(__(row.mode_of_payment)));
                        if (row.mode_of_payment === "Moniepoint MFB") {
                            $("<img class='k3ls-payment-mark' alt='' src='/assets/moniepoint_pos/images/moniepoint-mark.svg'>").prependTo(card);
                        }
                        card.on("keydown.k3ls", event => {
                            if (event.target !== card[0] || !["Enter", " "].includes(event.key)) return;
                            event.preventDefault(); card.trigger("click");
                        });
                    }
                    if (!payment.selected_mode) {
                        const cash = payment[`${payment.sanitize_mode_of_payment("Cash")}_control`];
                        if (cash) {payment.selected_mode = cash; payment.highlight_selected_mode();}
                    }
                };
                const old = this.payment.$component.find(".submit-order-btn");
                $("<button type='button'></button>").attr("class", old.attr("class")).html(old.html()).replaceAll(old);
                let submitting = false;
                this.payment.events.submit_invoice = async () => {
                    if (submitting) return;
                    const doc = this.frm.doc;
                    const total = flt(doc.rounded_total) || flt(doc.grand_total);
                    const left = flt(total - flt(doc.paid_amount), 2);
                    if (left > 0 && (!doc.customer || doc.customer === "K3LS Walk-in Customer" || !doc.contact_mobile || !doc.due_date)) {
                        this.ask_credit_customer(left);
                        return;
                    }
                    const confirm = new frappe.ui.Dialog({title: __(left > 0 ? "Save part-paid sale" : "Finish sale"),
                        fields: [{fieldname: "amounts", fieldtype: "HTML", options: `<p>${escape(__("Received {0}", [format_currency(doc.paid_amount, doc.currency)]))}</p>
                            ${left > 0 ? `<p>${escape(__("{0} owes {1}, due {2}", [doc.customer, format_currency(left, doc.currency), frappe.datetime.str_to_user(doc.due_date)]))}</p>` : ""}
                            <p class="text-muted">${escape(__("Confirm money already received. This does not charge a terminal."))}</p>`}],
                        primary_action_label: __("Confirm sale"), primary_action: async () => {
                            confirm.disable_primary_action(); submitting = true;
                            try {
                                await this.save_shop_invoice("Submit");
                                confirm.hide(); this.toggle_components(false); this.toggle_submitted_invoice_summary(true);
                                frappe.show_alert(__("Sale saved"));
                            } catch (error) {
                                frappe.msgprint(error.message || __("Sale could not save. Check the sale and try again."));
                            } finally {submitting = false; confirm.enable_primary_action();}
                        }});
                    confirm.show();
                };
            }

            async save_shop_invoice(action) {
                const frm = this.frm;
                frm.validate_form_action(action);
                frappe.validated = true;
                if (action === "Submit") await frm.script_manager.trigger("before_submit");
                await frm.script_manager.trigger("validate");
                await frm.script_manager.trigger("before_save");
                if (!frappe.validated || !frappe.ui.form.check_mandatory(frm)) {
                    throw new Error(__("Check the sale details before saving."));
                }
                // The checkout sheet already confirms the action. Keep core save
                // and server validation without a second generic confirmation.
                await new Promise((resolve, reject) => {
                    frappe.ui.form.save(frm, action, response => {
                        if (response.exc || (action === "Submit" ? frm.doc.docstatus !== 1 : frm.is_dirty())) {
                            reject(new Error(__("Sale was not saved. Check the message and try again.")));
                            return;
                        }
                        resolve();
                    });
                });
                await frm.script_manager.trigger("after_save");
                if (action === "Submit") await frm.script_manager.trigger("on_submit");
            }

            ask_credit_customer(left) {
                const doc = this.frm.doc;
                const dialog = new frappe.ui.Dialog({title: __("Who will pay the balance?"), fields: [
                    {fieldname: "balance", fieldtype: "HTML", options: `<p>${escape(__("Left to pay {0}", [format_currency(left, doc.currency)]))}</p>`},
                    {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer", reqd: 1,
                        default: doc.customer === "K3LS Walk-in Customer" ? "" : doc.customer, get_query: () => ({filters: {name: ["!=", "K3LS Walk-in Customer"], disabled: 0}})},
                    {fieldname: "phone", label: __("Phone"), fieldtype: "Data", reqd: 1, default: doc.contact_mobile},
                    {fieldname: "due_date", label: __("Pay by"), fieldtype: "Date", reqd: 1, default: doc.due_date || frappe.datetime.get_today()}
                ], primary_action_label: __("Save details"), primary_action: async ({customer, phone, due_date}) => {
                    if (customer === "K3LS Walk-in Customer") {frappe.msgprint(__("Choose the customer's name.")); return;}
                    dialog.disable_primary_action();
                    try {
                        const payments = this.frm.doc.payments.map(row => ({name: row.name, mode: row.mode_of_payment, amount: row.amount}));
                        const currency = this.frm.doc.currency;
                        await this.frm.set_value("customer", customer);
                        await frappe.after_ajax();
                        if (this.frm.doc.currency !== currency) throw new Error(__("Currency changed. Recheck the payment amounts."));
                        await this.frm.set_value({contact_mobile: phone, due_date});
                        for (const saved of payments) {
                            const row = this.frm.doc.payments.find(row => row.name === saved.name && row.mode_of_payment === saved.mode);
                            if (!row) throw new Error(__("Payment methods changed. Recheck the payment amounts."));
                            await frappe.model.set_value(row.doctype, row.name, "amount", saved.amount);
                        }
                        await this.save_shop_invoice("Save");
                        dialog.hide(); this.cart.load_invoice(); this.payment.checkout();
                    } catch (error) {
                        frappe.msgprint(error.message || __("Details could not save. Check them and try again."));
                    } finally {dialog.enable_primary_action();}
                }});
                dialog.show();
            }

            check_outdated_pos_opening_entry() {
                if (this.pos_profile !== "K3LS Shop") return super.check_outdated_pos_opening_entry();
                // A new calendar day does not reconcile the physical cash drawer.
            }

            async make_app() {
                if (this.invoice_fields_ready) await this.invoice_fields_ready;
                super.make_app();
                if (this.pos_profile !== "K3LS Shop") return;
                this.setup_phone_pos();
                this.show_shop_date();
                if (!this.shop_date_timer) {
                    this.shop_date_timer = setInterval(() => {
                        if (frappe.get_route()[0] === "point-of-sale") this.show_shop_date();
                    }, 60000);
                }
            }

            setup_phone_pos() {
                const shell = this.$components_wrapper;
                this.phone_panel = "products";
                const tabs = $("<nav class='k3ls-pos-phone-tabs' aria-label='Sale'></nav>").prependTo(shell);
                const products = $("<button type='button'></button>").text(__("Products")).appendTo(tabs);
                const basket = $("<button type='button'></button>").appendTo(tabs);
                const back = $("<button type='button' class='k3ls-pos-phone-back'></button>")
                    .text(__("Back to basket")).prependTo(shell);
                const preview = $("<button type='button' class='k3ls-pos-phone-basket'></button>").appendTo(shell);
                const select = panel => {
                    this.phone_panel = panel;
                    this.sync_phone_pos();
                };
                products.on("click", () => select("products"));
                basket.on("click", () => select("basket"));
                preview.on("click", () => select("basket"));
                back.on("click", () => {
                    if (this.payment.$component[0].style.display !== "none") this.payment.edit_cart();
                    if (this.item_details.$component[0].style.display !== "none") this.item_details.events.close_item_details();
                    select("basket");
                });
                this.phone_controls = {products, basket, back, preview};
                const totals = this.cart.update_totals_section.bind(this.cart);
                this.cart.update_totals_section = (...args) => {
                    const result = totals(...args);
                    this.sync_phone_pos();
                    return result;
                };
                // Listen to the core controller's panel changes, including serial selection,
                // checkout, saved sales and receipts. No duplicate sale or payment state.
                this.phone_observer?.disconnect();
                this.phone_observer = new MutationObserver(() => this.sync_phone_pos());
                shell.children("section").each((index, section) => {
                    this.phone_observer.observe(section, {attributes: true, attributeFilter: ["style"]});
                });
                this.sync_phone_pos();
            }

            sync_phone_pos() {
                if (!this.phone_controls) return;
                const shown = component => Boolean(component?.$component?.[0]
                    && getComputedStyle(component.$component[0]).display !== "none");
                let panel = this.phone_panel || "products";
                if (shown(this.recent_order_list)) panel = "history";
                else if (shown(this.payment)) panel = "payment";
                else if (shown(this.item_details)) panel = "details";
                else if (this.frm?.doc.docstatus === 1 && shown(this.order_summary)) panel = "receipt";
                const {products, basket, back, preview} = this.phone_controls;
                const count = (this.frm?.doc.items || []).reduce((sum, item) => sum + flt(item.qty), 0);
                const total = flt(this.frm?.doc.rounded_total) || flt(this.frm?.doc.grand_total);
                this.$components_wrapper.attr("data-phone-panel", panel);
                products.attr("aria-pressed", String(panel === "products"));
                basket.text(__("Basket ({0})", [count])).attr("aria-pressed", String(panel === "basket"));
                preview.empty().append($("<span></span>").text(__("View basket ({0})", [count])))
                    .append($("<strong></strong>").text(format_currency(total, this.frm?.doc.currency || "NGN")));
                back.text(__(panel === "details" ? "Back to basket" : "Edit basket"));
            }

            fetch_invoice_fields() {
                this.invoice_fields_ready = super.fetch_invoice_fields();
                return this.invoice_fields_ready;
            }

            show_shop_date() {
                const today = frappe.datetime.system_datetime().slice(0, 10);
                const opened = this.pos_opening_time.slice(0, 10);
                const text = today === opened ? __("Till open") : __("Till opened {0}", [frappe.datetime.str_to_user(opened)]);
                // Frappe 16's page header has no subtitle element.
                if (!this.shop_date_label) {
                    this.shop_date_label = $("<p class='text-muted small mb-2 k3ls-shop-date'></p>").prependTo(this.page.main);
                }
                this.shop_date_label.text(`${frappe.datetime.str_to_user(today)} · ${text}`);
            }

            async create_opening_voucher() {
                const { message: defaults } = await frappe.call({
                    method: "moniepoint_pos.shop_setup.opening_defaults", type: "GET",
                });
                if (!defaults) return super.create_opening_voucher();
                const dialog = new frappe.ui.Dialog({
                    title: __("Open K3LS Shop"),
                    static: true,
                    fields: [
                        { fieldname: "cash", fieldtype: "Currency", label: __("Cash in drawer, NGN"),
                            reqd: 1, description: __("Use 0 for an empty drawer.") },
                    ],
                    primary_action_label: __("Start selling"),
                    secondary_action_label: __("Back"),
                    secondary_action() { dialog.hide(); frappe.set_route("desktop"); },
                    primary_action: async ({ cash }) => {
                        if (cash == null || cash === "" || !Number.isFinite(Number(cash)) || flt(cash) < 0) {
                            frappe.msgprint(__("Enter the cash in the drawer, or 0 if it is empty."));
                            return;
                        }
                        const balance_details = defaults.payments.map(mode => ({
                            mode_of_payment: mode, opening_amount: mode === defaults.cash_method ? flt(cash) : 0,
                        }));
                        dialog.disable_primary_action();
                        try {
                            // Another tab may have opened the till while this dialog was open.
                            const active = await this.fetch_opening_entry();
                            if (active.message?.length) {
                                dialog.hide();
                                await this.prepare_app_defaults(active.message[0]);
                                return;
                            }
                            const result = await frappe.call({
                                method: "erpnext.selling.page.point_of_sale.point_of_sale.create_opening_voucher",
                                type: "POST", args: { company: defaults.company, pos_profile: defaults.profile, balance_details },
                                freeze: true,
                            });
                            if (result.message && !result.exc) {
                                dialog.hide();
                                await this.prepare_app_defaults(result.message);
                            }
                        } finally { dialog.enable_primary_action(); }
                    },
                });
                dialog.show();
            }
        }
        wrapper.pos = new K3LSController(wrapper);
        window.cur_pos = wrapper.pos;
    });
};

// New or resumed draft sales use the shop's date when saved, including across midnight.
function k3ls_set_sale_date(frm) {
    if (window.cur_pos?.frm !== frm || frm.doc.docstatus !== 0 || frm.doc.pos_profile !== "K3LS Shop") return;
    const now = frappe.datetime.system_datetime();
    return frm.set_value({ posting_date: now.slice(0, 10), posting_time: now.slice(11), set_posting_time: 1 });
}
frappe.ui.form.on("POS Invoice", { before_save: k3ls_set_sale_date, before_submit: k3ls_set_sale_date });
