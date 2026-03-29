#!/usr/bin/env python
"""Mostrar qué cambiar en Render"""
import os

print("\n" + "="*50)
print("CAMBIOS NECESARIOS EN RENDER")
print("="*50)

sg_key = os.getenv('SENDGRID_API_KEY', '')
current_host = os.getenv('EMAIL_HOST', '')

print("\nVARIABLES A CAMBIAR:")
print("-"*50)

if current_host != 'smtp.sendgrid.net':
    print("❌ EMAIL_HOST")
    print(f"   Actual: {current_host}")
    print("   Cambiar a: smtp.sendgrid.net")
else:
    print("✅ EMAIL_HOST = smtp.sendgrid.net")

current_user = os.getenv('EMAIL_HOST_USER', '')
if current_user != 'apikey':
    print("\n❌ EMAIL_HOST_USER")
    print(f"   Actual: {current_user}")
    print("   Cambiar a: apikey")
else:
    print("✅ EMAIL_HOST_USER = apikey")

current_pass = os.getenv('EMAIL_HOST_PASSWORD', '')
if current_pass != sg_key:
    print("\n❌ EMAIL_HOST_PASSWORD")
    print("   Actual: [diferente a SENDGRID_API_KEY]")
    print(f"   Cambiar a: {sg_key}")
else:
    print("✅ EMAIL_HOST_PASSWORD = SENDGRID_API_KEY")

print("\n" + "="*50)
print("Ve a Render → Settings → Environment Variables")
print("="*50)