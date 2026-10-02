// Keep ERPNext's till, open-session lookup and checkout.
frappe.pages["point-of-sale"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper, title: __("Point of Sale"), single_column: true, hide_sidebar: true,
    });
    frappe.require("point-of-sale.bundle.js", function () {
        class K3LSController extends erpnext.PointOfSale.Controller {
            check_outdated_pos_opening_entry() {
                if (this.pos_profile !== "K3LS Shop") return super.check_outdated_pos_opening_entry();
                // A new calendar day does not reconcile the physical cash drawer.
            }

            make_app() {
                super.make_app();
                if (this.pos_profile !== "K3LS Shop") return;
                this.show_shop_date();
                if (!this.shop_date_timer) {
                    this.shop_date_timer = setInterval(() => {
                        if (frappe.get_route()[0] === "point-of-sale") this.show_shop_date();
                    }, 60000);
                }
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
