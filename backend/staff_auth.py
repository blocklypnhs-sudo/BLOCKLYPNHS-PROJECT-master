from werkzeug.security import check_password_hash, generate_password_hash


# These values are used only when an account has no validation-code hash yet.
# They must never be returned to or rendered by the client.
STAFF_VALIDATION_CODES = {
	'teacher': 'Teacher@2026',
	'ict': 'Tech@2026',
}


def initialize_staff_code_hashes(cursor):
	"""Create missing validation-code hashes for existing staff accounts."""
	for table, role in (('teachers', 'teacher'), ('ict_support', 'ict')):
		cursor.execute(f"SELECT id, staff_code_hash FROM {table}")
		for account in cursor.fetchall():
			stored_hash = account.get('staff_code_hash')
			if not stored_hash or not check_password_hash(stored_hash, STAFF_VALIDATION_CODES[role]):
				cursor.execute(
					f"UPDATE {table} SET staff_code_hash = %s WHERE id = %s",
					(generate_password_hash(STAFF_VALIDATION_CODES[role]), account['id']),
				)


def verify_staff_code(stored_hash, submitted_code):
	"""Check a submitted code without exposing the stored hash."""
	return bool(stored_hash and submitted_code and check_password_hash(stored_hash, submitted_code))
