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

    if (!frappe.boot.k3ls_shop_ui) return;
    const users = frappe.listview_settings.User;
    if (users && !users.k3ls_user_list) {
        users.k3ls_user_list = true;
        users.add_fields = [...new Set([...(users.add_fields || []), "email"])];
        const load_users = users.onload;
        users.onload = function (view) {
            load_users?.call(this, view);
            view.columns = view.columns.filter(column => column.type !== "Field" || column.df.fieldname === "email");
            if (!view.columns.some(column => column.df?.fieldname === "email")) {
                view.columns.push({type: "Field", df: frappe.meta.get_docfield("User", "email")});
            }
            view.render_header(true);
        };
    }
    for (const [doctype, config] of Object.entries(frappe.boot.k3ls_shop_ui)) {
        const settings = frappe.listview_settings[doctype];
        if (!config.search_title || settings.k3ls_unified_search) continue;
        settings.k3ls_unified_search = true;
        const onload = settings.onload;
        settings.onload = function (view) {
            onload?.call(this, view);
            view.page.wrapper.addClass("k3ls-search-list");
            view.page.show_form();
            const input = $("<input type='search' class='form-control'>").attr({
                placeholder: __("Search {0}", [__(config.search_title)]),
                "aria-label": __("Search {0}", [__(config.search_title)]), autocomplete: "off"});
            const area = frappe.k3ls_search_field(input).prependTo(view.page.page_form);
            const clear = $("<button type='button' class='btn btn-default' hidden></button>")
                .attr("aria-label", __("Clear search")).html(frappe.utils.icon("x", "sm")).appendTo(area);
            const detected = $("<div class='k3ls-search-detected' role='status' hidden></div>").insertAfter(area);
            let term = new URLSearchParams(location.search).get("shop_search") || "", timer;
            input.val(term);
            clear.prop("hidden", !term);
            const refresh = () => {
                clearTimeout(timer);
                term = input.val().trim();
                clear.prop("hidden", !term);
                detected.prop("hidden", true);
                view.start = 0;
                view.refresh();
            };
            const parse_route = view.parse_filters_from_route_options;
            view.parse_filters_from_route_options = function () {
                const params = new URLSearchParams(location.search);
                term = params.get("shop_search") || "";
                input.val(term); clear.prop("hidden", !term);
                return parse_route.call(this);
            };
            input.on("input", () => {clearTimeout(timer); timer = setTimeout(refresh, 300);})
                .on("keydown", event => {
                    if (event.key === "Enter") {event.preventDefault(); refresh();}
                    if (event.key === "Escape") {input.val(""); refresh();}
                });
            clear.on("click", () => {input.val(""); refresh(); input.trigger("focus");});
            const clear_filters = view.filter_area.clear;
            view.filter_area.clear = function (...args) {
                if (args[0] !== false) {
                    term = ""; input.val(""); clear.prop("hidden", true); detected.prop("hidden", true);
                }
                return clear_filters.apply(this, args);
            };
            const get_params = view.get_search_params;
            view.get_search_params = function () {
                const params = get_params.call(this);
                if (term) params.set("shop_search", term);
                const sidebar = frappe.app?.sidebar?.sidebar_title;
                if (["Item", "POS Invoice"].includes(doctype) && ["K3LS Shop", "K3LS Owner"].includes(sidebar)) {
                    params.set("sidebar", sidebar);
                }
                return params;
            };
            const get_args = view.get_call_args;
            view.get_call_args = function () {
                const call = get_args.call(this);
                return {...call, method: "moniepoint_pos.list_search.search", args: {...call.args, shop_search: term}};
            };
            const prepare = view.prepare_data;
            view.prepare_data = function (response) {
                const labels = response.message?.search_labels || [];
                if (response.message) delete response.message.search_labels;
                detected.text(labels.map(label => __(label)).join(" · ")).prop("hidden", !labels.length);
                return prepare.call(this, response);
            };
            view.get_count_str = async function () {
                const current = this.data.length;
                const searched = term;
                const filters = JSON.stringify(this.get_args().filters);
                const {message: total} = await frappe.call({method: "moniepoint_pos.list_search.count", type: "GET",
                    args: {...this.get_args(), fields: [], shop_search: searched, limit: this.count_upper_bound}});
                if (searched !== term || filters !== JSON.stringify(this.get_args().filters) || current !== this.data.length) {
                    return this.get_count_str();
                }
                this.total_count = total;
                this.count_without_children = undefined;
                const count = total == null ? "??" : total === this.count_upper_bound
                    ? `${format_number(total - 1, null, 0)}+` : format_number(total, null, 0);
                return __("{0} of {1}", [format_number(current, null, 0), count]);
            };
            const no_result = view.get_no_result_message;
            view.get_no_result_message = function () {
                return term ? `<div class='k3ls-shop-empty'><p>${frappe.utils.escape_html(__("No matches"))}</p></div>`
                    : no_result.call(this);
            };
            // Fold pre-existing standard filters into the regular Filter dialog. Their values remain active.
            for (const field of Object.values(view.page.fields_dict)) field.$wrapper?.hide();
            view.filter_area.$filter_list_wrapper.find(".filter-toggle").hide();
        };
    }
})();
