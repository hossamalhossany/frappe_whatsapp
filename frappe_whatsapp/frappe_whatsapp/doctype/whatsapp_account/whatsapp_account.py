# Copyright (c) 2025, Shridhar Patil and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
from frappe.integrations.utils import make_post_request
from frappe.model.document import Document


class WhatsAppAccount(Document):
	def before_insert(self):
		if not self.webhook_verify_token:
			self.webhook_verify_token = frappe.generate_hash(length=40)

	def validate(self):
		self.webhook_callback_url = (
			f"{frappe.utils.get_url()}/api/method/"
			"frappe_whatsapp.utils.webhook.webhook"
		)

	def on_update(self):
		"""Check there is only one default of each type."""
		self.there_must_be_only_one_default()

	def there_must_be_only_one_default(self):
		"""If current WhatsApp Account is default, un-default all other accounts."""
		for field in ("is_default_incoming", "is_default_outgoing"):
			if not self.get(field):
				continue

			for whatsapp_account in frappe.get_all("WhatsApp Account", filters={field: 1}):
				if whatsapp_account.name == self.name:
					continue

				whatsapp_account = frappe.get_doc("WhatsApp Account", whatsapp_account.name)
				whatsapp_account.set(field, 0)
				whatsapp_account.save()

	@frappe.whitelist()
	def subscribe_app(self):
		"""Subscribe this app to webhooks for the WhatsApp Business Account.

		Required after phone number registration to receive incoming messages.
		Calls POST /{version}/{business_id}/subscribed_apps on the Graph API.
		"""
		for field in ("url", "version", "business_id"):
			if not self.get(field):
				frappe.throw(_("{0} is required to subscribe the app").format(
					frappe.bold(self.meta.get_label(field))
				))

		token = self.get_password("token")
		if not token:
			frappe.throw(_("Access token is required to subscribe the app"))

		endpoint = f"{self.url}/{self.version}/{self.business_id}/subscribed_apps"
		headers = {
			"authorization": f"Bearer {token}",
			"content-type": "application/json",
		}

		try:
			response = make_post_request(endpoint, headers=headers)
		except Exception as e:
			error_message = str(e)
			if frappe.flags.integration_request:
				err = frappe.flags.integration_request.json().get("error", {})
				if err:
					error_message = err.get("message") or err.get("Error") or error_message
			frappe.throw(_("Failed to subscribe app to webhooks: {0}").format(error_message))

		if not response.get("success"):
			frappe.throw(_("Subscription was not successful: {0}").format(frappe.as_json(response)))

		frappe.logger().info(
			f"WhatsApp app subscribed to webhooks for business_id={self.business_id}"
		)
		return response

	@frappe.whitelist()
	def send_template_test(self, to, parent_name, student_name, lesson_date, lesson_time):
		"""Send a lesson_reminder test and persist it for webhook status updates."""
		if not self.has_permission("write"):
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		if self.status != "Active":
			frappe.throw(_("Activate this WhatsApp Account before sending a test"))
		for field in ("url", "version", "phone_id"):
			if not self.get(field):
				frappe.throw(_("{0} is required").format(self.meta.get_label(field)))
		token = self.get_password("token")
		if not token:
			frappe.throw(_("Access token is required"))

		to = "".join(char for char in str(to or "") if char.isdigit())
		if not to:
			frappe.throw(_("Enter the recipient phone number with country code"))
		values = [parent_name, student_name, lesson_date, lesson_time]
		if any(not str(value or "").strip() for value in values):
			frappe.throw(_("Fill in all four lesson_reminder template values"))
		payload = {
			"messaging_product": "whatsapp",
			"to": to,
			"type": "template",
			"template": {
				"name": "lesson_reminder",
				"language": {"code": "en"},
				"components": [{
					"type": "body",
					"parameters": [{"type": "text", "text": str(value)} for value in values],
				}],
			},
		}
		try:
			response = make_post_request(
				f"{self.url.rstrip('/')}/{self.version}/{self.phone_id}/messages",
				headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
				data=json.dumps(payload),
			)
			message_id = response["messages"][0]["id"]
		except Exception:
			integration_request = frappe.flags.get("integration_request")
			error = {}
			if integration_request:
				try:
					error = integration_request.json().get("error", {})
				except Exception:
					pass
			frappe.get_doc({
				"doctype": "WhatsApp Notification Log",
				"template": "lesson_reminder test",
				"meta_data": frappe.as_json(error or {"error": "Request failed; see Error Log"}),
			}).insert(ignore_permissions=True)
			frappe.log_error(title="WhatsApp template test failed", message=frappe.as_json(error))
			frappe.throw(_(error.get("message") or "WhatsApp template send failed; see Error Log"))

		message = frappe.get_doc({
			"doctype": "WhatsApp Message",
			"type": "Outgoing",
			"to": to,
			"message": "lesson_reminder",
			"message_type": "Template",
			"template": frappe.db.get_value(
				"WhatsApp Templates", {"actual_name": "lesson_reminder", "language_code": "en"}, "name"
			),
			"template_parameters": frappe.as_json(values),
			"message_id": message_id,
			"content_type": "text",
			"use_template": 1,
			"whatsapp_account": self.name,
		}).insert(ignore_permissions=True)
		return {"name": message.name, "message_id": message_id}
