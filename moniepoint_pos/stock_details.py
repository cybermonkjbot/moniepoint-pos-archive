"""Workbook facts as master metadata, not opening-stock valuation."""
import frappe


def apply_workbook_details():
    for number in range(1, 12):
        item = frappe.get_doc("Item", f"K3LS-ITM-{number:04d}")
        values = {"custom_k3ls_ownership": "K3LS Owned"}
        if number == 1:
            values.update({
                "custom_k3ls_model": "Surface Book 2", "custom_k3ls_serial": "010988293157",
                "custom_k3ls_colour": "silver", "custom_k3ls_acquired_on": "2026-07-27",
                "custom_k3ls_acquisition_type": "Swap / Trade-in",
                "custom_k3ls_purchase_cost": 350000, "custom_k3ls_landing_cost": 5000,
                "custom_k3ls_arrival_condition": "Broken screen, recorded in the source item register.",
                "custom_k3ls_configuration": "Intel Core i7-8650U; 16 GB RAM; 512 GB nominal storage, SSD type unverified; GTX 1050 2 GB; Windows 11 Pro; pen and touch supported.",
            })
        else:
            values.update({
                "custom_k3ls_model": "MOSW115" if number <= 6 else "Wireless mouse, model unspecified",
                "custom_k3ls_configuration": "Wireless; Bluetooth; rechargeable" if number <= 6 else "Wireless; other specifications not provided",
                "custom_k3ls_acquisition_type": "Supplier Purchase",
                "custom_k3ls_purchase_cost": 6500 if number <= 6 else 5500,
            })
        for field, value in values.items():
            if item.get(field) in (None, "", 0):
                item.set(field, value)
        item.save()
