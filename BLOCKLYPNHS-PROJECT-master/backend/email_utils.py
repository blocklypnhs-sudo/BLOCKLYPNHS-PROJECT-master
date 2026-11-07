# backend/email_utils.py
"""
Sending email for BlockLearn (password reset and registration verification).

Settings come from environment variables or a `.env` file in the project root
(see `.env.example`). Credentials are never stored in the source code.

Resend (recommended, https://resend.com):
    RESEND_API_KEY  API key starting with "re_"
    MAIL_FROM       Sender, e.g. "BlockLearn <noreply@yourdomain.com>".
                    Default: onboarding@resend.dev (testing only: Resend delivers
                    it ONLY to the email address your Resend account uses).

Plain SMTP (used only if RESEND_API_KEY is empty), e.g. Gmail:
    MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_USE_SSL

Both:
    APP_BASE_URL    Public URL used in email links, e.g. http://192.168.1.10:5000
"""
import json
import urllib.error
import urllib.request
from email.utils import parseaddr
import html
import os
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr

APP_NAME = 'BlockLearn'
RESET_LINK_MINUTES = 30
VERIFY_LINK_HOURS = 24
PLACEHOLDER_DOMAIN = '@student.blocklearn.edu.ph'  # auto-filled when no real email was given


def _load_env_file():
    """Minimal .env reader so no extra package is needed. Real env vars win."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    path = os.path.join(root, '.env')
    if not os.path.isfile(path):
        return
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def _setting(name, default=''):
    return os.environ.get(name, default).strip()


RESEND_URL = 'https://api.resend.com/emails'
RESEND_TEST_SENDER = 'onboarding@resend.dev'


def provider():
    """Which service sends the mail: 'resend', 'smtp' or None."""
    if _setting('RESEND_API_KEY'):
        return 'resend'
    if _setting('MAIL_USERNAME') and _setting('MAIL_PASSWORD'):
        return 'smtp'
    return None


def email_configured():
    return provider() is not None


def testing_mode():
    """
    True when sending from Resend's shared test domain. Resend only delivers
    those emails to the account owner, so real students can't receive them.
    """
    if provider() != 'resend':
        return False
    sender = parseaddr(_setting('MAIL_FROM') or RESEND_TEST_SENDER)[1].lower()
    return sender.endswith('@resend.dev')


def verification_enforced():
    """
    Registration verification is only enforced when emails can really reach
    students. Otherwise nobody could ever verify and log in.
    """
    return email_configured() and not testing_mode()


def is_real_email(address):
    address = (address or '').strip().lower()
    return bool(address) and '@' in address and not address.endswith(PLACEHOLDER_DOMAIN)


def base_url(request_host_url):
    """
    Base URL for links inside emails. Prefer APP_BASE_URL so a forged Host
    header can't make us email a victim a link that points at an attacker.
    """
    return (_setting('APP_BASE_URL') or request_host_url).rstrip('/')


def _send_via_resend(to_address, subject, text_body, html_body):
    sender = _setting('MAIL_FROM') or RESEND_TEST_SENDER
    if '<' not in sender:
        sender = formataddr((APP_NAME, sender))
    payload = {'from': sender, 'to': [to_address], 'subject': subject, 'text': text_body}
    if html_body:
        payload['html'] = html_body
    request = urllib.request.Request(
        RESEND_URL,
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={
            'Authorization': f"Bearer {_setting('RESEND_API_KEY')}",
            'Content-Type': 'application/json',
            'User-Agent': 'BlockLearn/1.0',  # Resend's firewall rejects requests without one
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
        return True, ''
    except urllib.error.HTTPError as err:
        detail = err.read().decode('utf-8', 'replace')[:300]
        return False, f'Resend error {err.code}: {detail}'
    except Exception as exc:
        return False, str(exc)


def send_email(to_address, subject, text_body, html_body=None):
    """Send one email. Returns (ok, error_message)."""
    service = provider()
    if service is None:
        return False, 'Email is not configured'
    if service == 'resend':
        return _send_via_resend(to_address, subject, text_body, html_body)
    username = _setting('MAIL_USERNAME')
    sender = _setting('MAIL_FROM') or username

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = formataddr((APP_NAME, sender))
    message['To'] = to_address
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype='html')

    host = _setting('MAIL_SERVER', 'smtp.gmail.com')
    port = int(_setting('MAIL_PORT', '587') or 587)
    context = ssl.create_default_context()
    try:
        if _setting('MAIL_USE_SSL').lower() in ('1', 'true', 'yes'):
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as server:
                server.login(username, _setting('MAIL_PASSWORD'))
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls(context=context)
                server.login(username, _setting('MAIL_PASSWORD'))
                server.send_message(message)
        return True, ''
    except Exception as exc:  # network, auth, refused recipient...
        return False, str(exc)


def send_email_async(to_address, subject, text_body, html_body=None):
    """Send in the background so the request returns fast and timing doesn't leak."""
    def worker():
        ok, error = send_email(to_address, subject, text_body, html_body)
        if not ok:
            print(f"❌ [EMAIL] Could not send '{subject}' to {to_address}: {error}")
            if testing_mode():
                print("   Resend test mode: onboarding@resend.dev only delivers to your own Resend account email. "
                      "Verify a domain at resend.com/domains and set MAIL_FROM to send to students.")
                print(f"   [DEV] Email body so you can still test the link:\n{text_body}")
        else:
            print(f"✉️ [EMAIL] Sent '{subject}' to {to_address}")

    threading.Thread(target=worker, daemon=True).start()


# ----------------------------------------------------------------- templates
def _wrap_html(name, intro, button_label, url, footer):
    safe_name = html.escape(name or 'Student')
    return f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:auto;color:#1f2937">
  <h2 style="color:#4f46e5;margin-bottom:4px">{APP_NAME}</h2>
  <p>Hi {safe_name},</p>
  <p>{html.escape(intro)}</p>
  <p style="margin:24px 0">
    <a href="{html.escape(url)}" style="background:#4f46e5;color:#fff;padding:12px 22px;
       border-radius:8px;text-decoration:none;font-weight:bold">{html.escape(button_label)}</a>
  </p>
  <p style="font-size:13px;color:#6b7280">If the button doesn't work, copy this link into your browser:<br>
     <span style="word-break:break-all">{html.escape(url)}</span></p>
  <p style="font-size:13px;color:#6b7280">{html.escape(footer)}</p>
</div>"""


def send_password_reset_email(to_address, name, reset_url):
    intro = f'We received a request to reset your {APP_NAME} password. This link works for {RESET_LINK_MINUTES} minutes.'
    footer = "If you didn't ask for this, you can ignore this email. Your password won't change."
    text = f"Hi {name or 'Student'},\n\n{intro}\n\n{reset_url}\n\n{footer}\n"
    send_email_async(to_address, f'{APP_NAME}: reset your password', text,
                     _wrap_html(name, intro, 'Reset password', reset_url, footer))


def send_verification_email(to_address, name, verify_url):
    intro = f'Welcome to {APP_NAME}! Please confirm your email address to activate your account. This link works for {VERIFY_LINK_HOURS} hours.'
    footer = "If you didn't create this account, you can ignore this email."
    text = f"Hi {name or 'Student'},\n\n{intro}\n\n{verify_url}\n\n{footer}\n"
    send_email_async(to_address, f'{APP_NAME}: verify your email', text,
                     _wrap_html(name, intro, 'Verify email', verify_url, footer))
