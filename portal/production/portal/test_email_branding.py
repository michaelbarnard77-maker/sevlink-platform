from django.test import SimpleTestCase
from .email_branding import branded_bodies


class EmailBrandingTests(SimpleTestCase):
    def test_signature_and_links_with_safe_message_content(self):
        body='Hello PM,\nhttps://portal.example.test/invitation/test-token/\n<script>unsafe</script>'
        plain,html=branded_bodies(body)
        self.assertTrue(plain.startswith(body))
        for content in (plain,html):
            self.assertIn('maintenance@sevlink.co.za',content)
            self.assertIn('Your Property. Our Priority.',content)
        self.assertIn('href="https://portal.example.test/invitation/test-token/"',html)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<img',html)

    def test_inline_watermark_and_pdf_remain_separate(self):
        from email import policy
        from email.parser import BytesParser
        from .email_branding import BrandedEmail
        plain,html=branded_bodies('Test invitation')
        message=BrandedEmail('Test',plain,'test@example.test',['recipient@example.test'])
        message.attach_alternative(html,'text/html')
        message.attach('test.pdf',b'%PDF-synthetic','application/pdf')
        parsed=BytesParser(policy=policy.default).parsebytes(message.message().as_bytes())
        self.assertEqual([p.get_content_type() for p in parsed.iter_attachments()],['application/pdf'])
        images=[p for p in parsed.walk() if p.get_content_type()=='image/png']
        self.assertEqual(len(images),1)
        self.assertEqual(images[0]['Content-ID'],'<sevlink-signature-watermark>')
        self.assertIn('cid:sevlink-signature-watermark',parsed.get_body(preferencelist=('html',)).get_content())

    def test_explicit_test_sender_never_uses_queue_or_persists_credentials(self):
        from unittest.mock import patch, MagicMock
        from django.core.management import call_command
        import io
        provider=MagicMock()
        with patch('portal.management.commands.test_branded_email.input',return_value='test-user'), patch('portal.management.commands.test_branded_email.getpass',return_value='private-test-password'), patch('portal.management.commands.test_branded_email.get_connection',return_value=provider), patch('portal.management.commands.test_branded_email.BrandedEmail') as message:
            message.return_value.send.return_value=1
            out=io.StringIO()
            call_command('test_branded_email',to='synthetic@example.test',stdout=out)
            message.return_value.send.assert_called_once()
            message.return_value.attach_alternative.assert_called_once()
            self.assertIn('SUCCESS',out.getvalue())
            self.assertNotIn('private-test-password',out.getvalue())
