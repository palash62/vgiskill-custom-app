import frappe


@frappe.whitelist(allow_guest=True)
def ping():
    """Simple test API to verify custom app is wired correctly."""
    return {
        "status": "ok1",
        "app": "vgiskill_custom_app",
        "message": "Custom API is working",
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
