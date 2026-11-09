"""Shared company signature, applied at delivery without changing queued content."""
from django.utils.html import urlize
from django.core.mail import EmailMultiAlternatives
from django.core.mail.message import SafeMIMEMultipart
from email.mime.image import MIMEImage
from pathlib import Path

WATERMARK = Path(__file__).parent / 'email_assets' / 'signature-watermark.png'
WATERMARK_CID = 'sevlink-signature-watermark'


class BrandedEmail(EmailMultiAlternatives):
    """Keep the embedded signature related to HTML, separate from PDF attachments."""
    def _create_mime_attachment(self, content, mimetype):
        part = super()._create_mime_attachment(content, mimetype)
        if mimetype == 'text/html' and ('cid:' + WATERMARK_CID) in content:
            related = SafeMIMEMultipart(_subtype='related', encoding=self.encoding or 'utf-8')
            related.attach(part)
            image = MIMEImage(WATERMARK.read_bytes(), _subtype='png')
            image.add_header('Content-ID', '<' + WATERMARK_CID + '>')
            image.add_header('Content-Disposition', 'inline', filename='sevlink-signature.png')
            related.attach(image)
            return related
        return part


PLAIN_SIGNATURE = ('SEVLINK | Property Maintenance\n'
                   'Your Property. Our Priority.\n'
                   'maintenance@sevlink.co.za\nfinance@sevlink.co.za\ninfo@sevlink.co.za\n'
                   '081 028 5034\nhttps://www.sevlink.co.za')


def branded_bodies(body, *, content_html=None):
    """Keep a readable text alternative and safely render clickable message links."""
    text = str(body)
    html_body = content_html if content_html is not None else urlize(text, autoescape=True).replace('\n', '<br>')
    signature = '''<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin-top:28px"><tr><td>
<a href="https://www.sevlink.co.za" style="text-decoration:none"><img src="cid:sevlink-signature-watermark" width="542" alt="SEVLINK | Property Maintenance. maintenance@sevlink.co.za | finance@sevlink.co.za | info@sevlink.co.za | 081 028 5034 | www.sevlink.co.za. Your Property. Our Priority." style="display:block;width:100%;max-width:542px;height:auto;border:0;border-radius:12px"></a>
</td></tr><tr><td style="padding-top:12px;font:12px Arial,sans-serif;line-height:2;color:#28546b">
<a href="mailto:maintenance@sevlink.co.za" style="color:#28546b">Maintenance</a> &nbsp;·&nbsp;
<a href="mailto:finance@sevlink.co.za" style="color:#28546b">Finance</a> &nbsp;·&nbsp;
<a href="mailto:info@sevlink.co.za" style="color:#28546b">Info</a> &nbsp;·&nbsp;
<a href="tel:+27810285034" style="color:#28546b">Call 081 028 5034</a>
</td></tr></table>'''
    html = ('<!doctype html><html><body style="margin:0;background:#eff6fc;color:#12344e;font-family:Arial,sans-serif">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:24px 12px">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff;border:1px solid #dce7f1;border-radius:14px">'
            '<tr><td style="padding:28px;font-size:14px;line-height:1.7;overflow-wrap:anywhere">'
            + html_body + signature + '</td></tr></table></td></tr></table></body></html>')
    return text + '\n\n' + PLAIN_SIGNATURE, html
