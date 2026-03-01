import frappe
from frappe.utils import today
from frappe import _

# -------------------------------------------------------------------------
# COUPON VALIDATION API
# -------------------------------------------------------------------------

@frappe.whitelist()
def validate_coupon(coupon_code, amount=None):
    """
    Validate LMS Coupon
    
    Args:
        coupon_code (str): Coupon code entered by user
        amount (float, optional): Cart amount
    
    Returns:
        dict: Coupon validation result
    """

    # ✅ सुरक्षा check
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to apply coupon."))

    # ✅ Fetch Coupon (Schema Correct)
    coupon = frappe.db.get_value(
        "LMS Coupon",
        {"code": coupon_code, "enabled": 1},
        [
            "name",
            "expires_on",
            "discount_type",
            "percentage_discount",
            "fixed_amount_discount",
            "usage_limit",
            "redemption_count"
        ],
        as_dict=True
    )

    if not coupon:
        return {
            "valid": False,
            "message": "Invalid Coupon"
        }

    # ✅ Expiry Check
    if coupon.expires_on and str(today()) > str(coupon.expires_on):
        return {
            "valid": False,
            "message": "Coupon Expired"
        }

    # ✅ Usage Limit Check
    if coupon.usage_limit and coupon.redemption_count >= coupon.usage_limit:
        return {
            "valid": False,
            "message": "Coupon Limit Reached"
        }

    # ✅ Discount Logic
    if coupon.discount_type == "Percentage":
        discount_value = coupon.percentage_discount
    else:
        discount_value = coupon.fixed_amount_discount

    return {
        "valid": True,
        "discount_type": coupon.discount_type,
        "discount_value": discount_value
    }
	
# -------------------------------------------------------------------------
# OPTIONAL: FINAL PRICE CALCULATION API ⭐⭐⭐
# -------------------------------------------------------------------------

@frappe.whitelist()
def calculate_discounted_price(amount, coupon_code=None):
    """
    Calculate final price after coupon
    
    Args:
        amount (float): Original amount
        coupon_code (str, optional): Coupon code
    
    Returns:
        dict: Pricing breakdown
    """

    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."))

    original_amount = float(amount)
    discount_amount = 0

    if coupon_code:
        coupon_result = validate_coupon(coupon_code, original_amount)

        if not coupon_result.get("valid"):
            return coupon_result

        if coupon_result["discount_type"] == "Percentage":
            discount_amount = original_amount * coupon_result["discount_value"] / 100
        else:
            discount_amount = coupon_result["discount_value"]

    final_amount = max(original_amount - discount_amount, 0)

    return {
        "valid": True,
        "original_amount": original_amount,
        "discount_amount": discount_amount,
        "final_amount": final_amount
    }


# -------------------------------------------------------------------------
# OPTIONAL: COUPON USAGE UPDATE API ⭐⭐⭐
# (Call AFTER successful payment)
# -------------------------------------------------------------------------

@frappe.whitelist()
def mark_coupon_used(coupon_code):
    """
    Increment coupon redemption count
    
    Args:
        coupon_code (str): Coupon code
    """

    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."))

    coupon_name = frappe.db.get_value(
        "LMS Coupon",
        {"code": coupon_code},
        "name"
    )

    if not coupon_name:
        frappe.throw(_("Invalid Coupon"))

    frappe.db.sql("""
        UPDATE `tabLMS Coupon`
        SET redemption_count = redemption_count + 1
        WHERE name = %s
    """, coupon_name)

    frappe.db.commit()

    return {
        "success": True,
        "message": "Coupon usage updated"
    }	

# @frappe.whitelist(allow_guest=True)
# def get_public_courses():
#     """Return a list of published LMS courses for guest/3rd‑party use."""
#     courses = frappe.get_all(
#         "LMS Course",
#         filters={"published": 1},
#         fields=[
#             "title",
#             "short_introduction",
#             "image",
#             "course_price",
#             "currency",
#             "paid_course",
#             "published_on",
#             "featured",
#         ],
#         order_by="published_on desc",
#     )
#     return {"courses": courses}


@frappe.whitelist()
def enroll_in_course(course, payment=None):
	"""
	Enroll the current user in a course.
	
	Args:
		course: Course name (document name of LMS Course)
		payment: Optional payment name (LMS Payment document name) for paid courses
	
	Returns:
		Dictionary with enrollment details
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to enroll in the course."))
	
	# Check if course exists and is published
	if not frappe.db.exists("LMS Course", course):
		frappe.throw(_("Course not found: {0}").format(course))
	
	course_doc = frappe.get_doc("LMS Course", course)
	if not course_doc.published:
		frappe.throw(_("This course is not published yet."))
	
	# Check if already enrolled
	enrollment_filters = {"member": frappe.session.user, "course": course}
	if frappe.db.exists("LMS Enrollment", enrollment_filters):
		enrollment_name = frappe.db.get_value("LMS Enrollment", enrollment_filters, "name")
		return {
			"success": True,
			"message": "Already enrolled in this course",
			"enrollment": enrollment_name
		}
	
	# Create enrollment
	enrollment = frappe.new_doc("LMS Enrollment")
	enrollment_data = {
		"member": frappe.session.user,
		"course": course,
	}
	
	# Link payment if provided (for paid courses)
	if payment:
		# Verify payment exists and is valid
		if frappe.db.exists("LMS Payment", payment):
			enrollment_data["payment"] = payment
		else:
			frappe.throw(_("Payment record not found: {0}").format(payment))
	
	enrollment.update(enrollment_data)
	enrollment.save(ignore_permissions=True)
	
	return {
		"success": True,
		"message": "Successfully enrolled in course",
		"enrollment": enrollment.name
	}


@frappe.whitelist(allow_guest=True)
def get_public_courses(filters=None, fields=None, limit_start=0, limit_page_length=20):
	"""
	Get list of published public courses.
	
	Args:
		filters: Dictionary of filters to apply (optional)
		fields: List of fields to return (optional)
		limit_start: Starting index for pagination (default: 0)
		limit_page_length: Number of records per page (default: 20)
	
	Returns:
		List of course dictionaries
	"""
	# Default filters - only published courses
	default_filters = {
		"published": 1,
		"upcoming": 0
	}
	
	# Merge with user-provided filters
	if filters:
		if isinstance(filters, str):
			import json
			filters = json.loads(filters)
		default_filters.update(filters)
	
	# Default fields to return
	default_fields = [
		"name",
		"title",
		"short_introduction",
		"description",
		"image",
		"video_link",
		"card_gradient",
		"category",
		"tags",
		"published_on",
		"featured",
		"course_price",
		"currency",
		"amount_usd",
		"paid_course",
		"enable_certification",
		"lessons",
		"enrollments",
		"rating"
	]
	
	# Use provided fields or defaults
	if fields:
		if isinstance(fields, str):
			import json
			fields = json.loads(fields)
		query_fields = fields
	else:
		query_fields = default_fields
	
	# Get courses
	courses = frappe.get_all(
		"LMS Course",
		filters=default_filters,
		fields=query_fields,
		order_by="published_on desc, creation desc",
		limit_start=limit_start,
		limit_page_length=limit_page_length
	)
	
	# Get total count for pagination
	total_count = frappe.db.count("LMS Course", filters=default_filters)
	
	# Format response
	response = {
		"courses": courses,
		"total_count": total_count,
		"limit_start": limit_start,
		"limit_page_length": limit_page_length
	}
	
	return response

@frappe.whitelist(allow_guest=True)
def get_upcoming_batches(limit=None):
	"""
	Get list of upcoming batches.
	
	Args:
		limit: Number of records to return (optional, defaults to all if not specified)
	
	Returns:
		Dictionary with list of batches
	"""
	from frappe.utils import today
	
	# Set default limit to a high number to get all batches, or use provided limit
	if limit is not None:
		try:
			limit = int(limit)
		except (ValueError, TypeError):
			limit = None
	
	# Build filters - only published batches with start_date >= today
	filters = [
		["start_date", ">=", today()],
		["published", "=", 1]
	]
		
	# Get batches with all relevant fields
	batches = frappe.get_all(
		"LMS Batch",
		filters=filters,
		fields=[
			"name", 
			"title",
			"description",
			"start_date", 
			"end_date", 
			"start_time", 
			"end_time",
			"timezone",
			"seat_count as seat_limit",
			"category",
			"medium",
			"paid_batch",
			"amount",
			"currency",
			"amount_usd"
		],
		order_by="start_date asc",
		limit_page_length=limit if limit else 0  # 0 means no limit
	)
	
	# Get instructor names for each batch
	for batch in batches:
		# Get Course Instructor records linked to this batch
		instructor_records = frappe.get_all(
			"Course Instructor",
			filters={"parent": batch.name, "parenttype": "LMS Batch"},
			fields=["instructor"],
			order_by="idx"
		)
		# Get instructor user names
		instructor_names = []
		for record in instructor_records:
			instructor_user = record.get("instructor")
			if instructor_user:
				# Get full name from User doctype
				full_name = frappe.db.get_value("User", instructor_user, "full_name")
				if full_name:
					instructor_names.append(full_name)
		batch["instructors"] = instructor_names
		batch["instructor"] = ", ".join(instructor_names) if instructor_names else None
	
	return {
		"data": batches,
		"count": len(batches),
		"success": True
	}
