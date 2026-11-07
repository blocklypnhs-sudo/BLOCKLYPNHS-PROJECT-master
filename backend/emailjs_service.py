"""Server-side EmailJS delivery for student one-time passcodes."""
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta


EMAILJS_URL = 'https://api.emailjs.com/api/v1.0/email/send'
OTP_VALIDITY_MINUTES = 10
PASSWORD_RESET_TEMPLATE_ENV = 'EMAILJS_PASSWORD_RESET_TEMPLATE_ID'


def _load_env_file():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    path = os.path.join(root, '.env')
    if not os.path.isfile(path):
        return
    with open(path, encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def emailjs_configured():
    return all(os.environ.get(key, '').strip() for key in (
        'EMAILJS_SERVICE_ID',
        'EMAILJS_TEMPLATE_ID',
        'EMAILJS_PUBLIC_KEY',
    ))


def send_student_otp(email, code, name='Student'):
    """Send an OTP via EmailJS; account configuration remains server-side."""
    return _send_template(
        os.environ.get('EMAILJS_TEMPLATE_ID', '').strip(),
        {
            'email': email,
            'name': name or 'Student',
            'passcode': code,
            'time': (datetime.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)).strftime('%I:%M %p'),
        },
    )


def send_password_reset_email(email, name, reset_url):
    """Send a one-hour password reset link with the configured reset template."""
    template_id = os.environ.get(PASSWORD_RESET_TEMPLATE_ENV, '').strip()
    if not template_id:
        return False, f'{PASSWORD_RESET_TEMPLATE_ENV} is not configured'
    return _send_template(
        template_id,
        {
            'email': email,
            'name': name or 'Student',
            'link': reset_url,
        },
    )


def _send_template(template_id, template_params):
    settings = {
        'service_id': os.environ.get('EMAILJS_SERVICE_ID', '').strip(),
        'template_id': template_id,
        'user_id': os.environ.get('EMAILJS_PUBLIC_KEY', '').strip(),
        'template_params': template_params,
    }
    private_key = os.environ.get('EMAILJS_PRIVATE_KEY', '').strip()
    if private_key:
        settings['accessToken'] = private_key
    if not all(settings[key] for key in ('service_id', 'template_id', 'user_id')):
        return False, 'EmailJS service, template, or public key is not configured'

    request = urllib.request.Request(
        EMAILJS_URL,
        data=json.dumps(settings).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'BlockLearn/1.0',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
        return True, ''
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', 'replace')[:300]
        return False, f'EmailJS error {error.code}: {detail}'
    except (OSError, TimeoutError) as error:
        return False, str(error)
