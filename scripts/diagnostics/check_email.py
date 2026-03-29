#!/usr/bin/env python
"""Ver configuración actual de email"""
import os

print("=== EMAIL CONFIG ===")
print(f"HOST: {os.getenv('EMAIL_HOST')}")
print(f"USER: {os.getenv('EMAIL_HOST_USER')}")
print(f"PORT: {os.getenv('EMAIL_PORT')}")
print(f"FROM: {os.getenv('DEFAULT_FROM_EMAIL')}")
print(f"PASS: {len(os.getenv('EMAIL_HOST_PASSWORD', ''))} chars")
print(f"SGKEY: {'YES' if os.getenv('SENDGRID_API_KEY') else 'NO'}")
print("\nPARA SENDGRID NECESITAS:")
print("HOST: smtp.sendgrid.net")
print("USER: apikey")
print("PASS: [tu SENDGRID_API_KEY]")