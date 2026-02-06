import frappe


@frappe.whitelist(allow_guest=True)
def ping():
    """Simple test API to verify custom app is wired correctly."""
    return {
        "status": "ok",
        "app": "vgiskill_custom_app",
        "message": "Custom API is working",
    }


@frappe.whitelist(allow_guest=True)
def get_public_courses():
    """Return a list of published LMS courses for guest/3rd‑party use."""
    courses = frappe.get_all(
        "LMS Course",
        filters={"published": 1},
        fields=[
            "name",
            "title",
            "short_introduction",
            "image",
            "course_price",
            "currency",
            "paid_course",
            "published_on",
            "featured",
        ],
        order_by="published_on desc",
    )
    return {"courses": courses}
