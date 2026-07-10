"""The invitation email escapes tenant-controlled content before rendering it."""

from email_service import _invitation_html


def test_invitation_html_escapes_association_name():
    body = _invitation_html(
        '<script>alert(1)</script> & "Café"',
        "https://abacus.example.com/invitation?token=abc123",
    )
    # The raw markup never lands verbatim in the message body...
    assert "<script>alert(1)</script>" not in body
    # ...it is HTML-escaped instead.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "&amp;" in body


def test_invitation_html_keeps_the_accept_url():
    url = "https://abacus.example.com/invitation?token=abc123"
    body = _invitation_html("Les Amis du Parc", url)
    assert url in body
    assert "Les Amis du Parc" in body
