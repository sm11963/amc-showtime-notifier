import smtplib
from email.mime.text import MIMEText


# Sends an email using Gmail SMTP (make sure to use an App Password)
def send_email(subject, body, sender, recipients, password, html=False):
    msg = MIMEText(body, 'html' if html else 'plain')
    msg['Subject'] = subject
    msg['From'] = f"AMC Showtime Notifier <{sender}>"
    msg['To'] = ', '.join(recipients)
    # Adding this header prevents emails being grouped into threads
    msg.add_header('X-Entity-Ref-ID', 'null')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msg.as_string())


def gen_formated_showtimes(showtimes, theatres, html=False):
    by_films = {}
    theatre_keys = [t.split('/')[-1] for t in theatres]
    for fk in set([x.film.key for x in showtimes]):
        ts = [(t, [s for s in showtimes if s.film.key == fk and s.theatre == t]) for t in theatre_keys]
        by_films[fk] = [t for t in ts if len(t[1]) > 0]

    body = ""
    for (k, ts) in by_films.items():

        if html:
            body += f"""
            <p style="margin:0;font-size:14px"> </p>
            <p style="margin:0;font-size:14px"><strong>{k}</strong></p>
            <p style="margin:0;font-size:14px"> </p>
            """
        else:
            body += k + "\n"
        for t in ts:
            if html:
                body += f"""
                <p dir="ltr" style="margin:0;font-size:14px;margin-left:40px">{t[0]}</p>
                <ul style="line-height:1.2">
                    <li style="list-style-type:none">
                        <ul style="line-height:1.2;font-size:14px">
                """
            else:
                body += f"  {t[0]}\n"
            for s in t[1]:
                ds = s.date.strftime("%Y-%m-%d %I:%M %p")
                if html:
                    body += f"""
                                <li dir="ltr"><a href="{s.link}">{ds}</a></li>
                    """
                else:
                    body += f"    [{ds}] - {s.link}\n"
            if html:
                body += """
                        </ul>
                    </li>
                </ul>
                """
            else:
                body += "\n"

    return body


def gen_new_showtimes_email_body(showtimes, theatres):
    body = """
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
    <html><head><META http-equiv="Content-Type" content="text/html; charset=utf-8"><style>*{box-sizing:border-box}body{margin:0;padding:0}#m_MessageViewBody a{color:inherit;text-decoration:none}p{line-height:inherit}.m_desktop_hide,.m_desktop_hide table{display:none;max-height:0;overflow:hidden}.m_image_block img+div{display:none}@media (max-width:520px){.m_mobile_hide{display:none}.m_row-content{width:100%!important}.m_stack .m_column{width:100%;display:block}.m_mobile_hide{min-height:0;max-height:0;max-width:0;overflow:hidden;font-size:0}.m_desktop_hide,.m_desktop_hide table{display:table!important;max-height:none!important}}</style></head><body><u></u><div style="background-color:#fff;margin:0;padding:0"><table class="m_nl-container" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#fff"><tbody><tr><td><table class="m_row m_row-1" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#cd2323">
    <tbody><tr><td><table class="m_row-content m_stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="color:#000;width:500px;margin:0 auto" width="500"><tbody><tr><td class="m_column m_column-1" width="100%" style="font-weight:400;text-align:left;padding-bottom:5px;padding-top:5px;vertical-align:top;border-top:0;border-right:0;border-bottom:0;border-left:0"><table class="m_text_block m_block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="word-break:break-word"><tr><td class="m_pad"><div style="font-family:Verdana,sans-serif"><div style="font-size:14px;font-family:&#39;Lucida Sans Unicode&#39;,&#39;Lucida Grande&#39;,&#39;Lucida Sans&#39;,Geneva,Verdana,sans-serif;color:#555;line-height:1.8"><p style="margin:0;font-size:14px;text-align:center">
    <span style="font-size:26px;color:#ffffff"><strong>AMC Showtime</strong><strong> </strong><strong>Notifier</strong></span></p></div></div></td></tr></table></td></tr></tbody></table></td></tr></tbody></table><table class="m_row m_row-2" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"><tbody><tr><td><table class="m_row-content m_stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:0;color:#000;width:500px;margin:0 auto" width="500"><tbody><tr><td class="m_column m_column-1" width="100%" style="font-weight:400;text-align:left;padding-bottom:5px;padding-top:5px;vertical-align:top;border-top:0;border-right:0;border-bottom:0;border-left:0"><table class="m_text_block m_block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="word-break:break-word"><tr><td class="m_pad"><div style="font-family:sans-serif"><div style="font-size:14px;font-family:Arial,&#39;Helvetica Neue&#39;,Helvetica,sans-serif;color:#555;line-height:1.2"><p style="margin:0;font-size:14px">Found new AMC showtimes!</p>
    """
    body += gen_formated_showtimes(showtimes, theatres, html=True)
    body += """
    </div></div></td></tr></table></td></tr></tbody></table></td></tr></tbody></table></td></tr></tbody></table><div style="background-color:transparent">
        <div style="Margin:0 auto;min-width:320px;max-width:500px;word-wrap:break-word;word-break:break-word;background-color:transparent" class="m_block-grid">
            <div style="border-collapse:collapse;display:table;width:100%;background-color:transparent">
            </div>
        </div>
    </div></div></body></html>
    """

    return body
