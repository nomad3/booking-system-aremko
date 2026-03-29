#!/usr/bin/env python
"""Script ultra corto para probar SendGrid"""
import os, smtplib

k = os.getenv('SENDGRID_API_KEY', '')
print(f'Key: {k[:15]}...' if k else 'NO KEY')

try:
    s = smtplib.SMTP('smtp.sendgrid.net', 587)
    s.starttls()
    s.login('apikey', k)
    print('✅ SENDGRID OK!')
    s.quit()
except Exception as e:
    print(f'❌ {e}')