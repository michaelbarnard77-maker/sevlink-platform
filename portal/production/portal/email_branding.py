"""Shared company signature, applied at delivery without changing queued content."""
from django.utils.html import urlize
from django.core.mail import EmailMultiAlternatives
from django.core.mail.message import SafeMIMEMultipart
from email.mime.image import MIMEImage
from pathlib import Path

WATERMARK = Path(__file__).parent / 'email_assets' / 'signature-watermark.png'
WATERMARK_CID = 'sevlink-signature-watermark'


class BrandedEmail(EmailMultiAlternatives):
    """Keep the embedded watermark related to HTML, separate from PDF attachments."""
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
                   'maintenance@sevlink.co.za\nhttps://www.sevlink.co.za')


def branded_bodies(body):
    """Keep a readable text alternative and safely render clickable message links."""
    text = str(body)
    html_body = urlize(text, autoescape=True).replace('\n', '<br>')
    signature = '''<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin-top:28px;background:#103249;border-radius:12px;color:#fff"><tr><td background="cid:sevlink-signature-watermark" bgcolor="#103249" style="padding:24px;font-family:Arial,sans-serif;background-color:#103249;background-image:url('cid:sevlink-signature-watermark');background-position:center;background-size:cover;background-repeat:no-repeat;border-radius:12px">
<div style="font-size:25px;font-weight:bold;letter-spacing:1px;color:#fff">SEV<span style="color:#a1cfca">LINK</span></div>
<div style="font-size:11px;letter-spacing:2px;color:#d7e7ef;margin-top:5px">PROPERTY MAINTENANCE</div>
<div style="height:1px;background:#49868c;margin:17px 0"></div>
<a href="mailto:maintenance@sevlink.co.za" style="font-size:13px;color:#fff;text-decoration:none">maintenance@sevlink.co.za</a><br>
<a href="https://www.sevlink.co.za" style="font-size:13px;color:#fff;text-decoration:none;line-height:2">www.sevlink.co.za</a>
<div style="font-size:13px;color:#b5dbd3;margin-top:13px">Your Property. Our Priority.</div>
</td></tr></table>'''
    html = ('<!doctype html><html><body style="margin:0;background:#eff6fc;color:#12344e;font-family:Arial,sans-serif">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:24px 12px">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff;border:1px solid #dce7f1;border-radius:14px">'
            '<tr><td style="padding:28px;font-size:14px;line-height:1.7;overflow-wrap:anywhere">'
            + html_body + signature + '</td></tr></table></td></tr></table></body></html>')
    return text + '\n\n' + PLAIN_SIGNATURE, html
