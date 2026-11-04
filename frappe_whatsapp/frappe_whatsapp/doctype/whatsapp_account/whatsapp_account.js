// Copyright (c) 2025, Shridhar Patil and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Account", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Send lesson_reminder test"), () => {
				const dialog = new frappe.ui.Dialog({
					title: __("Send lesson_reminder test"),
					fields: [
						{ fieldname: "to", label: __("Recipient phone with country code"), fieldtype: "Data", reqd: 1 },
						{ fieldname: "parent_name", label: __("Parent name"), fieldtype: "Data", reqd: 1 },
						{ fieldname: "student_name", label: __("Student name"), fieldtype: "Data", reqd: 1 },
						{ fieldname: "lesson_date", label: __("Lesson date"), fieldtype: "Data", reqd: 1 },
						{ fieldname: "lesson_time", label: __("Lesson time"), fieldtype: "Data", reqd: 1 },
					],
					primary_action_label: __("Send test"),
					primary_action(values) {
						frappe.call({
							method: "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_account.whatsapp_account.send_template_test",
							args: { account_name: frm.doc.name, ...values },
							freeze: true,
							freeze_message: __("Sending WhatsApp template..."),
							callback(r) {
								if (!r.exc) {
									dialog.hide();
									frappe.show_alert({ message: __("Test sent and logged as {0}", [r.message.name]), indicator: "green" });
								}
							},
						});
					},
				});
				dialog.show();
			});

			frm.add_custom_button(__("Subscribe App to Webhooks"), () => {
				frappe.confirm(
					__("Subscribe this app to webhooks for WhatsApp Business Account {0}?", [
						frm.doc.business_id || frm.doc.account_name,
					]),
					() => {
						frm.call({
							doc: frm.doc,
							method: "subscribe_app",
							freeze: true,
							freeze_message: __("Subscribing app to webhooks..."),
							callback: (r) => {
								if (!r.exc) {
									frappe.show_alert({
										message: __("App subscribed to webhooks"),
										indicator: "green",
									});
								}
							},
						});
					}
				);
			});
		}
	},
});
