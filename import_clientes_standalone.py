import csv
import re
import psycopg2
from psycopg2 import sql
from datetime import datetime

def normalize_phone(phone):
    original = str(phone)
    cleaned = re.sub(r'\D', '', original).lstrip('0')
    
    if len(cleaned) == 9 and cleaned.startswith('9'):
        return f'+56{cleaned}'
    elif len(cleaned) == 8:
        return f'+569{cleaned}'
    elif len(cleaned) == 11 and cleaned.startswith('569'):
        return f'+{cleaned}'
    return None

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def check_existing_records(cur):
    log("Starting normalization check for existing records...")
    cur.execute("SELECT id, telefono FROM ventas_cliente")
    existing = cur.fetchall()
    log(f"Found {len(existing)} existing records to check")
    
    updated_count = 0
    conflict_count = 0
    
    for record_id, original_phone in existing:
        normalized = normalize_phone(original_phone)
        
        if not normalized:
            log(f"Invalid phone format for record {record_id}: {original_phone}", "WARNING")
            continue
            
        if normalized != original_phone:
            try:
                # Check if normalized phone already exists
                cur.execute("SELECT id FROM ventas_cliente WHERE telefono = %s", (normalized,))
                if cur.fetchone():
                    log(f"Phone conflict: {original_phone} -> {normalized} (already exists)", "WARNING")
                    conflict_count += 1
                    continue
                
                # Update the record
                cur.execute("""
                    UPDATE ventas_cliente 
                    SET telefono = %s 
                    WHERE id = %s
                """, (normalized, record_id))
                log(f"Updated record {record_id}: {original_phone} -> {normalized}")
                updated_count += 1
                
            except Exception as e:
                log(f"Error updating record {record_id}: {str(e)}", "ERROR")
                conflict_count += 1
                
    log(f"Existing records check completed. Updated: {updated_count}, Conflicts: {conflict_count}")

def main(csv_path):
    conn = psycopg2.connect(
        dbname="your_db_name",
        user="your_db_user",
        password="your_db_password",
        host="localhost",
        port="5432"
    )
    
    try:
        with conn.cursor() as cur:
            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ventas_cliente (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    email VARCHAR(254) NOT NULL,
                    telefono VARCHAR(20) NOT NULL UNIQUE,
                    documento_identidad VARCHAR(20),
                    pais VARCHAR(100),
                    ciudad VARCHAR(100)
                )
            """)
            conn.commit()
            
            # Phase 1: Normalize existing records
            check_existing_records(cur)
            conn.commit()
            
            # Phase 2: Process CSV import
            log("Starting CSV import process...")
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_count = 0
                inserted_count = 0
                updated_count = 0
                skipped_count = 0
                
                for row in reader:
                    total_count += 1
                    try:
                        # Data processing
                        nombre = row['Client'].strip()
                        telefono = normalize_phone(row['Telefono'])
                        email = (row['Email'] or '').strip() or None
                        documento = (row['Documento Identidad'] or '').strip() or None
                        direccion_parts = (row['Direccion'] or '').split(', ')
                        ciudad = direccion_parts[0].strip() if direccion_parts else ''
                        pais = 'Chile'

                        if not nombre or not telefono:
                            log(f"Row {total_count}: Skipped - Missing nombre or telefono", "WARNING")
                            skipped_count += 1
                            continue

                        # UPSERT operation
                        cur.execute("""
                            INSERT INTO ventas_cliente 
                                (nombre, email, telefono, documento_identidad, pais, ciudad)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (telefono) DO UPDATE SET
                                nombre = EXCLUDED.nombre,
                                email = EXCLUDED.email,
                                documento_identidad = EXCLUDED.documento_identidad,
                                pais = EXCLUDED.pais,
                                ciudad = EXCLUDED.ciudad
                            RETURNING (xmax = 0)
                        """, (nombre, email, telefono, documento, pais, ciudad))
                        
                        is_insert = cur.fetchone()[0]
                        if is_insert:
                            inserted_count += 1
                            log(f"Row {total_count}: Inserted new record - {telefono}")
                        else:
                            updated_count += 1
                            log(f"Row {total_count}: Updated existing record - {telefono}")
                            
                        conn.commit()
                        
                    except Exception as e:
                        conn.rollback()
                        log(f"Row {total_count}: Error - {str(e)}", "ERROR")
                        skipped_count += 1
                        
                log("\nImport Summary:")
                log(f"Total rows processed: {total_count}")
                log(f"Successfully inserted: {inserted_count}")
                log(f"Successfully updated: {updated_count}")
                log(f"Skipped rows: {skipped_count}")
                
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True)
    args = parser.parse_args()
    
    main(args.csv) 